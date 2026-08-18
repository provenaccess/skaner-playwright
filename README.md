# Ten sam pomiar, dwie implementacje

[![testy](https://github.com/provenaccess/skaner-playwright/actions/workflows/testy.yml/badge.svg)](https://github.com/provenaccess/skaner-playwright/actions/workflows/testy.yml)

Pomiar dostępności stron przepisany z **PowerShell + surowy Chrome DevTools
Protocol** na **Python + Playwright**, a następnie zestawiony z wynikiem
pierwotnej implementacji.

Sens tego projektu nie polega na przepisaniu kodu na nowszą bibliotekę.
Polega na odpowiedzi na pytanie, którego zwykle nikt nie zadaje:
**czy wynik pomiaru przetrwa zmianę narzędzia, którym go wykonano?**

Pomiar pierwotny objął 1 950 domen, z których 1 554 zmierzono silnikiem axe-core.

Projekt pierwotny: [skaner-dostepnosci](https://github.com/provenaccess/skaner-dostepnosci)
· Wyniki: [provenaccess.com](https://provenaccess.com)

---

## Wynik porównania

**Pierwsza próbka, 12 witryn: zgodność werdyktu 100%. I była bezwartościowa.**

Dobrałem ją wyłącznie ze stron zaklasyfikowanych wcześniej jako działające,
więc nie zawierała ani jednego przypadku, w którym niezgodność mogłaby
wystąpić. Sto procent na takiej próbce nie mówi nic.

Na **reprezentatywnej próbce 163 domen**, obejmującej wszystkie osiem
kategorii werdyktu wraz ze stronami odrzuconymi:

| Etap | Zgodność werdyktu |
|---|---|
| pierwsza wersja, jedna karta przeglądarki na całą listę | 53% błędów nawigacji |
| po naprawie: nowa karta na każdą domenę | **89,6%** (146 / 163) |
| po dodaniu detektora strony parkingowej | **93,3%** (152 / 163) |

Rozbieżności ujawniły **dwa defekty mojej implementacji**, nie różnice zdań:

**Współdzielona karta przeglądarki.** Jedna karta dla całej listy powodowała,
że niedokończone przekierowanie poprzedniej strony przerywało wejście na
następną. Komunikat mówił wprost: `Navigation to <domena> is interrupted by
another navigation to <POPRZEDNIA domena>`. Na próbce 12 witryn było to
niewidoczne, bo żadna z nich nie przekierowywała. Wersja PowerShell tego
błędu nie miała, bo otwierała nową kartę na każdą domenę.

**Brak detektora strony parkingowej.** Wersja PowerShell rozpoznaje domeny
zaparkowane po regule: tytuł równy nazwie domeny, mniej niż 400 znaków
treści, mniej niż 60 węzłów DOM. Moja wersja nie miała tego wcale i wrzucała
je do „praktycznie pusta" albo nawet do „ok".

## Miary, które nadal się różnią

| Miara | średnia PowerShell | średnia Playwright |
|---|---|---|
| linków na stronie | 23,4 | 93,0 |
| obrazków na stronie | 10,9 | 40,3 |
| obrazków bez `alt` | 3,8 | 0,5 |
| znaków treści | 2251,7 | 2328,0 |

Odsetek stron z pustym linkiem: **39,7% wobec 49,6%**, zgodność werdyktu
„ma / nie ma pustego linku" wynosi 80,2%.

Liczba znaków treści zgadza się niemal dokładnie, a liczba elementów różni
się czterokrotnie. To znaczy, że obie implementacje widzą **tę samą treść
w innym momencie jej życia**: wersja Playwright czeka na zdarzenie `load`
i jeszcze 2,5 sekundy, więc łapie elementy doładowywane leniwie. Wersja
pierwotna mierzyła wcześniej.

Kierunek różnicy przy `alt` to potwierdza: obrazków jest więcej, a obrazków
bez opisu **mniej** — doładowywane później zdjęcia produktowe mają opisy,
wcześniej złapane ikony ich nie mają.

Oba pomiary wykonano w odstępie kilku dni, więc część różnic to zwykłe
zmiany na stronach.

## Co zostało przeniesione świadomie

Kod JavaScript wstrzykiwany do strony jest **identyczny w obu wersjach, znak
w znak**. Inaczej porównanie nie miałoby sensu: nie dałoby się odróżnić
różnicy wynikającej ze sterownika przeglądarki od różnicy w regułach pomiaru.

Przeniesione zostały też zasady, nie tylko funkcje:

- **Żaden rekord nie wchodzi do wyniku bez kodu HTTP, adresu końcowego
  i jawnego werdyktu.** Zasada powstała po tym, jak pierwotny skaner zapisał
  brak wyniku jako wynik.
- **Odrzucone rekordy dostają zapisaną przyczynę**, nie są usuwane po cichu.
- **Wykrywanie strony błędu samej przeglądarki.** W pierwotnym badaniu
  12 witryn z nieprawidłowym certyfikatem oddało stronę błędu Edge, którą
  skaner policzył jako treść restauracji i zaraportował jako udany pomiar.
  Tutaj `ignore_https_errors` jest jawnie ustawione na `False` — chcemy ten
  błąd **widzieć**, a nie ukryć.
- **Zapis częściowy i restart przeglądarki** co N stron, żeby długi przebieg
  nie tracił pracy i nie zjadał pamięci.

---

## Dlaczego Playwright, a nie surowy CDP

Wersja pierwotna otwierała połączenie WebSocket do portu debugowania
przeglądarki, składała ramki protokołu ręcznie, sama pilnowała identyfikatorów
wiadomości, timeoutów i cyklu życia karty. Playwright jest **opakowaniem na
dokładnie ten sam protokół**.

Efekt: to samo zachowanie w wyraźnie mniejszej ilości kodu, z gotową obsługą
oczekiwania na `load`, statusu odpowiedzi HTTP i adresu po przekierowaniach.

Kolejność ma znaczenie — najpierw napisałem trudniejszą wersję i dopiero przez
nią rozumiem, co Playwright robi pod spodem.

---

## Testy — 54 przypadki, bez sieci

Zestaw testów w `pytest`, uruchamiany automatycznie przez GitHub Actions
przy każdym wysłaniu kodu.

**Testy nie korzystają z internetu.** Mierzą osiem lokalnych plików HTML
z katalogu `testy/strony`, z których każdy reprezentuje jeden przypadek
o znanym z góry wyniku. Test, który zależy od tego, czy jakaś restauracja
ma dziś włączony serwer, nie jest testem — jest sondą.

| Plik | Co sprawdza | Testów |
|---|---|---|
| `testy/test_kontrakt.py` | logikę bez przeglądarki: klasyfikację werdyktu, stronę błędu przeglądarki, przekierowania, stronę parkingową, mapowanie błędu certyfikatu | 44 |
| `testy/test_pomiar.py` | pomiar na lokalnych stronach: liczenie pustych linków, obrazków bez `alt`, pól bez etykiet, progu treści | 10 |

Co konkretnie jest zabezpieczone testem:

- **Strona błędu przeglądarki nie może dostać werdyktu `ok`.** To jest ta
  klasa błędu, która w pierwotnym badaniu przeszła niezauważona — 12 witryn
  z nieprawidłowym certyfikatem zostało policzonych jako treść restauracji.
- **Fałszywy alarm jest groźniejszy niż przeoczenie.** Restauracja pisząca
  o certyfikacie HACCP nie może być zaklasyfikowana jako błąd certyfikatu
  SSL. Osobny test pilnuje właśnie tego kierunku.
- **Rekord przed pomiarem ma werdykt `blad`, nie `ok`.** Wartość domyślna
  `ok` byłaby dokładnie tym błędem, który ten projekt istnieje żeby wykrywać.
- **Suma naruszeń jest przeliczana niezależnie** z pojedynczych kolumn.
  Jeśli się nie zgadza, błąd jest w agregacji, nie w detektorze.
- **Błąd certyfikatu dostaje ten sam werdykt co w wersji PowerShell.**
  Tam przeglądarka zwracała własną stronę błędu i była mierzona; tutaj
  Playwright rzuca wyjątek. Bez zmapowania jednego na drugie porównanie
  obu implementacji kłamałoby.

Uruchomienie lokalne:

```bash
pip install pytest
python -m pytest testy/ -v
```

Cały zestaw wykonuje się w około 22 sekundy, bo strony testowe nie
doładowują treści i pomiar nie czeka na nią (`czekaj_ms=0`).

---

## Uruchomienie

Wymagany Python 3 i zainstalowany Chrome. Playwright korzysta z przeglądarki
obecnej w systemie (`channel="chrome"`), więc nie pobiera własnej.

```bash
pip install playwright

py zbadaj.py --plik probka.txt --wyjscie wynik-playwright.csv
py porownaj.py --nowy wynik-playwright.csv
```

Pojedyncza strona:

```bash
py zbadaj.py --domena example.com
```

## Pliki

| Plik | Rola |
|---|---|
| `zbadaj.py` | pomiar: Playwright, klasyfikacja werdyktu, zapis częściowy, restart przeglądarki |
| `porownaj.py` | zestawienie wyniku z implementacją PowerShell, zgodność werdyktu i miar |
| `probka.txt` | 12 domen z pierwszego, wadliwie dobranego porównania |
| `probka-150.txt` | 163 domeny, przekrój wszystkich ośmiu kategorii werdyktu |

## Czego ten pomiar nie obejmuje

Reguły sprawdzają `alt` przy obrazkach, nazwę dostępną linków, etykiety pól
formularza, tytuł ramki i język dokumentu. To wycinek WCAG — pułapek
klawiaturowych, kolejności fokusa ani sensowności tekstu alternatywnego
maszyna nie oceni. Wynik jest **dolną granicą**, nie górną.

Dane wynikowe pierwotnego badania nie są publikowane: zawierają adresy e-mail
i numery telefonu prawdziwych firm pochodzące z OpenStreetMap.
