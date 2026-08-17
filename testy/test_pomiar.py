"""
Testy pomiaru — na lokalnych plikach HTML, bez sieci.

Dlaczego lokalne pliki, a nie żywe witryny: test, który zależy od tego,
czy jakaś restauracja ma dziś włączony serwer, nie jest testem. Jest
sondą. Każda strona w katalogu `strony/` reprezentuje jeden konkretny
przypadek, a spodziewany wynik jest znany z góry.

Zasada przeniesiona ze `Test-Rzetelnosc.ps1`: liczby sprawdzamy tam,
gdzie znamy prawdę, a nie tam, gdzie prawdy nie da się ustalić.
"""

import sys
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import zbadaj  # noqa: E402

STRONY = Path(__file__).parent / "strony"


def adres(nazwa):
    return (STRONY / nazwa).resolve().as_uri()


@pytest.fixture(scope="module")
def strona():
    with sync_playwright() as p:
        przegladarka = zbadaj.uruchom_przegladarke(p)
        kontekst = przegladarka.new_context(
            viewport={"width": 1280, "height": 900}, locale="en-US")
        s = kontekst.new_page()
        yield s
        kontekst.close()
        przegladarka.close()


def zmierz(strona, nazwa, domena="test.local"):
    # czekaj_ms=0: lokalne pliki nie doladowuja tresci, wiec czekanie
    # bylo by tylko strata czasu w zestawie testow
    return zbadaj.zbadaj_domene(strona, domena, 15000, url=adres(nazwa), czekaj_ms=0)


# ----------------------------------------------------------------- werdykty

def test_strona_poprawna_dostaje_werdykt_ok(strona):
    r = zmierz(strona, "czysta.html")
    assert r["Werdykt"] == "ok"
    assert r["Razem"] == 0, "strona bez barier nie powinna miec naruszen"


def test_strona_bledu_przegladarki_nie_jest_liczona_jako_tresc(strona):
    """To jest ta klasa bledu, ktora w pierwotnym badaniu przeszla
    niezauwazona: 12 witryn z nieprawidlowym certyfikatem oddalo strone
    bledu przegladarki, a skaner policzyl ja jako tresc restauracji."""
    r = zmierz(strona, "blad-certyfikatu.html")
    assert r["Werdykt"] == "strona bledu przegladarki"
    assert r["Werdykt"] != "ok", "strona bledu NIE MOZE dostac werdyktu ok"


def test_strona_bez_tresci_dostaje_werdykt_pusta(strona):
    r = zmierz(strona, "praktycznie-pusta.html")
    assert r["Werdykt"] == "strona praktycznie pusta"
    assert r["Znakow"] < zbadaj.MIN_ZNAKOW_TRESCI


# ------------------------------------------------------------------ liczenie

def test_puste_linki_sa_liczone(strona):
    """Strona ma trzy linki bez tekstu: dwa z obrazkiem bez alt
    i jeden calkiem pusty. Czwarty link ma tekst 'Menu'."""
    r = zmierz(strona, "puste-linki.html")
    assert r["Werdykt"] == "ok"
    assert r["Linkow"] == 4
    assert r["LinkiBezTekstu"] == 3


def test_obrazki_bez_alt_sa_liczone(strona):
    """Strona ma trzy obrazki, dwa bez atrybutu alt."""
    r = zmierz(strona, "bez-alt.html")
    assert r["Obrazkow"] == 3
    assert r["ImgBezAlt"] == 2


def test_pola_bez_etykiet_sa_liczone(strona):
    """Formularz ma trzy pola, dwa bez etykiety."""
    r = zmierz(strona, "pola-bez-etykiet.html")
    assert r["Pol"] == 3
    assert r["PolaBezEtykiety"] == 2


def test_brak_atrybutu_lang_jest_wykrywany(strona):
    r = zmierz(strona, "bez-jezyka.html")
    assert r["BrakLang"] == "TAK"
    assert r["Razem"] >= 1, "brak lang liczy sie do sumy naruszen"


def test_brak_naglowka_h1_jest_wykrywany(strona):
    r = zmierz(strona, "bez-h1.html")
    assert r["BrakH1"] == "TAK"


def test_strona_z_lang_nie_jest_zglaszana(strona):
    r = zmierz(strona, "czysta.html")
    assert r["BrakLang"] == "nie"
    assert r["BrakH1"] == "nie"


# ------------------------------------------------- niezalezne przeliczenie

def test_suma_naruszen_zgadza_sie_ze_skladnikami(strona):
    """Przeliczenie sumy OSOBNO, z pojedynczych kolumn.

    Zasada z Test-Rzetelnosc.ps1: nie ufamy jednej sciezce liczenia.
    Jesli suma nie zgadza sie ze skladnikami, blad jest w agregacji,
    a nie w detektorze."""
    for nazwa in ("puste-linki.html", "bez-alt.html", "pola-bez-etykiet.html",
                  "bez-jezyka.html", "czysta.html"):
        r = zmierz(strona, nazwa)
        if r["Werdykt"] != "ok":
            continue
        oczekiwana = (r["ImgBezAlt"] + r["LinkiBezTekstu"]
                      + r["PolaBezEtykiety"] + r["IframeBezTytulu"])
        if r["BrakLang"] == "TAK":
            oczekiwana += 1
        assert r["Razem"] == oczekiwana, (
            "%s: suma %d, skladniki daja %d" % (nazwa, r["Razem"], oczekiwana))
