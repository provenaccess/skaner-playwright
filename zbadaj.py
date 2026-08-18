"""
zbadaj.py — pomiar dostępności stron, wersja w Playwright.

Przepisane z Pobierz-Wyrenderowane.ps1, gdzie to samo było zrobione ręcznie:
surowe połączenie WebSocket do Chrome DevTools Protocol, własna obsługa sesji,
timeoutów i restartów przeglądarki. Playwright jest opakowaniem na dokładnie
ten protokół — ta wersja robi to samo mniejszą ilością kodu.

Kod JavaScript wstrzykiwany do strony jest IDENTYCZNY jak w wersji
PowerShell. Dzięki temu wyniki obu implementacji da się porównać wprost:
jakakolwiek różnica pochodzi od sposobu sterowania przeglądarką,
a nie od zmiany reguł pomiaru.

Zasady przeniesione z wersji PowerShell:
  - żaden rekord nie wchodzi do wyniku bez kodu HTTP, adresu końcowego
    i jawnego werdyktu,
  - odrzucone rekordy dostają zapisaną PRZYCZYNĘ, nie są usuwane po cichu,
  - zapis częściowy, żeby przerwany przebieg nie tracił dotychczasowej pracy.

Użycie:
    py zbadaj.py --plik domeny.txt --wyjscie wynik.csv
    py zbadaj.py --domena example.com
"""

import argparse
import csv
import json
import os
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright, Error as PwError


def uruchom_przegladarke(p):
    """Startuje przegladarke.

    Lokalnie uzywa Chrome zainstalowanego w systemie (channel="chrome"),
    zeby nie pobierac drugiej kopii. W CI takiego Chrome nie ma, wiec
    zmienna SKANER_CHANNEL="" przelacza na przegladarke wbudowana
    w Playwright. Ta sama sciezka kodu w obu miejscach.
    """
    kanal = os.environ.get("SKANER_CHANNEL", "chrome")
    if kanal:
        return p.chromium.launch(channel=kanal, headless=True)
    return p.chromium.launch(headless=True)

# --------------------------------------------------------------------------
# Ten sam skrypt oceny co w Pobierz-Wyrenderowane.ps1 — nie zmieniony ani
# w jednym znaku, żeby porównanie wyników było uczciwe.
# --------------------------------------------------------------------------
SKRYPT_OCENY = r"""
(function(){
 try{
  var r={img:0,imgZle:0,link:0,linkZle:0,pole:0,poleZle:0,ramka:0,ramkaZle:0,
         lang:(document.documentElement.getAttribute('lang')||''),
         tytul:(document.title||''),znakow:0,h1:0};
  r.znakow=(document.body?(document.body.innerText||''):'').replace(/\s+/g,' ').trim().length;
  r.h1=document.querySelectorAll('h1').length;
  var im=document.querySelectorAll('img');
  r.img=im.length;
  for(var i=0;i<im.length;i++){ if(!im[i].hasAttribute('alt')){ r.imgZle++; } }
  var a=document.querySelectorAll('a[href]');
  r.link=a.length;
  for(var i=0;i<a.length;i++){
    var e=a[i], t=(e.textContent||'').trim();
    var al=((e.getAttribute('aria-label')||'')+(e.getAttribute('title')||'')).trim();
    var g=e.querySelector('img[alt]'), ga=g?((g.getAttribute('alt')||'').trim()):'';
    if(!t && !al && !ga){ r.linkZle++; }
  }
  var p=document.querySelectorAll('input:not([type=hidden]):not([type=submit]):not([type=button]):not([type=reset]),select,textarea');
  r.pole=p.length;
  for(var i=0;i<p.length;i++){
    var e=p[i], ok=false;
    if(e.id){ try{ if(document.querySelector('label[for="'+CSS.escape(e.id)+'"]')){ ok=true; } }catch(x){} }
    if(!ok && e.closest && e.closest('label')){ ok=true; }
    if(!ok && (e.getAttribute('aria-label')||'').trim()){ ok=true; }
    if(!ok && e.getAttribute('aria-labelledby')){ ok=true; }
    if(!ok && (e.getAttribute('title')||'').trim()){ ok=true; }
    if(!ok){ r.poleZle++; }
  }
  var f=document.querySelectorAll('iframe');
  r.ramka=f.length;
  for(var i=0;i<f.length;i++){ if(!(f[i].getAttribute('title')||'').trim()){ r.ramkaZle++; } }
  return JSON.stringify(r);
 }catch(err){ return JSON.stringify({blad:String(err)}); }
})()
"""

