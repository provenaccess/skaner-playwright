# Ten sam pomiar, dwie implementacje

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

Próbka 12 witryn zmierzonych obydwoma implementacjami:

| Miara | Wynik |
|---|---|
| **Zgodność werdyktu** | **12 / 12 = 100%** |
| **Odsetek stron z pustym linkiem — PowerShell** | 6 z 12 = **50,0%** |
| **Odsetek stron z pustym linkiem — Playwright** | 6 z 12 = **50,0%** |
| Zgodność „ma / nie ma pustego linku" | 12 / 12 = 100% |

**Wniosek zbiorczy jest identyczny**, mimo że liczby jednostkowe się różnią:

| Miara | średnia PowerShell | średnia Playwright |
|---|---|---|
| linków na stronie | 31,7 | 45,2 |
| obrazków na stronie | 12,9 | 20,6 |
| obrazków bez `alt` | 4,5 | 2,2 |
| znaków treści | 2710,7 | 2708,8 |

## Skąd te różnice — i dlaczego są informacją, nie błędem

Wersja Playwright widzi **więcej elementów**: 45 linków wobec 32, 21 obrazków
wobec 13. Powód jest prozaiczny — czeka na zdarzenie `load`, a potem jeszcze
2,5 sekundy, i łapie treść doładowywaną leniwie. Wersja pierwotna mierzyła
wcześniej.

Ciekawsze jest to, co z tego wynika: **obrazków jest więcej, a obrazków bez
`alt` mniej** (2,2 wobec 4,5). Elementy doładowane później to głównie zdjęcia
produktowe, które mają opis. Te złapane wcześniej to ikony i grafiki
dekoracyjne, które opisu nie mają. Zmiana momentu pomiaru przesuwa więc
proporcję, choć nie zmienia werdyktu.

Liczba znaków treści zgadza się niemal dokładnie — 2710,7 wobec 2708,8 — co
potwierdza, że to nie jest przypadkowy szum, a różnica dotyczy konkretnie
elementów doładowywanych.

Oba pomiary wykonano w różnych dniach, więc część różnic to zwykłe zmiany
na stronach.

---

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
| `probka.txt` | lista domen użyta w porównaniu |

## Czego ten pomiar nie obejmuje

Reguły sprawdzają `alt` przy obrazkach, nazwę dostępną linków, etykiety pól
formularza, tytuł ramki i język dokumentu. To wycinek WCAG — pułapek
klawiaturowych, kolejności fokusa ani sensowności tekstu alternatywnego
maszyna nie oceni. Wynik jest **dolną granicą**, nie górną.

Dane wynikowe pierwotnego badania nie są publikowane: zawierają adresy e-mail
i numery telefonu prawdziwych firm pochodzące z OpenStreetMap.
