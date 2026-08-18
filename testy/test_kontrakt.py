"""
Testy kontraktu walidacyjnego — bez przeglądarki, bez sieci.

Kontrakt brzmi: żaden rekord nie wchodzi do statystyk bez kodu odpowiedzi
HTTP, adresu końcowego i jawnego werdyktu. Zasada powstała po tym, jak
pierwotny skaner zapisał brak wyniku jako wynik.

Te testy sprawdzają samą logikę, więc uruchamiają się w milisekundach
i nie potrzebują ani przeglądarki, ani internetu.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import zbadaj  # noqa: E402


# ---------------------------------------------------- struktura rekordu

def test_pusty_rekord_ma_wszystkie_kolumny():
    r = zbadaj.pusty_rekord("example.com")
    assert set(r.keys()) == set(zbadaj.KOLUMNY)


def test_pusty_rekord_nie_udaje_udanego_pomiaru():
    """Rekord przed pomiarem musi miec werdykt 'blad', nie 'ok'.
    Wartosc domyslna 'ok' byla by dokladnie tym bledem, ktory ten
    projekt istnieje zeby wykrywac."""
    r = zbadaj.pusty_rekord("example.com")
    assert r["Werdykt"] == "blad"
    assert r["Werdykt"] != "ok"


def test_liczniki_startuja_od_zera_a_nie_od_pustego_tekstu():
    r = zbadaj.pusty_rekord("example.com")
    for kolumna in ("Znakow", "Obrazkow", "ImgBezAlt", "Linkow",
                    "LinkiBezTekstu", "Pol", "PolaBezEtykiety", "Razem"):
        assert r[kolumna] == 0, "%s ma byc liczba, nie pustym tekstem" % kolumna
        assert isinstance(r[kolumna], int)


# ------------------------------------------- wykrywanie strony bledu

@pytest.mark.parametrize("tytul,tresc", [
    ("Privacy error", "Your connection is not private"),
    ("", "NET::ERR_CERT_AUTHORITY_INVALID"),
    ("", "err_name_not_resolved"),
    ("", "ERR_CONNECTION_REFUSED"),
    ("Blad prywatnosci", ""),
    ("", "This site can't be reached"),
])
def test_rozpoznaje_strony_bledu_przegladarki(tytul, tresc):
    assert zbadaj.czy_strona_bledu(tytul, tresc) is True


@pytest.mark.parametrize("tytul,tresc", [
    ("Restauracja Pod Roza", "Zapraszamy codziennie od 12:00"),
    ("Menu", "Pizza, makarony, salatki"),
    ("", "Certyfikat jakosci HACCP posiadamy od 2015 roku"),
    ("Kontakt", "Prosimy o rezerwacje telefoniczna"),
])
def test_nie_zglasza_falszywie_zwyklych_stron(tytul, tresc):
    """Falszywy alarm jest tu grozniejszy niz przeoczenie: oznaczylby
    dzialajaca restauracje jako strone bledu i wyrzucil ja ze zbioru."""
    assert zbadaj.czy_strona_bledu(tytul, tresc) is False


def test_slowo_certyfikat_w_tresci_nie_wystarcza():
    """Restauracja moze pisac o certyfikacie HACCP. To nie jest blad
    certyfikatu SSL i nie moze byc tak zaklasyfikowane."""
    assert zbadaj.czy_strona_bledu(
        "O nas", "Nasz certyfikat jakosci odnawiamy co roku") is False


# ----------------------------------------------- wykrywanie przekierowan

@pytest.mark.parametrize("domena,adres", [
    ("example.com", "https://kasyno-online.ru/"),
    ("restauracja.pl", "https://parkingdomen.com/restauracja"),
    ("mojlokal.com", "https://facebook.com/mojlokal"),
])
def test_rozpoznaje_przekierowanie_na_inna_domene(domena, adres):
    assert zbadaj.czy_przekierowana(domena, adres) is True


@pytest.mark.parametrize("domena,adres", [
    ("example.com", "https://example.com/"),
    ("example.com", "https://www.example.com/menu"),
    ("www.example.com", "https://example.com/"),
    ("example.com", "https://example.com.pl/"),
])
def test_nie_zglasza_przekierowania_gdy_domena_ta_sama(domena, adres):
    assert zbadaj.czy_przekierowana(domena, adres) is False


def test_adres_pliku_lokalnego_nie_jest_przekierowaniem():
    """Testy mierza lokalne pliki. Pojecie przekierowania tam nie
    obowiazuje i nie moze faluszowac werdyktu."""
    assert zbadaj.czy_przekierowana(
        "test.local", "file:///C:/testy/strony/czysta.html") is False


def test_pusty_adres_koncowy_nie_powoduje_wyjatku():
    assert zbadaj.czy_przekierowana("example.com", "") is False


# ------------------------------------------------------------- prog tresci

def test_prog_tresci_jest_ustawiony_jawnie():
    """Prog przeniesiony z wersji PowerShell. Jesli ktos go zmieni,
    ten test przypomni, ze zmienia sie tym samym klasyfikacja
    calego zbioru."""
    assert zbadaj.MIN_ZNAKOW_TRESCI == 200


# ------------------------------------------- strona parkingowa

@pytest.mark.parametrize("tytul,domena,znakow,wezly", [
    ("asasushi.com", "asasushi.com", 120, 30),
    ("Asa Sushi", "asasushi.com", 200, 45),
    ("state-chicago", "state-chicago.com", 80, 20),
])
def test_rozpoznaje_strone_parkingowa(tytul, domena, znakow, wezly):
    assert zbadaj.czy_parkingowa(tytul, domena, znakow, wezly) is True


@pytest.mark.parametrize("tytul,domena,znakow,wezly", [
    # dziejaca restauracja: duzo tresci
    ("Asa Sushi", "asasushi.com", 2500, 400),
    # tytul nie ma nic wspolnego z domena
    ("Menu i rezerwacje", "asasushi.com", 100, 30),
    # tresci malo, ale DOM rozbudowany - to nie parking
    ("asasushi.com", "asasushi.com", 100, 500),
    # brak tytulu
    ("", "asasushi.com", 50, 10),
])
def test_nie_zglasza_falszywie_strony_parkingowej(tytul, domena, znakow, wezly):
    assert zbadaj.czy_parkingowa(tytul, domena, znakow, wezly) is False


def test_brak_liczby_wezlow_nie_powoduje_falszywego_werdyktu():
    """Jesli nie udalo sie policzyc wezlow DOM, nie zgadujemy - regula
    wymaga wszystkich trzech warunkow."""
    assert zbadaj.czy_parkingowa("asasushi.com", "asasushi.com", 100, None) is False


@pytest.mark.parametrize("a,b", [
    ("Bar Roza", "bar-roza.pl"),
    ("asasushi.com", "www.asasushi.com"),
    ("STATE-CHICAGO", "state-chicago.com"),
])
def test_rdzen_zestawia_tytul_z_domena(a, b):
    assert zbadaj.rdzen(a) == zbadaj.rdzen(b)


# ------------------------------------- blad nawigacji a blad certyfikatu

@pytest.mark.parametrize("komunikat", [
    "Page.goto: net::ERR_CERT_DATE_INVALID at https://example.com/",
    "Page.goto: net::ERR_CERT_AUTHORITY_INVALID at https://example.com/",
    "Page.goto: net::ERR_CERT_COMMON_NAME_INVALID at https://example.com/",
    "Page.goto: net::ERR_SSL_PROTOCOL_ERROR at https://example.com/",
    "Page.goto: net::ERR_NAME_NOT_RESOLVED at https://example.com/",
    "Page.goto: net::ERR_CONNECTION_REFUSED at https://example.com/",
    "Page.goto: Timeout 22000ms exceeded",
])
def test_kazdy_wyjatek_nawigacji_daje_blad_nawigacji(komunikat):
    """Blad certyfikatu NIE dostaje osobnego werdyktu.

    Przez jeden przebieg dostawal - mapowalem go na "strona bledu
    przegladarki", bo tak mowilo zdanie w moim wlasnym README. Zdanie bylo
    nieprawdziwe: w zbiorze pierwotnym 65 z 94 werdyktow "blad nawigacji"
    to ERR_CERT_* i ERR_SSL_*. Wersja PowerShell nigdy tych stron nie
    mierzyla. Mapowanie zbilo zgodnosc obu implementacji z 93,3% do 90,2%.

    Ten test istnieje po to, zeby taka poprawka nie wrocila.
    """
    assert zbadaj.werdykt_wyjatku_nawigacji(komunikat) == "blad nawigacji"


# ------------------------------------- adres koncowy musi byc koncowy

def test_adres_koncowy_jest_odczytany_po_odczekaniu(monkeypatch):
    """AdresKoncowy zapisywany przed czekaniem na doladowanie tresci nie
    jest adresem koncowym.

    Zmierzone na zywo: bakeforme.com oddaje HTTP 200 ze strona "Access
    Denied", a po 2,5 sekundy JavaScript przerzuca przegladarke na
    forsale.godaddy.com. Rekord mial wiec zapisany adres sprzed
    przekierowania i werdykt policzony po nim - dowod w rekordzie
    przeczyl werdyktowi tego samego rekordu.
    """
    kroki = []

    class StronaUdajaca:
        def __init__(self):
            self._url = "https://przyklad.test/"
        @property
        def url(self):
            return self._url
        def goto(self, *a, **k):
            kroki.append("goto")
            class Odp:
                status = 200
            return Odp()
        def wait_for_timeout(self, ms):
            kroki.append("czekanie")
            self._url = "https://forsale.example/przyklad.test"
        def evaluate(self, skrypt):
            if skrypt == "document.getElementsByTagName('*').length":
                return 400
            return json.dumps({"tytul": "Access Denied", "znakow": 221,
                               "img": 0, "imgZle": 0, "link": 1, "linkZle": 0,
                               "pole": 0, "poleZle": 0, "ramka": 0,
                               "ramkaZle": 0, "brakLang": 0, "brakH1": 1})
        def inner_text(self, sel):
            return "Access Denied"

    s = StronaUdajaca()
    r = zbadaj.zbadaj_domene(s, "przyklad.test", 22000, czekaj_ms=1)

    assert "czekanie" in kroki
    assert r["AdresKoncowy"] == "https://forsale.example/przyklad.test"
    assert r["Werdykt"] == "przekierowanie na inna domene"