KOLUMNY = [
    "Domena", "Werdykt", "KodHttp", "AdresKoncowy", "Tytul", "Znakow",
    "Obrazkow", "ImgBezAlt", "Linkow", "LinkiBezTekstu", "Pol",
    "PolaBezEtykiety", "IframeBezTytulu", "BrakLang", "BrakH1", "Razem",
    "Uwaga",
]

# progi klasyfikacji przeniesione z wersji PowerShell
MIN_ZNAKOW_TRESCI = 200


def pusty_rekord(domena):
    r = {k: "" for k in KOLUMNY}
    r["Domena"] = domena
    r["Werdykt"] = "blad"
    for k in ("Znakow", "Obrazkow", "ImgBezAlt", "Linkow", "LinkiBezTekstu",
              "Pol", "PolaBezEtykiety", "IframeBezTytulu", "Razem"):
        r[k] = 0
    return r


def czy_strona_bledu(tytul, tresc):
    """Wykrywa stronę błędu SAMEJ PRZEGLĄDARKI.

    To jest ta klasa błędu, która w pierwotnym badaniu przeszła niezauważona:
    12 witryn z nieprawidłowym certyfikatem oddało stronę błędu Edge,
    a skaner policzył ją jako treść restauracji i zaraportował jako
    udany pomiar.
    """
    sygnaly = [
        "err_cert", "err_ssl", "err_name_not_resolved", "err_connection",
        "privacy error", "blad prywatnosci", "błąd prywatności",
        "this site can", "nie moze polaczyc", "nie może połączyć",
        "your connection is not private",
    ]
    t = (tytul + " " + tresc[:600]).lower()
    return any(s in t for s in sygnaly)


def czy_blad_certyfikatu(komunikat):
    """Czy komunikat Playwrighta opisuje odrzucony certyfikat albo
    nieistniejaca domene - czyli to, co przegladarka pokazalaby jako
    wlasna strone bledu."""
    sygnaly = ("err_cert", "err_ssl", "ssl_", "err_name_not_resolved",
               "err_connection_refused", "err_connection_closed")
    k = (komunikat or "").lower()
    return any(s in k for s in sygnaly)


