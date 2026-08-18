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
| jedna karta przeglądarki na całą listę | 53% błędów nawigacji |
| nowa karta na każdą domenę | 89,6% (146 / 163) |
| detektor strony parkingowej | 93,3% (152 / 163) |
| **mapowanie błędu certyfikatu — moja błędna poprawka** | **90,2%** (147 / 163) |
| po wycofaniu jej i naprawie adresu końcowego | **92,6%** (151 / 163) |

Ostatni wiersz jest **nieodróżnialny od przedostatniego przed nim** i to jest
najważniejsza rzecz w tej tabeli. Wyjaśnienie niżej.

### Ile wynosi szum, czyli czego te procenty nie znaczą

Uruchomiłem **ten sam kod dwa razy** na tych samych 163 domenach, w odstępie
dwunastu godzin. Trzy domeny zmieniły werdykt: jedna przekroczyła limit czasu,
jedna oddała 403 zamiast błędu certyfikatu, jedna oddała pustą treść.

**Powtarzalność własnego pomiaru: 160 / 163 = 98,2%.**

Czyli różnica **poniżej dwóch punktów procentowych między przebiegami niczego
nie dowodzi**. Zgodność 93,3% i 92,6% to ta sama liczba. Gdybym nie zmierzył
szumu, ogłosiłbym spadek o siedem dziesiątych punktu jako pogorszenie —
a wzrost o tyle samo jako sukces.

Spadek do 90,2% jest natomiast realny: przekracza szum półtorakrotnie.

### Poprawka, która zepsuła pomiar

Dodałem mapowanie: błąd certyfikatu z Playwrighta miał dostawać werdykt
„strona błędu przeglądarki". Oparłem to na zdaniu **z tego README**, że wersja
PowerShell dostawała w takiej sytuacji stronę błędu i mierzyła ją jako treść.

Zdania nie sprawdziłem przeciwko danym. Po sprawdzeniu:

| Co sprawdziłem | Wynik |
|---|---|
| czy te 12 witryn to błędy certyfikatu | **nie** — tytuły „Access Denied" (10), „403 Forbidden", „404 Not Found" |
| jaki kod HTTP oddawały | **11 z 12 oddało HTTP 200** |
| gdzie wersja PowerShell trzymała błędy certyfikatu | 65 z 94 werdyktów „błąd nawigacji" — **nigdy ich nie mierzyła** |

Obie implementacje zachowywały się z certyfikatami tak samo. Moja poprawka
przesunęła cztery domeny z kategorii, w której **się zgadzały**, do kategorii,
w której się różnią. Stąd cały spadek.

Wycofana. Na jej miejscu stoi test, który blokuje jej powrót.

### Drugi defekt, znaleziony przy okazji

Rekord `bakeforme.com` miał werdykt „przekierowanie na inną domenę"
i adres końcowy równy domenie badanej. **Dowód przeczył werdyktowi w tym
samym wierszu.**

Przyczyna: adres końcowy zapisywałem przed odczekaniem na doładowanie treści,
a werdykt liczyłem po nim. Sprawdzone na żywo:

```
bakeforme.com   http=200
    url przed odczekaniem: https://bakeforme.com/         tytuł: Access Denied
    url po  odczekaniu   : https://forsale.godaddy.com/forsale/bakeforme.com
```

To wyjaśnia tamte 12 witryn lepiej niż moja pierwotna historia: **to są domeny
wystawione na sprzedaż**, pokazujące stronę blokady, która po chwili przeskakuje
na ofertę sprzedaży. Wersja PowerShell mierzyła przed przeskokiem, moja po nim.

Adres końcowy jest teraz odczytywany po odczekaniu, a gdy się zmienił, rekord
zapisuje **oba adresy**. Na 163 domenach wykryło to 8 takich przeskoków.

