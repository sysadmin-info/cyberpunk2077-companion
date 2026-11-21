# CP2077 Companion — weryfikacja wydań / release verification

[Instrukcja PL](README.md) · [English instructions](README.en.md)

## 0.8.2 — wyszukiwarka decyzji / decision save finder

**PL:** Testy z neutralnymi slotami pokrywają rozgałęzienia `q305/q306`, dodatnie i zerowe flagi, konflikt, brak identyfikatora rozgrywki, kopie o tej samej etykiecie, remisy czasu i slot poza limitem listy. Test Chromium sprawdza wyszukiwanie w PL i EN, oba wyniki w podsumowaniu, filtry, zmianę aktywnej rozgrywki i brak połączeń strony poza komputer. Numer slotu nie jest dowodem momentu dialogu. Nie testowano rozgrywki w silniku gry.

**EN:** Neutral test slots exercise both routes, positive and zero flags, conflicting evidence, missing playthrough IDs, duplicate game labels, timestamp ties and a slot outside the main list. A Chromium test checks both languages, both summary results, filtering, switching playthroughs and absence of off-device page requests. Slot numbers are not evidence of the dialogue frame. The game engine itself was not tested.

```bash
python3 -m unittest tests.test_firestarter -v
# Optional: Playwright for Python and a local Chromium executable
python3 tests/browser_firestarter.py --chromium /path/to/chromium
```

## 0.8.1 — uruchamianie w PowerShell / PowerShell launchers

**PL.** Na Linuxie w PowerShell 7.7.0 odtworzono błąd 0.8.0 z trzema programami `py` na `PATH`. W rozpakowanej 0.8.1 panel odpowiedział pod `127.0.0.1:8765` i `127.0.0.1:9977` po uruchomieniu skryptu spoza katalogu programu. Sprawdzono przypadek z trzema programami `py` oraz wariant bez `py` z kilkoma programami `python`. Oba uruchomienia odczytały lokalną kopię zapisu. W osobnych testach rejestrator wywołań sprawdził również argumenty obu skryptów i kod błędu aktualizacji. Te testy nie pobierają katalogu. Natywny Windows PowerShell 5.1 nie był dostępny w środowisku testowym.

**EN.** The 0.8.0 error was reproduced on Linux using PowerShell 7.7.0 and three `py` applications on `PATH`. Starting the extracted 0.8.1 release from outside its directory served the panel at `127.0.0.1:8765` and `127.0.0.1:9977`. One case had three `py` applications; the other had multiple `python` applications and no `py`. Both read a local save copy. Separate tests recorded both scripts' arguments and checked that a catalog failure preserved the exit code. These tests do not download the catalog. Native Windows PowerShell 5.1 was unavailable in the test environment.

**Powtórzenie w Windows PowerShell 5.1 / Reproduce on Windows PowerShell 5.1** (z katalogu programu / from the project directory):

```powershell
$env:CP2077_TEST_POWERSHELL = (Get-Command powershell.exe -CommandType Application | Select-Object -First 1).Path
py -3 -m unittest tests.test_powershell_launcher -v
```

## 0.8.0 — wcześniejsza weryfikacja / previous release verification

**PL.** Środowisko: Linux, Python 3.12.14, Node.js 24.22.3, PowerShell 7.7.0 i Chromium 158.0.8127.36. Sprawdzono rozpakowaną paczkę, nie tylko robocze drzewo plików. **EN.** Verification ran against an extracted release on Linux with Python 3.12.14, Node.js 24.22.3, PowerShell 7.7.0 and Chromium 158.0.8127.36. No native Windows session was used.