def zbadaj_domene(strona, domena, timeout_ms, url=None, czekaj_ms=2500):
    """Mierzy jedna strone i zwraca rekord.

    Parametr url pozwala podac adres wprost - uzywaja tego testy,
    ktore mierza lokalne pliki HTML zamiast zywych witryn. Dzieki temu
    testy sa szybkie i deterministyczne: nie zaleza od tego, czy jakas
    restauracja ma dzis wlaczony serwer.
    """
    rekord = pusty_rekord(domena)
    if url is None:
        url = "https://" + domena

    try:
        odp = strona.goto(url, wait_until="load", timeout=timeout_ms)
    except PwError as e:
        komunikat = str(e).splitlines()[0][:160]
        rekord["Uwaga"] = komunikat
        # Blad certyfikatu to NIE jest blad nawigacji.
        #
        # Wersja PowerShell w tej sytuacji dostawala od przegladarki jej
        # wlasna strone bledu i mierzyla ja - stad werdykt "strona bledu
        # przegladarki". Playwright zamiast tego rzuca wyjatek, wiec ta sama
        # rzeczywistosc wyglada inaczej na powierzchni.
        #
        # Na probce 163 domen ta jedna roznica odpowiadala za piec z jedenastu
        # niezgodnosci miedzy implementacjami.
        rekord["Werdykt"] = (
            "strona bledu przegladarki" if czy_blad_certyfikatu(komunikat)
            else "blad nawigacji")
        return rekord

    # KOD HTTP I ADRES KONCOWY — bez tych dwoch rzeczy rekord nie ma prawa
    # wejsc do statystyk. Ta zasada powstala po tym, jak zapisalismy
    # brak wyniku jako wynik.
    rekord["KodHttp"] = odp.status if odp else ""
    rekord["AdresKoncowy"] = strona.url

    if odp and odp.status >= 400:
        rekord["Werdykt"] = "blad HTTP %d" % odp.status
        return rekord

    # Czas na dorysowanie tresci po zdarzeniu load (odpowiednik Start-Sleep 3
    # w wersji PowerShell). Potrzebny przy zywych witrynach, ktore doladowuja
    # tresc leniwie. Testy na lokalnych plikach podaja tu 0 - nie ma czego
    # czekac, a zestaw testow ma byc szybki.
    if czekaj_ms:
        strona.wait_for_timeout(czekaj_ms)

    try:
        surowy = strona.evaluate(SKRYPT_OCENY)
    except PwError as e:
        rekord["Werdykt"] = "blad pomiaru"
        rekord["Uwaga"] = str(e).splitlines()[0][:160]
        return rekord

    o = json.loads(surowy)
    if o.get("blad"):
        rekord["Werdykt"] = "blad w przegladarce"
        rekord["Uwaga"] = o["blad"][:160]
        return rekord

    tytul = o.get("tytul", "")
    try:
        tresc = strona.inner_text("body")[:800]
    except PwError:
        tresc = ""

    # Liczba wezlow DOM - potrzebna wylacznie do rozpoznania strony
    # parkingowej. OSOBNE wywolanie, zeby nie ruszac SKRYPT_OCENY, ktory ma
    # zostac identyczny znak w znak z wersja PowerShell. Inaczej porownanie
    # obu implementacji przestaloby cokolwiek znaczyc.
    try:
        wezlow_dom = strona.evaluate("document.getElementsByTagName('*').length")
    except PwError:
        wezlow_dom = None

    rekord.update({
        "Tytul": tytul,
        "Znakow": o["znakow"],
        "Obrazkow": o["img"],
        "ImgBezAlt": o["imgZle"],
        "Linkow": o["link"],
        "LinkiBezTekstu": o["linkZle"],
        "Pol": o["pole"],
        "PolaBezEtykiety": o["poleZle"],
        "IframeBezTytulu": o["ramkaZle"],
        "BrakLang": "nie" if o.get("lang") else "TAK",
        "BrakH1": "nie" if o.get("h1", 0) > 0 else "TAK",
    })

    suma = o["imgZle"] + o["linkZle"] + o["poleZle"] + o["ramkaZle"]
    if not o.get("lang"):
        suma += 1
    rekord["Razem"] = suma

    # --- klasyfikacja: czym ta strona w ogole jest ---
    # Kolejnosc jak w Zbadaj-Strone.ps1: najpierw czym strona NIE jest,
    # dopiero na koncu 'ok'. Przekierowanie przed strona parkingowa, bo
    # domena sprzedana czesto prowadzi gdzie indziej.
    if czy_strona_bledu(tytul, tresc):
        rekord["Werdykt"] = "strona bledu przegladarki"
    elif czy_przekierowana(domena, strona.url):
        rekord["Werdykt"] = "przekierowanie na inna domene"
    elif czy_parkingowa(tytul, domena, o["znakow"], wezlow_dom):
        rekord["Werdykt"] = "strona parkingowa"
    elif o["znakow"] < MIN_ZNAKOW_TRESCI:
        rekord["Werdykt"] = "strona praktycznie pusta"
    else:
        rekord["Werdykt"] = "ok"

    return rekord


def rdzen(nazwa):
    """Rdzen nazwy domeny albo tytulu - do porownania ze soba.

    Odpowiednik funkcji Rdzen z Zbadaj-Strone.ps1: zostawia same litery
    i cyfry z pierwszego czlonu, zeby 'Bar Roza' i 'bar-roza.pl' dalo sie
    zestawic.
    """
    n = (nazwa or "").strip().lower()
    n = n.removeprefix("www.")
    n = n.split(".")[0]
    return "".join(c for c in n if c.isalnum())


def czy_parkingowa(tytul, domena, znakow, wezlow_dom):
    """Strona parkingowa: tytul rowny nazwie domeny, znikoma tresc,
    prawie pusty DOM.

    Regula przeniesiona z Zbadaj-Strone.ps1 wraz z progami. Wersja
    Playwright dlugo jej nie miala i na probce 163 domen dawalo to cztery
    bledne werdykty: strony zaparkowane trafialy do 'praktycznie pusta'
    albo nawet do 'ok'.
    """
    if not tytul:
        return False
    return (rdzen(tytul) == rdzen(domena)
            and znakow < 400
            and wezlow_dom is not None and wezlow_dom < 60)


def czy_przekierowana(domena, adres_koncowy):
    """Czy adres koncowy prowadzi gdzie indziej niz badana domena.

    Adresy file:// pomijamy - uzywaja ich testy na lokalnych plikach,
    gdzie pojecie przekierowania nie ma zastosowania.
    """
    if adres_koncowy.startswith("file:"):
        return False

    gospodarz = urlparse(adres_koncowy).hostname or ""
    gospodarz = gospodarz.removeprefix("www.").lower()
    cel = domena.removeprefix("www.").lower()
    if not gospodarz:
        return False

    # zgodny, jesli rdzen nazwy badanej domeny wystepuje w adresie koncowym
    rdzen = cel.split(".")[0]
    return rdzen not in gospodarz


