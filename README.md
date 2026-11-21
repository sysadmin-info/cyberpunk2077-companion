# CP2077 Companion 0.8.3

**Patch 2.5 — przewodnik gracza** — Ukończ „Skok na głęboką wodę” i dwa zlecenia Wakako. Poczekaj na jej wiadomość. W nowym zadaniu możesz zdobyć pięć elementów zestawu Kinga. W drzewku Opanowanie szukaj atutu Podwójne Kłopoty. Dotyczy pistoletów i rewolwerów typu Power. Wycieczka z Richardem Nightem wymaga ukończenia „Skoku na głęboką wodę” i reputacji 15. Osobne zadanie rozpoczniesz, skanując dowolną z 12 nowych kart Arkanów Małych. To poradnik offline. Nie sprawdza w zapisie, które z tych warunków już spełniasz.

[English](README.en.md) · [Historia zmian](CHANGELOG.md) · [Źródła poradników](GUIDE_SOURCES.md) · [Źródła zewnętrzne](THIRD_PARTY.md) · [Weryfikacja wydania](RELEASE_TESTS.md)

Companion czyta lokalne zapisy Cyberpunka 2077 i pokazuje wynik w przeglądarce. Do uruchomienia, analizy postaci i korzystania z obu wersji językowych wystarczy Python 3.10 lub nowszy. Nie trzeba instalować pakietów przez pip, tworzyć konta ani łączyć się z Internetem. Program nie zapisuje niczego w plikach gry.

## Offline a online

**Jest jedna wersja Companiona.** Panel działa na Twoim komputerze pod adresem `127.0.0.1`. Samo połączenie komputera z internetem nie zmienia działania programu.

| Jak uruchamiasz program w Windows | Czy Companion łączy się z internetem? | Co zobaczysz w panelu |
|---|---|---|
| `.\run.ps1 -Port 9977`, bez dodatkowego katalogu | Nie, również przy pierwszym starcie. | Postać, wyposażenie, schowek, poradniki i eksporty działają. Dla przedmiotów spoza wbudowanej listy panel może pokazać tylko identyfikator lub hash. |
| `.\run.ps1 -UpdateCatalog -Port 9977` | Tak, na Twoje polecenie: pobiera jeden publiczny plik TSV z projektu NightCity Console na GitHubie i sprawdza jego SHA-256. Potem uruchamia lokalny panel. | Więcej przedmiotów z zapisu ma czytelną nazwę i kategorię. Zapis gry, zrzut ekranu i eksporty nie są wysyłane. |
| `.\run.ps1 -Port 9977`, gdy zweryfikowany katalog jest już na dysku | Nie. Program czyta `data/cet_catalog.tsv` z dysku i nie sprawdza, czy w sieci jest nowsza wersja. | Te same rozszerzone nazwy i kategorie działają po odłączeniu internetu. |

Przykład: zwykły pistolet `Items.Preset_Lexington_Default` nie ma nazwy we wbudowanym katalogu. Z dodatkowym TSV Companion rozpoznaje go jako **M-10AF LEXINGTON**. Katalog pomaga nazwać przedmiot; dowodem posiadania pozostaje wpis w ekwipunku lub schowku danego zapisu.

W 0.7.1 skrypt `run.ps1` domyślnie próbował pobrać brakujący katalog. Od 0.8.0 nie trzeba podawać `-NoCatalogDownload`, żeby pracować offline. Kliknięcie źródła poradnika lub mapy to osobna czynność: dopiero wtedy **przeglądarka** otwiera wybraną stronę.

## Uruchomienie

Rozpakuj **cały ZIP** do osobnego katalogu na dysku lokalnym i otwórz w nim terminal. W Windows:

```powershell
.\run.ps1 -Port 9977
```

Od 0.8.1 oba skrypty PowerShell wybierają pierwszy program `py` z `PATH`. Jeśli go nie ma, wybierają pierwszy `python`. W 0.8.0 komunikat z kilkoma ścieżkami do `py.exe` w jednej nazwie oznaczał błąd skryptu, niezależny od portu. Możesz ominąć ten błąd lub uruchomić panel bez zmiany zasad wykonywania skryptów:

```powershell
py -3 .\cp2077_companion.py --port 9977
```

W Linuxie wskaż lokalny katalog zawierający foldery takie jak `ManualSave-660`:

```bash
python3 cp2077_companion.py --save-root "/ścieżka/do/zapisów" --port 9977
```

Program otworzy [panel lokalny](http://127.0.0.1:9977/). Bez opcji portu używa `8765`. Opcja `--no-open` (w skrypcie PowerShell: `-NoOpen`) pomija otwieranie przeglądarki, a Ctrl+C zatrzymuje serwer. Domyślny katalog w Windows to `%USERPROFILE%\Saved Games\CD Projekt Red\Cyberpunk 2077`. Inny wybierzesz przez `-SaveRoot` w PowerShell lub `--save-root` w Pythonie. Nie potrzeba praw administratora.

## Co zostaje na komputerze, a co korzysta z Internetu

| Działanie | Dane i miejsce | Co opuszcza komputer |
|---|---|---|
| Start, wybór i odświeżenie zapisu | Metadane `metadata.*.json`, plik `sav.dat` i, przy wyświetlaniu, lokalny `screenshot.png`. Przeglądarka pobiera wyniki, skrypty, style i tłumaczenia z serwera na tym komputerze. | Nic. Żądania do `127.0.0.1` nie trafiają do Internetu. |
| Poradniki, postać, wyposażenie i ikoniczna broń | Dane dołączone do programu; zweryfikowany katalog TSV na dysku może uzupełnić nazwy przedmiotów. | Nic. Nie ma analityki, zdalnych fontów, CDN, API tłumaczeń ani wywołań usług AI. |
| Język i lista ukrytych interakcji | Przeglądarka zapamiętuje język w ciasteczku `companion_lang`. Oznaczenia interakcji trafiają do `data/hidden_encounters.sqlite3`. | Nic. |
| Eksport na żądanie | Plik pobrany z lokalnego panelu lub katalog eksportu wskazany przy `--once`. Może zawierać nazwy zapisów, wyposażenie i postęp fabuły. | Nic automatycznie. Jeżeli sam udostępnisz eksport, odbiorca pozna jego treść. |
| **Opcjonalne pobranie katalogu** | Jedno żądanie HTTPS GET pobiera publiczną listę przedmiotów z `raw.githubusercontent.com` do `data/cet_catalog.tsv`. | Dostawca widzi zwykłe dane połączenia, m.in. publiczny IP, czas, żądany adres i nagłówki HTTP. Program nie dołącza zapisu, zrzutu, identyfikatora postaci, ścieżek ani eksportu. |
| Kliknięcie odnośnika do źródła lub mapy | Przeglądarka przechodzi do strony wskazanej w karcie, np. Cyberpunk Wiki, EIP lub MapGenie. | Dopiero wtedy przeglądarka łączy się z wybraną stroną. Companion nie dołącza danych zapisu ani nagłówka Referer. |

**Dokładny adres opcjonalnego pliku:** [NightCity Console — runtime/cet_catalog.tsv](https://raw.githubusercontent.com/ysrdevs/nightcity-console-mac/f256a327d533f5058465c7f64e6f4773d0330535/runtime/cet_catalog.tsv). [Repozytorium źródłowe](https://github.com/ysrdevs/nightcity-console-mac/tree/f256a327d533f5058465c7f64e6f4773d0330535). Każdy z 7667 rekordów zawiera identyfikator TweakDB, nazwę wyświetlaną, podkategorię i kategorię. Z tego lokalny resolver obsługuje 7556 wierszy z prefiksami Items., Ammo. i TEST.; pozostałe pomija, w tym 71 pozycji z grupy Keycards. Opis klucza do magazynu nie oznacza, że program wykrył klucz w danym zapisie. Wydanie akceptuje plik o rozmiarze 514 951 bajtów i SHA-256 `e69fbab9fcad414980f3ee6e898043912ba80dc2925a7d94f363c4e9bd1dcbf7`. Adres wskazuje konkretną rewizję. Pobieranie nie śledzi zmian na gałęzi projektu i nie uruchamia pobranego kodu.

Aby pobrać sam katalog, bez uruchamiania panelu:

```powershell
py -3 .\cp2077_companion.py --update-catalog
```

Odpowiednik: `.\update-item-catalog.ps1`. Opcja `.\run.ps1 -UpdateCatalog -Port 9977` najpierw sprawdza pobrany plik, a potem uruchamia panel. Błąd sieci, przekierowanie lub niezgodna suma nie zastępują poprzedniej kopii. Wtedy uruchom program bez opcji aktualizacji. Brak katalogu lub plik o innej sumie nie blokują analizy zapisu; dla części przedmiotów zobaczysz wbudowaną nazwę albo identyfikator.

## Korzystanie z panelu

U góry wybierz **Polski** lub **English**. Zmiana języka zachowuje otwartą kartę i wybór zapisu. Identyfikatory gry, nazwy własne, wartości pochodzące z zapisu i część nazw z opcjonalnego TSV zachowują oryginalne brzmienie.

W trybie automatycznym panel pokazuje najnowszy odczytany zapis. Wybór ręczny wskazuje **folder** zapisu: dwie kopie z tą samą nazwą postaci lub tą samą etykietą gry pozostają rozróżnialne. Panel pokazuje m.in. postać, rozwój, wszczepy, aktywne sloty, wyposażenie, schowek, quickhacki, ikoniczne przedmioty oraz decyzje fabularne. W kartach poradnika odróżniamy potwierdzoną własność od warunków zdobycia: brak przedmiotu w analizowanych kontenerach nie dowodzi, że przedmiot przepadł. Na przykład karta **Gris-Gris** opisuje klucz z zadania `Treating Symptoms` dla Mr. Hands i późniejszy dostęp do skrytki Slidera podczas zadania `The Damned`. Znacznik fabularny lub relacja gracza nie są dowodem, że wybrany zapis zawiera broń.

Lista ukrytych interakcji jest osobna dla każdego przejścia identyfikowanego przez `playthroughID`. Jeśli zapis nie udostępnia tego identyfikatora, oznaczenia dotyczą wyłącznie wybranego folderu. Baza SQLite powstaje przy zapisie oznaczeń lub ręcznym imporcie. Wybór aktualnego zapisu jest wspólny dla kart przeglądarki połączonych z jednym procesem.

## Jak znaleźć zapis do Dnia próby

1. Wybierz u góry zapis z interesującej Cię rozgrywki. Otwórz **Decyzje i konsekwencje → Znajdź zapis do decyzji: Dzień próby** i kliknij **Szukaj zapisów tej rozgrywki**.
2. Wybierz **Ręczne**, jeśli interesują Cię tylko zapisy ręczne. Ten filtr przelicza także podsumowanie. Najpóźniejszy kandydat ma aktywne `q304` i nie ma rozpoznanego sygnału późniejszego etapu. Obok zobaczysz najwcześniejszy późniejszy zapis z potwierdzoną ścieżką. Jeśli kandydata brakuje, panel pokaże najstarszy datowany dowód ścieżki, o ile go znalazł. Nazwa slotu i etap filtrują tabelę.
3. W **Wczytaj grę** porównaj datę i czas gry. Sprawdź w grze, czy rozmowa na stadionie jest jeszcze przed Tobą. Warto zachować osobny ręczny zapis przed podłączeniem do matrycy. Companion nie tworzy kopii ani nie przełącza gry na wskazany slot.

Wyszukiwanie obsługuje na razie decyzję **Songbird/Reed w Firestarter**. Na żądanie przegląda lokalne pliki `metadata.*.json` także poza limitem głównej listy (domyślnie 500). Wymaga zgodnego `playthroughID`; slot bez identyfikatora nie jest łączony z innymi. Wyszukiwarka sprawdza, czy `sav.dat` istnieje i nie jest pusty, ale nie dekoduje go do wyszukiwania. Brak daty wyłącza slot z podsumowania, lecz pozostawia go w tabeli. Przy równych czasach nie wybiera arbitralnie jednego zapisu. Rozgrywka po cofnięciu może zawierać obie ścieżki.

Dodatnia flaga `q304_songbirds_path` lub rozpoznany postęp `q306` wskazuje ścieżkę Songbird; postęp `q305` wskazuje ścieżkę Reeda. Samo ukończenie `q304`, śmierć Hansena ani zerowa flaga nie identyfikują strony wyboru. Osobna karta poradnika pokazuje skutki obu dróg po rozwinięciu spoilerów. Wyszukiwanie nie korzysta z internetu.

## Eksport i przejście z 0.7.1

Zwykłe otwarcie panelu **nie tworzy eksportu**. Przyciski eksportu zapisują wskazany plik na żądanie. Aby bez uruchamiania panelu wyeksportować najnowszy poprawnie zdekodowany zapis wybrany przez program:

```powershell
py -3 .\cp2077_companion.py --once --export-dir .\exports
```

Program zapisze razem `state.json`, `assistant-context.json` i `assistant-context.md` do nowego podkatalogu z czasem UTC i unikatowym sufiksem. Poprzednie eksporty pozostaną nienaruszone. Katalog docelowy musi leżeć poza katalogiem zapisów gry. Odczyt niepełnego lub uszkodzonego wybranego zapisu nie publikuje nowego zestawu.

1. Zatrzymaj poprzednią wersję i rozpakuj 0.8.3 do nowego katalogu. Nie kopiuj całego starego katalogu `data` na nowy.
2. Jeśli zachowujesz oznaczenia z 0.7.1, skopiuj jedynie `data/hidden_encounters_status.json` do `data` w nowej wersji. W panelu wybierz zapis właściwej postaci. W karcie **Ukryte interakcje** użyj przycisku importu. Stary format nie rozróżnia postaci; sam decydujesz, której go przypisać. Ponowny import nie nadpisuje istniejących oznaczeń ani starego pliku.
3. Możesz skopiować stary `cet_catalog.tsv` zamiast pobierać katalog ponownie. Program użyje go tylko po potwierdzeniu sumy. Przy następnym przenoszeniu tej wersji zachowaj `data/hidden_encounters.sqlite3` po zatrzymaniu procesu.

## Granice ochrony i rozwój

Serwer odrzuca nasłuch poza pętlą zwrotną; sprawdza nagłówek Host i pochodzenie zmian stanu. Zapis z panelu wymaga również losowego tokenu bieżącego procesu. Nie wystawiaj go przez proxy ani tunel. Proces działający z uprawnieniami Twojego użytkownika nadal może czytać Twoje pliki. Symlinki, punkty ponownej analizy Windows, ścieżki UNC, mapowane dyski sieciowe Windows i rozpoznane sieciowe systemy plików Linux są odrzucane dla danych wejściowych. Program nie kontroluje synchronizacji OneDrive, Steam ani przeglądarki; wybierz zwykły katalog na dysku lokalnym, jeśli nie chcesz takiej synchronizacji.

Limity odczytu: `sav.dat` 64 MiB, blok LZ4 2 MiB po rozpakowaniu, całość po rozpakowaniu 128 MiB, metadane 1 MiB, obraz 16 MiB. Jeżeli uprzednio odczytany zapis stanie się chwilowo nieczytelny, panel oznacza ostatni poprawny widok tego samego folderu; eksport i zmiana oznaczeń są wtedy wstrzymane do poprawnego odświeżenia. Modyfikowany zapis ponad limitem może nie zostać odczytany. Brakująca nazwa katalogowa lub niepotwierdzony skutek decyzji pozostają oznaczone jako takie.

Tłumaczenia panelu i treści są w `locales/ui.{pl,en}.json` i `locales/content.{pl,en}.json`. Po edycji szablonów w `ui-src` lub etykiet interfejsu uruchom `python tools/build_ui.py`. W CI można użyć `python tools/build_ui.py --check`. W paczce oba panele są już zbudowane; użytkownik nie instaluje gettext i nie kompiluje plików PO/MO.
