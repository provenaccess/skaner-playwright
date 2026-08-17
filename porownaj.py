"""
porownaj.py — zestawia wynik wersji Playwright z wynikiem wersji PowerShell.

Sens tego skryptu jest taki sam, jak sens Test-Rzetelnosc.ps1 w pierwotnym
projekcie: nie ufamy jednej implementacji tylko dlatego, że jest nasza.
Ten sam kod pomiarowy uruchomiony przez dwa różne sterowniki przeglądarki
powinien dać zbliżony wynik. Każda różnica jest informacją, nie szumem.

Użycie:
    py porownaj.py --nowy wynik-playwright.csv
"""

import argparse
import csv
from pathlib import Path

STARY = Path(r"C:\Users\Administrator\Downloads\a11y-leads\klasyfikacja-pelna.csv")

POLA = [
    ("Werdykt",         "werdykt"),
    ("Linkow",          "linkow"),
    ("LinkiBezNazwy",   "linki bez nazwy"),
    ("Obrazkow",        "obrazkow"),
    ("ObrazkiBezNazwy", "obrazki bez alt"),
    ("Znakow",          "znakow tresci"),
]

# nazwy kolumn roznia sie miedzy implementacjami
MAPA = {
    "LinkiBezNazwy":   "LinkiBezTekstu",
    "ObrazkiBezNazwy": "ImgBezAlt",
}


def wczytaj(sciezka, klucz="Domena"):
    with open(sciezka, encoding="utf-8-sig", newline="") as f:
        return {w[klucz]: w for w in csv.DictReader(f)}


def liczba(x):
    try:
        return int((x or "0").strip() or 0)
    except ValueError:
        return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--nowy", default="wynik-playwright.csv")
    ap.add_argument("--stary", default=str(STARY))
    a = ap.parse_args()

    nowy = wczytaj(a.nowy)
    stary = wczytaj(a.stary)

    wspolne = [d for d in nowy if d in stary]
    print("Porownanie dwoch implementacji tego samego pomiaru")
    print("=" * 78)
    print("PowerShell + surowy CDP   vs   Python + Playwright")
    print("")
    print("Domen w wyniku Playwright: %d" % len(nowy))
    print("Wspolnych ze starym zbiorem: %d" % len(wspolne))
    print("")

    if not wspolne:
        print("Brak wspolnych domen - nie ma czego porownac.")
        return

    # --- zgodnosc werdyktu ---
    zgodne_w = sum(1 for d in wspolne if nowy[d]["Werdykt"] == stary[d]["Werdykt"])
    print("ZGODNOSC WERDYKTU: %d z %d = %.1f%%" % (
        zgodne_w, len(wspolne), 100.0 * zgodne_w / len(wspolne)))
    for d in wspolne:
        if nowy[d]["Werdykt"] != stary[d]["Werdykt"]:
            print("   ROZNICA  %-34s PS: %-26s PW: %s" % (
                d[:34], stary[d]["Werdykt"], nowy[d]["Werdykt"]))
    print("")

    # --- zgodnosc liczb ---
    print("%-18s %8s %8s %10s %10s" % ("MIARA", "zgodne", "roznych", "sr. PS", "sr. PW"))
    print("-" * 78)
    for kol_stary, opis in POLA:
        if kol_stary == "Werdykt":
            continue
        kol_nowy = MAPA.get(kol_stary, kol_stary)
        if kol_nowy not in next(iter(nowy.values())):
            continue
        zg = ro = 0
        sps = spw = 0
        for d in wspolne:
            ps = liczba(stary[d].get(kol_stary))
            pw = liczba(nowy[d].get(kol_nowy))
            sps += ps; spw += pw
            if ps == pw: zg += 1
            else: ro += 1
        print("%-18s %8d %8d %10.1f %10.1f" % (
            opis, zg, ro, sps / len(wspolne), spw / len(wspolne)))

    # --- najwazniejsza miara projektu ---
    print("")
    print("ODSETEK STRON Z PUSTYM LINKIEM (tylko werdykt ok w obu):")
    oba_ok = [d for d in wspolne
              if nowy[d]["Werdykt"] == "ok" and stary[d]["Werdykt"] == "ok"]
    if oba_ok:
        ps_zle = sum(1 for d in oba_ok if liczba(stary[d]["LinkiBezNazwy"]) > 0)
        pw_zle = sum(1 for d in oba_ok if liczba(nowy[d]["LinkiBezTekstu"]) > 0)
        print("   PowerShell:  %d z %d = %.1f%%" % (ps_zle, len(oba_ok), 100.0*ps_zle/len(oba_ok)))
        print("   Playwright:  %d z %d = %.1f%%" % (pw_zle, len(oba_ok), 100.0*pw_zle/len(oba_ok)))
        zgodne_wykrycie = sum(
            1 for d in oba_ok
            if (liczba(stary[d]["LinkiBezNazwy"]) > 0) == (liczba(nowy[d]["LinkiBezTekstu"]) > 0))
        print("   zgodnosc 'ma / nie ma pustego linku': %d z %d = %.1f%%" % (
            zgodne_wykrycie, len(oba_ok), 100.0*zgodne_wykrycie/len(oba_ok)))

    # --- gdzie liczby roznia sie najbardziej ---
    print("")
    print("NAJWIEKSZE ROZNICE W LICZBIE PUSTYCH LINKOW:")
    roznice = []
    for d in oba_ok:
        ps = liczba(stary[d]["LinkiBezNazwy"])
        pw = liczba(nowy[d]["LinkiBezTekstu"])
        if ps != pw:
            roznice.append((abs(ps - pw), d, ps, pw))
    roznice.sort(reverse=True)
    if not roznice:
        print("   brak - wszystkie liczby identyczne")
    for _, d, ps, pw in roznice[:10]:
        print("   %-36s PS: %3d   PW: %3d" % (d[:36], ps, pw))
    print("")
    print("Roznice sa oczekiwane: strony zmieniaja sie w czasie, a oba pomiary")
    print("wykonano w roznych dniach. Wazne jest, czy WERDYKT sie zgadza.")


if __name__ == "__main__":
    main()