| Próba / Check | Wynik | Result |
|---|---|---|
| `unittest`, w tym dwie lokalne kopie prawdziwych zapisów gry 2.31 | 74 testy zakończone powodzeniem. Obejmują m.in. odczyt kontenerów i wyposażenia, granice parsera, wybór przywróconej kopii, transakcje oznaczeń i import starszej listy. | All 74 tests passed, with two real 2.31 saves. They cover inventory and equipment, parser limits, restored slots, transactional checklist writes and legacy import. |
| Odczyt i eksport offline / offline reading and export | Udało się odczytać i wyeksportować kopię po zmianie nazwy folderu z zablokowaną możliwością nawiązania połączenia przez Pythona. Niekompletny zapis nie nadpisuje wyniku. Porównanie SHA-256 przed i po: identyczne 6/6 plików wejściowych. | Reading and exporting a renamed backup succeeded with Python socket connections blocked. An incomplete save does not overwrite a result. Before/after SHA-256 comparison: all six input files unchanged. |
| Panel PL/EN, rzeczywista przeglądarka / real browser | Sprawdzono wybór i zapamiętanie języka, zachowanie aktywnej karty, zakładki panelu, zmianę zapisu, utrwalenie oznaczenia, opis Gris-Gris i skutki wyborów Anny Hamill. Test rejestrował każde żądanie strony poza lokalny adres i nie wykrył żadnego; brak błędów JavaScript. | Verified language switching and persistence, tab retention, navigation, changing saves, saving a mark, the Gris-Gris guide and Anna Hamill’s branches. The test intercepted page requests: none targeted another host. No JavaScript errors. |
| Start PowerShell i druga próba Chromium / launcher and second browser test | Rzeczywisty skrypt uruchomił serwer na wskazanym porcie i odczytał wskazany katalog. Brak eksportu przy starcie. Sprawdzono także filtry wyposażenia i schowka, paginację 112 modeli i zachowanie rozwiniętych opisów. | The actual launcher served the chosen directory on the specified port and created no startup exports. The browser verified equipment and stash filters, pagination across 112 models and persistence of open guides. |
| Katalog opcjonalny / optional catalog | Pobrano publiczny TSV wyłącznie w ramach osobnej próby aktualizacji. Zgadzały się: SHA-256, 514 951 bajtów i 7667 wierszy po cztery pola. Resolver obsłużył 7556 rekordów. Osobny test sprawdza zachowanie wcześniejszej kopii po błędzie weryfikacji. | The separate updater test fetched the public TSV: its checksum, 514,951 bytes and 7,667 four-field rows matched. The resolver accepted 7,556 records. A separate test checks preservation of the previous file after failed verification. |
| Spójność tłumaczeń i paczki / translation and package consistency | Zgodne klucze obu wersji panelu; wygenerowane pliki odpowiadają szablonom; sprawdzone opisy 112 ikon i warianty poradników decyzji. Archiwum nie zawiera prywatnych zapisów, eksportów, bazy oznaczeń, opcjonalnego TSV ani narzędzi testowej przeglądarki. | Both UI catalogs share their keys; generated assets match their templates. Coverage includes descriptions for all 112 iconic items and the decision guide branches. The archive contains no private saves, exports, checklist database, optional TSV or browser test tooling binaries. |

## Powtórzenie / Reproduce

Z katalogu programu / From the project directory:

```bash
python3 tools/build_ui.py --check
python3 -m unittest discover -s tests -q
node tests/test_ui.cjs
```

**PL:** Bez prywatnych danych część testów zostanie pominięta. Pełna regresja używa konkretnych zapisów `ManualSave-660` i `ManualSave-661`; w zmiennej `CP2077_TEST_SAVE_ROOT` podaj katalog zawierający ich **kopie**. Zastąpienie ich inną rozgrywką zmieni oczekiwane wyposażenie. Node.js i Playwright są opcjonalne, wyłącznie do testów. Nie są zależnościami aplikacji. Test PL/EN sam otwiera serwer na wolnym porcie i używa tymczasowej bazy oznaczeń.

**EN:** Tests requiring private fixtures skip if none are provided. Full regression uses specific `ManualSave-660` and `ManualSave-661` fixtures. Set `CP2077_TEST_SAVE_ROOT` to the directory containing **copies** of both. A different playthrough has different expected equipment. Node.js and Playwright are optional test tools, not application dependencies. The bilingual test starts its own server on a free port and uses a temporary checklist database.

```bash
export CP2077_TEST_SAVE_ROOT="/path/to/fixture-copies"
python3 -m unittest discover -s tests -q
python3 tests/browser_locales.py --save-root "$CP2077_TEST_SAVE_ROOT" --chromium "/path/to/chromium"
```

**PL:** Drugi test przeglądarkowy `node tests/browser_smoke.cjs` wymaga działającego panelu z tymi samymi kopiami. Opcjonalne zmienne: `COMPANION_URL` (adres lokalny) i `CHROMIUM_PATH` (plik wykonywalny Chromium). Nie sprawdzano natywnego Windows, wszystkich modyfikacji gry ani tego, czy inne aplikacje lub sam system synchronizują pliki użytkownika.

**EN:** The second browser test, `node tests/browser_smoke.cjs`, expects a running panel with the same fixtures. Set `COMPANION_URL` (local address) and `CHROMIUM_PATH` (Chromium executable) if needed. Native Windows, every game mod and external OS or browser synchronization were outside this test.
