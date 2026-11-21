# Changelog — CP2077 Companion

[Instrukcja po polsku](README.md) · [English manual](README.en.md) · [Weryfikacja / Verification](RELEASE_TESTS.md)

Serie wydań / Release series: [0.8](#082--2026-11-21) · [0.7](#071--2026-10-08) · [0.6](#0611--2026-09-23) · [0.5](#055--2026-09-01) · [0.4](#04--2026-08-26) · [0.3](#03--2026-08-26) · [0.2](#02--2026-08-26) · [0.1](#011--2026-08-26)

Daty pominięto tam, gdzie notatki potwierdzają zmianę, ale nie dzień wydania. / Dates are omitted where the change is documented but the release day is unconfirmed.

## 0.8.2 — 2026-11-21

**PL — Dodano.** W zakładce **Decyzje i konsekwencje** jest wyszukiwarka zapisów dla „Dnia próby” (*Firestarter*). Porównuje lokalne metadane slotów tej samej rozgrywki, również poza limitem głównej listy. Pokazuje najpóźniejszego kandydata z aktywnym zadaniem i pierwszy późniejszy zapis z dowodem wybranej ścieżki. Można filtrować po rodzaju zapisu, nazwie folderu i etapie. Remisy, sprzeczne dane i brak dowodów są oznaczone; wyszukiwarka nie wczytuje ani nie zmienia zapisu. Nowa karta PL/EN opisuje rozgałęzienie Songbird/Reed oraz różnicę między Chimerą a Cerberusem. [Jak znaleźć zapis](README.md#jak-znaleźć-zapis-do-dnia-próby).

**EN — Added.** The **Choices and consequences** tab now includes a save finder for *Firestarter*. It compares local metadata from the same playthrough, including slots outside the main list limit. It shows the latest active-quest candidate and the first later slot with positive route evidence. Results can be filtered by save type, folder name and stage. Ties, conflicting evidence and missing results are identified; the finder neither loads nor modifies a save. A new bilingual guide explains the Songbird/Reed fork and distinguishes the Chimera from the Cerberus. [How to find a save](README.en.md#find-a-save-for-firestarter).

## 0.8.1 — 2026-11-19

**PL — Poprawiono.** Gdy w `PATH` było kilka plików `py.exe`, skrypt z 0.8.0 przekazywał wszystkie ścieżki jako jedną nazwę polecenia. Panel nie uruchamiał się ani na domyślnym porcie 8765, ani z `-Port 9977`. Teraz `run.ps1` oraz `update-item-catalog.ps1` wybierają pierwszy program `py` z `PATH` i wywołują go z `-3`. Jeśli nie ma `py`, wybierają pierwszy `python`. Błąd jawnej aktualizacji zwraca kod Pythona i nie uruchamia panelu. [Instrukcja uruchomienia](README.md#uruchomienie).

**EN — Fixed.** When several `py.exe` files were on `PATH`, the 0.8.0 launcher passed their paths as a single command name. The panel failed to start on both the default port (8765) and a custom port such as 9977. Both `run.ps1` and `update-item-catalog.ps1` now use the first `py` on `PATH` with `-3`, or the first `python` when `py` is absent. A failed explicit catalog update returns Python's exit code and does not start the panel. [Startup instructions](README.en.md#quick-start).

## 0.8.0 — 2026-11-19

### Polski

#### Dodano

- **Panel PL/EN.** Przełącznik języka obejmuje interfejs i poradniki. Przeglądarka pamięta wybór; zmiana języka zachowuje aktywną kartę i wybrany zapis. Oba tłumaczenia są w paczce.

#### Zmieniono

- **Start bez internetu.** W 0.7.1 skrypt `run.ps1` próbował pobrać katalog przedmiotów, gdy brakowało go na dysku. Teraz pobiera go wyłącznie z opcją `-UpdateCatalog`. Wydanie akceptuje jeden plik TSV z konkretnej rewizji NightCity Console po sprawdzeniu rozmiaru i SHA-256. Nieudana aktualizacja zachowuje dotychczasowy plik. [Co działa offline?](README.md#offline-a-online)
- **Eksport na żądanie.** Otwarcie panelu nie tworzy już eksportów. Opcja `--once` zapisuje trzy pliki w nowym katalogu dopiero po poprawnym odczycie. Poprzednie eksporty pozostają nienaruszone. Usunięto z eksportów bezwzględne ścieżki do zapisów, zrzutów i katalogu przedmiotów.

#### Poprawiono

- **Przywrócone zapisy.** Panel wybiera zapis po folderze. Zmiana nazwy folderu kopii lub powtórzona etykieta gry nie powodują już pominięcia odczytu ekwipunku. Gdy wcześniej odczytany plik staje się chwilowo nieczytelny, panel oznacza ostatni poprawny odczyt tego samego zapisu i wstrzymuje eksport.
- **Oznaczenia osobno dla każdego przejścia.** Ukryte interakcje są zapisywane w transakcjach SQLite. Gdy gra nie podaje `playthroughID`, oznaczenia dotyczą folderu zapisu. Starą listę JSON można ręcznie przypisać do wybranej postaci; ponowny import zachowuje istniejące oznaczenia.

#### Bezpieczeństwo

- **Ochrona lokalnego serwera i parsera.** Serwer przyjmuje połączenia tylko na pętli zwrotnej, sprawdza nagłówek `Host`, a przy zmianach z panelu także pochodzenie żądania i token sesji. Parser ogranicza rozmiar plików i danych po dekompresji: 64 MiB na `sav.dat`, 2 MiB na blok LZ4 i 128 MiB łącznie po rozpakowaniu.

Instrukcja: [przeniesienie oznaczeń z 0.7.1 i nowy układ eksportów](README.md#eksport-i-przejście-z-071).

### English

#### Added

- **Polish and English panel.** The language selector covers the interface and guides. The browser remembers the choice; switching languages preserves the active tab and selected save. Both translations ship with the app.

#### Changed

- **Offline startup.** In 0.7.1, `run.ps1` tried to download the item catalog when it was missing. It now downloads it only with `-UpdateCatalog`. This release accepts one TSV from a pinned NightCity Console revision after checking its size and SHA-256. A failed update preserves the previous file. [What works offline?](README.en.md#offline-and-online)
- **On-demand exports.** Opening the panel no longer writes exports. After a successful read, `--once` writes all three files into a new directory and preserves earlier exports. Exports no longer include absolute paths to saves, screenshots or the item catalog.

#### Fixed

- **Restored saves.** The panel identifies each save by its directory. Renaming a backup directory or restoring two saves with the same in-game label no longer causes inventory decoding to be skipped. If a previously decoded save becomes temporarily unreadable, the panel labels its last successful read and blocks exports.
- **Per-playthrough checklists.** Hidden encounter marks now use SQLite transactions. If the game provides no `playthroughID`, marks apply to the save directory. You can import the old JSON checklist into the selected character; repeated imports preserve existing marks.

#### Security

- **Local server and parser safeguards.** The server binds only to loopback and validates the `Host` header. Panel writes also require a matching origin and a session token. The parser limits `sav.dat` to 64 MiB, each decompressed LZ4 block to 2 MiB and total decompressed output to 128 MiB.

Upgrade notes: [migrating 0.7.1 checklist marks and the new export layout](README.en.md#export-and-upgrade-from-071).

## 0.7.1 — 2026-10-08

**PL:** Przed otwarciem panelu program sprawdza, czy pliki `index.html`, `app.js` i `styles.css` istnieją i nie są puste. Jeśli przeglądarka nie załaduje skryptu, wyświetla błąd zamiast pozostawać na komunikacie „Czytam zapisy…”. Dzięki temu brak pliku interfejsu można odróżnić od problemu z odczytem zapisu gry.

**EN:** Startup checks that `index.html`, `app.js` and `styles.css` are present and nonempty. If the browser cannot load the script, the page reports the error instead of staying on the save-loading message. This distinguishes a missing interface file from a save parsing failure.

## 0.7.0 — 2026-10-01

**PL:** Dodano kartę **Quickhacki / Cyberdeck**: rozróżnia gotowe programy i schematy w 17 rodzinach oraz pokazuje wyposażony system operacyjny. Program w plecaku nie potwierdza obsadzenia slotu cyberdecku. Druga nowa karta opisuje 49 wariantów w 20 zadaniach; skutki decyzji pozostają ukryte do rozwinięcia. Obie sekcje trafiły do eksportu `assistant-context` v9.

**EN:** Added the **Quickhacks / Cyberdeck** tab, which separates usable programs from crafting specs across 17 families and shows the equipped operating system. A program in the backpack does not prove it occupies a cyberdeck slot. A second tab covers 49 branches across 20 quests, with consequences hidden until expanded. Both sections are included in `assistant-context` v9 exports.

## 0.6.11 — 2026-09-23

**PL:** Automatyczne odświeżenie przestało przebudowywać tabelę broni, gdy jej dane się nie zmieniły. Otwarty opis pozostaje rozwinięty, a pojawienie się paska przewijania nie przesuwa widoku na boki.

**EN:** Automatic refresh no longer rebuilds the weapon table when its data is unchanged. Open guides stay expanded, and the page no longer shifts sideways when a scrollbar appears.

## 0.6.10 — 2026-09-23

**PL:** Poprawiono wykrywanie **Psalm 11:6**, **Comrade’s Hammer** i **Sasquatch’s Hammer** na podstawie identyfikatorów rzeczywiście zapisanych w grze. Zwykły młot `Items.Preset_Hammer_Default` nie jest zaliczany do broni ikonicznej. Liczba modeli w katalogu pozostała bez zmian: 112.

**EN:** Fixed detection of **Psalm 11:6**, **Comrade’s Hammer** and **Sasquatch’s Hammer** using item IDs observed in saves. The standard hammer (`Items.Preset_Hammer_Default`) does not count as iconic. The catalog still contains 112 models.

## 0.6.9 — 2026-09-23

**PL:** Doprecyzowano pięć poradników: wejście na szczyt Heavy Hearts po **Claw X-MOD2**, alternatywne dojście do **Guillotine X-MOD2**, skrytkę **Kappa X-MOD2** za blachą oraz sposoby zdobycia **Volkodava** i **Chesapeake**. Była to aktualizacja opisów istniejących broni.

**EN:** Updated five existing guides: the climb to **Claw X-MOD2** on top of Heavy Hearts, an alternative way to reach **Guillotine X-MOD2**, the **Kappa X-MOD2** stash behind sheet metal, and acquisition routes for **Volkodav** and **Chesapeake**.

## 0.6.8 — 2026-09-21

**PL:** Uzupełniono ostatnie 14 poradników: wszystkie 112 modeli mają opis zdobycia ze źródłem. W karcie **Gris-Gris** pojawiła się zależność między zadaniami: w *Treating Symptoms* dla Mr. Hands trzeba zabrać klucz z biurka przy komputerze, żeby w *The Damned* otworzyć magazyn w kryjówce Slidera. Opis podaje warunek; nie potwierdza posiadania klucza w konkretnym zapisie.

**EN:** Completed the last 14 guides: all 112 models now have a sourced acquisition description. The **Gris-Gris** entry explains the link between two quests: take the storeroom key from the desk by the computer during Mr. Hands’ *Treating Symptoms*, then use it at Slider’s hideout in *The Damned*. The guide describes the requirement; it does not detect the key in a particular save.

## 0.6.7 — 2026-09-19

**PL:** Dodano 26 opisów zdobycia (łącznie 98 ze źródłem) i dziewięć odnośników do znaczników mapy (łącznie 46 modeli ze znacznikiem). Wycofano automatyczną etykietę „Zwykle dostępna”: sam poradnik nie rozstrzyga, czy wcześniejszy wybór zamknął drogę do nagrody.

**EN:** Added 26 acquisition descriptions (98 with sources) and nine map-marker links (46 models with markers). Removed the automatic “usually available” label: a guide alone cannot establish whether an earlier choice locked a reward in the selected playthrough.

## 0.6.6 — 2026-09-19

**PL:** Dodano osobny filtr warunków zdobycia, m.in. dla broni zależnych od decyzji i nagród powiązanych z kontem. Stan „Brak w zapisie” nadal oznaczał tylko brak dopasowania w odczytanym ekwipunku. Wprowadzoną tutaj kategorię „Zwykle dostępna” zmieniono w następnym wydaniu.

**EN:** Added a separate acquisition filter for conditions such as story choices and account rewards. “Missing from save” still meant that no matching item was found in the scanned inventory. The “usually available” category introduced here was revised in the next release.

## 0.6.5 — 2026-09-19

**PL:** Poprawiono paginację zakładki **Iconic**. Usunięto wewnętrzne przewijanie tabeli, dodano nawigację nad i pod listą, a zmiana strony przenosi widok do jej pierwszego wiersza. Na stronie pozostaje do 20 modeli.

**EN:** Fixed pagination in **Iconic Weapons**. Removed the table’s internal vertical scroll, placed navigation above and below the list, and made page changes return to the first row. Each page still shows up to 20 models.

## 0.6.4 — 2026-09-19

**PL:** Dodano 52 modele: kolekcja wzrosła z 60 do 112. Dla 72 modeli istniały już opisy ze źródłami, a dla 40 nadal można było sprawdzać posiadanie mimo braku zweryfikowanego opisu. Tak trafił do katalogu **Gris-Gris**; wskazówkę o kluczu do magazynu dodano w 0.6.8.

**EN:** Added 52 models, growing the collection from 60 to 112. At this point 72 had sourced guides; ownership could still be checked for the 40 whose acquisition guides were pending. **Gris-Gris** entered the registry in this release. Its storeroom-key instructions followed in 0.6.8.

## 0.6.3 — 2026-09-19

**PL:** Do kolekcji dodano lokalne poradniki zdobycia, wyszukiwanie po zadaniach i NPC oraz odnośniki do map. Spośród 60 modeli 49 miało opis sprawdzony w źródłach, a 37 – odnośnik do znacznika. Listę podzielono na strony po 20 modeli.

**EN:** Added offline acquisition guides, search by quest or NPC, and map links. Of the 60 models, 49 had sourced descriptions and 37 had a map-marker link. The list was split into pages of 20.

## 0.6.2 — 2026-09-18

**PL:** W panelu można było ręcznie wybrać zapis zamiast automatycznie wczytywać najnowszy. Wyposażenie, broń ikoniczna, zrzut ekranu i eksport z panelu odpowiadały wybranemu zapisowi. Odświeżenie zachowywało wybór; zniknięcie folderu powodowało komunikat zamiast cichego przełączenia na inny zapis.

**EN:** Added manual save selection alongside automatic selection of the latest save. Equipment, iconic weapons, the screenshot and downloads from the panel follow the selected slot. Refresh preserves the selection; a missing slot produces a message instead of silently switching to another save.

## 0.6.1 — 2026-09-18

**PL:** Rozszerzono kolekcję z 13 do 60 modeli. Parser zaczął odróżniać **schowek gracza** od innych kontenerów: broń odłożona do schowka liczy się jako posiadana. Warianty jakości, duplikaty i schematy nie zawyżają licznika modeli. Jeśli nie uda się odczytać kontenera, panel nie przypisuje go do schowka.

**EN:** Expanded the registry from 13 to 60 models. The parser now distinguishes the **player stash** from other containers, so a stashed weapon counts as owned. Quality variants, duplicates and crafting specs do not inflate model counts. An unreadable container is not assumed to be the stash.

## 0.6.0 — 2026-09-17

**PL:** Pierwsza karta **Iconic** porównywała 13 modeli z przedmiotami w najnowszym zapisie. Rozróżniała broń wyposażoną, znalezioną w plecaku, znalezioną w innym kontenerze i brak dopasowania. Osobne rozpoznawanie schowka dodano dopiero w 0.6.1.

**EN:** The first **Iconic Weapons** tab checked 13 models against the latest save. It distinguished equipped weapons, backpack items, items in other containers and missing matches. Dedicated stash detection followed in 0.6.1.

## 0.5.5 — 2026-09-01

**PL:** Dodano **Ukryte interakcje** z czterema wpisami: rozmową po walce z Césarem, spotkaniem z Padre, *Stadium Love* i *Only Pain*. Filtr „Nie strzelaj od razu” wyróżniał sceny z opcją rozmowy. Ręczne oznaczenia trafiały do lokalnego pliku JSON; niepotwierdzony warunek spotkania z Padre był oznaczony wprost.

**EN:** Added **Hidden Encounters** with four entries: the conversation after fighting César, the Padre encounter, *Stadium Love* and *Only Pain*. A “don’t shoot first” filter highlighted opportunities for dialogue. Manual marks went into a local JSON file, and the unconfirmed trigger for the Padre encounter was labeled as such.

## 0.5.4

**PL:** Panel oddzielił dokładną wartość zdrowia zapisaną w puli `Health` od samych modyfikatorów zdrowia i braku zapisanych danych. Tabela `StatsSystem` pokazuje m.in. zapisane wartości poziomu, reputacji i atrybutów. Gdy brak puli `Health`, program nie przelicza modyfikatora na rzekome maksymalne HP.

**EN:** Distinguished an exact saved `Health` pool from health modifiers alone and from missing data. The `StatsSystem` table shows saved values for level, Street Cred and attributes. When the save has no health pool, Companion does not report a modifier as the character’s maximum HP.

## 0.5.3

**PL:** Karta **Loadout** i eksport zaczęły obejmować wszystkie zapisane pule statystyk gracza, wraz z wartościami, limitami i sposobem zmiany. Na przykład obecność puli `SandevistanCharge` nie oznacza, że V ma obecnie wyposażony Sandevistan; o tym rozstrzygają sloty wyposażenia.

**EN:** The **Loadout** tab and exports now include all persisted player stat pools with their values, limits and change modes. A saved `SandevistanCharge` pool, for example, does not establish that a Sandevistan is equipped; that information comes from equipment slots.

## 0.5.2

**PL:** Poprawiono nazwy wyświetlane dla **Sulimov**, **Malorian Arms 3516** i **Widow Maker**. Dopasowanie nadal opiera się na identyfikatorze gry. Gdy poprawiona nazwa różni się od nazwy z zewnętrznego katalogu, panel pokazuje również oryginalną etykietę.

**EN:** Corrected the display names of **Sulimov**, **Malorian Arms 3516** and **Widow Maker**. Matching still uses the game’s item ID. When a corrected label differs from the external catalog, the panel also shows the catalog’s original name.

## 0.5.1

**PL:** Poprawiono rozpoznawanie tatuażu Johnny’ego w pierwszym slocie dłoni. Rekord `Items.CasiusTattoo` jest wyświetlany jako **Tattoo: Johnny’s Special**.

**EN:** Fixed recognition of Johnny’s tattoo in the first hand slot. The record `Items.CasiusTattoo` is displayed as **Tattoo: Johnny’s Special**.

## 0.5

**PL:** Nowa karta **Loadout** czytała trzy aktywne sloty broni i zainstalowane wszczepy. Dzięki temu można było odróżnić np. pompę krwi w plecaku od wszczepionej. Odczytano także zapisaną pulę zdrowia; ocena Reaper zaczęła osobno pokazywać gotowość do walki i warunki odblokowania ścieżki.

**EN:** Added **Loadout**, which reads the three active weapon slots and installed cyberware. This distinguishes a Blood Pump in the backpack from one installed in the circulatory system. Companion also reads the saved health pool, and Reaper readiness reports combat preparation separately from conditions for unlocking the route.

## 0.4 — 2026-08-26

**PL:** Dodano pierwszą ocenę gotowości do finału **(Don’t Fear) The Reaper**. Panel zestawiał rozpoznane perki, broń i wszczepy oraz wskazywał, które elementy spełniały kryteria, których brakowało, które były opcjonalne i których zapis nie pozwalał potwierdzić.

**EN:** Added the first readiness assessment for **(Don’t Fear) The Reaper**. It checked recognizable perks, weapons and cyberware, distinguishing criteria met, missing or optional items, and evidence the save could not confirm.

## 0.3 — 2026-08-26

**PL:** Dodano odczyt rozwoju postaci z `PlayerDevelopmentData`. Panel pokazuje atrybuty V, wolne punkty rozwoju, poziomy zdolności i wykupione perki na podstawie zapisu gry.

**EN:** Added character progression from `PlayerDevelopmentData`. The panel reads V’s attributes, unspent development points, skill levels and purchased perks from the save.

## 0.2 — 2026-08-26

**PL:** Dodano kartę **Ekwipunek** i odczyt rekordów przedmiotów z `sav.dat`. Companion mógł pokazać saldo w eurodolarach i rozpoznać wybrane bronie oraz wszczepy po ich identyfikatorach. Samo znalezienie przedmiotu w zapisie nie potwierdzało jeszcze, że jest wyposażony.

**EN:** Added the **Inventory** tab and item-record parsing from `sav.dat`. Companion could show the player’s eurodollars and identify selected weapons and cyberware by item ID. Finding an item in a save did not yet establish that it was equipped.

## 0.1.1 — 2026-08-26

**PL:** Naprawiono pusty panel po uruchomieniu: nieprawidłowo zapisany apostrof w etykiecie JavaScript przerywał wykonywanie skryptu, zanim przeglądarka zdążyła pobrać stan z lokalnego API.

**EN:** Fixed a blank dashboard on startup. An incorrectly quoted apostrophe in a JavaScript label stopped the script before the browser could fetch state from the local API.

## 0.1 — 2026-08-26

**PL:** Pierwsze wydanie lokalnego panelu: odczyt metadanych i pliku `sav.dat`, podgląd zadań i stanu świata oraz eksport kontekstu rozgrywki. Zapisy gry były otwierane tylko do odczytu.

**EN:** First release of the local dashboard: read save metadata and `sav.dat`, inspect quests and world state, and export playthrough context. Game saves were opened read-only.