def zapisz(sciezka, rekordy):
    with open(sciezka, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=KOLUMNY, quoting=csv.QUOTE_ALL)
        w.writeheader()
        w.writerows(rekordy)


def main():
    ap = argparse.ArgumentParser(description="Pomiar dostepnosci stron (Playwright).")
    ap.add_argument("--plik", help="plik z lista domen, jedna na linie")
    ap.add_argument("--domena", help="pojedyncza domena")
    ap.add_argument("--wyjscie", default="wynik-playwright.csv")
    ap.add_argument("--limit", type=int, default=0, help="zbadaj tylko N pierwszych")
    ap.add_argument("--timeout", type=int, default=25, help="limit czasu na strone, w sekundach")
    ap.add_argument("--zapis-co", type=int, default=10, help="zapis czesciowy co N rekordow")
    ap.add_argument("--restart-co", type=int, default=100, help="restart przegladarki co N stron")
    a = ap.parse_args()

    if a.domena:
        lista = [a.domena.strip()]
    elif a.plik:
        lista = [l.strip() for l in Path(a.plik).read_text(encoding="utf-8-sig").splitlines() if l.strip()]
    else:
        ap.error("podaj --plik albo --domena")

    if a.limit:
        lista = lista[:a.limit]

    print("Do zbadania: %d domen" % len(lista))
    print("Wyjscie:     %s" % a.wyjscie)
    print("")

    rekordy = []
    start = time.time()

    with sync_playwright() as p:
        przegladarka = uruchom_przegladarke(p)
        kontekst = przegladarka.new_context(
            viewport={"width": 1280, "height": 900},
            locale="en-US",
            ignore_https_errors=False,   # chcemy WIDZIEC blad certyfikatu, nie ukryc go
        )

        for i, dom in enumerate(lista, 1):
            # restart przegladarki, zeby dlugi przebieg nie zjadl pamieci
            if a.restart_co and i > 1 and (i - 1) % a.restart_co == 0:
                kontekst.close(); przegladarka.close()
                przegladarka = uruchom_przegladarke(p)
                kontekst = przegladarka.new_context(
                    viewport={"width": 1280, "height": 900}, locale="en-US")
                print("   [restart przegladarki po %d stronach]" % (i - 1))

            # NOWA KARTA NA KAZDA DOMENE.
            #
            # Pierwsza wersja tego skryptu uzywala jednej karty dla calej listy
            # i na reprezentatywnej probce 163 domen zwrocila 86 bledow
            # nawigacji - 53%. Komunikat brzmial:
            #   "Navigation to <domena> is interrupted by another navigation
            #    to <POPRZEDNIA domena>"
            # Czyli niedokonczone przekierowanie poprzedniej strony przerywalo
            # wejscie na nastepna. Wersja PowerShell tego bledu nie miala,
            # bo otwierala nowa karte na kazda domene
            # (/json/new?url=about:blank).
            #
            # Na probce 12 domen blad byl niewidoczny, bo wszystkie byly
            # wczesniej zaklasyfikowane jako dzialajace i zadna nie
            # przekierowywala.
            strona = kontekst.new_page()
            try:
                r = zbadaj_domene(strona, dom, a.timeout * 1000)
            finally:
                strona.close()
            rekordy.append(r)

            print("  %4d/%d  %-34s %-28s %s" % (
                i, len(lista), dom[:34], r["Werdykt"][:28],
                ("linkow bez nazwy: %s" % r["LinkiBezTekstu"]) if r["Werdykt"] == "ok" else ""))

            if a.zapis_co and i % a.zapis_co == 0:
                zapisz(a.wyjscie, rekordy)

        kontekst.close()
        przegladarka.close()

    zapisz(a.wyjscie, rekordy)

    # --- podsumowanie ---
    print("")
    print("Czas: %.1f s  (%.1f s na strone)" % (time.time() - start,
                                                (time.time() - start) / max(1, len(lista))))
    print("")
    print("Werdykty:")
    ile = {}
    for r in rekordy:
        ile[r["Werdykt"]] = ile.get(r["Werdykt"], 0) + 1
    for w, n in sorted(ile.items(), key=lambda x: -x[1]):
        print("  %-30s %4d" % (w, n))

    ok = [r for r in rekordy if r["Werdykt"] == "ok"]
    if ok:
        z_pustymi = sum(1 for r in ok if r["LinkiBezTekstu"] > 0)
        print("")
        print("Ze stron zmierzonych (%d): %d ma pusty link = %.1f%%" % (
            len(ok), z_pustymi, 100.0 * z_pustymi / len(ok)))


if __name__ == "__main__":
    sys.exit(main())