Nie dodałem detektora „Access Denied", choć podniósłby zgodność o kolejne
punkty. Byłoby to dopasowanie kodu do oczekiwanego wyniku. Różnica jest
prawdziwa i opisana wyżej.

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
- **Wykrywanie strony, która nie jest witryną.** W pierwotnym badaniu
  12 witryn oddało stronę blokady zamiast strony firmy — tytuł „Access
  Denied" (10 z nich), „403 Forbidden", „404 Not Found", treść od 52 do
  265 znaków — a skaner policzył to jako treść restauracji i zaraportował
  udany pomiar. **Jedenaście z dwunastu oddało przy tym HTTP 200.**
  Kontrola samego kodu odpowiedzi nie wykryłaby żadnej z nich.
- **Certyfikat odrzucony kończy pomiar, nie zmienia go.**
  `ignore_https_errors` jest jawnie ustawione na `False` — ten błąd chcemy
  **widzieć**, a nie ukryć. Wersja PowerShell robiła to samo: 65 z 94 jej
  werdyktów „błąd nawigacji" to `ERR_CERT_*` i `ERR_SSL_*`.
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

## Testy — 53 przypadki, bez sieci

Zestaw testów w `pytest`, uruchamiany automatycznie przez GitHub Actions
przy każdym wysłaniu kodu.

**Testy nie korzystają z internetu.** Mierzą osiem lokalnych plików HTML
z katalogu `testy/strony`, z których każdy reprezentuje jeden przypadek
o znanym z góry wyniku. Test, który zależy od tego, czy jakaś restauracja
ma dziś włączony serwer, nie jest testem — jest sondą.

| Plik | Co sprawdza | Testów |
|---|---|---|
| `testy/test_kontrakt.py` | logikę bez przeglądarki: klasyfikację werdyktu, stronę blokady, przekierowania, stronę parkingową, moment odczytu adresu końcowego | 43 |
| `testy/test_pomiar.py` | pomiar na lokalnych stronach: liczenie pustych linków, obrazków bez `alt`, pól bez etykiet, progu treści | 10 |

Co konkretnie jest zabezpieczone testem:

- **Strona blokady nie może dostać werdyktu `ok`.** To jest ta klasa błędu,
  która w pierwotnym badaniu przeszła niezauważona — 12 witryn oddających
  „Access Denied" zostało policzonych jako treść restauracji, przy
  poprawnym kodzie HTTP 200.
- **Fałszywy alarm jest groźniejszy niż przeoczenie.** Restauracja pisząca
  o certyfikacie HACCP nie może być zaklasyfikowana jako błąd certyfikatu
  SSL. Osobny test pilnuje właśnie tego kierunku.
- **Rekord przed pomiarem ma werdykt `blad`, nie `ok`.** Wartość domyślna
  `ok` byłaby dokładnie tym błędem, który ten projekt istnieje żeby wykrywać.
- **Suma naruszeń jest przeliczana niezależnie** z pojedynczych kolumn.
  Jeśli się nie zgadza, błąd jest w agregacji, nie w detektorze.
- **Adres końcowy jest odczytywany po odczekaniu na doładowanie treści.**
  Wcześniej zapisywałem go przed tym odczekaniem, a werdykt liczyłem po nim.
  Rekord miał więc adres sprzed przekierowania i werdykt „przekierowanie na
  inną domenę" obok siebie — dowód przeczył werdyktowi w tym samym wierszu.
  Zmierzone na żywo: `bakeforme.com` oddaje HTTP 200 ze stroną „Access
  Denied", a po 2,5 sekundy JavaScript przerzuca przeglądarkę na
  `forsale.godaddy.com`.
- **Każdy wyjątek nawigacji daje werdykt „błąd nawigacji", także błąd
  certyfikatu.** Ten test istnieje, bo przez jeden przebieg było tu inaczej.
  Zmapowałem błąd certyfikatu na osobny werdykt, opierając się na zdaniu
  z tego README, którego nie sprawdziłem przeciwko danym. Zdanie było
  nieprawdziwe, a poprawka zbiła zgodność obu implementacji o trzy punkty
  procentowe. Opis niżej.

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
