# CP2077 Companion 0.8.3

**Patch 2.5 — player guide** — Finish The Heist and two gigs for Wakako, then wait for her message. Her new job offers five pieces of King’s gear. Look in the Cool tree for the new dual-wield perk. It works with Power pistols and revolvers. Finish The Heist and reach Street Cred 15 to unlock Richard Night’s tour. A separate job starts when you scan any of the 12 new Minor Arcana cards. This offline guide does not check your save for these requirements.

[Polski](README.md) · [Changelog](CHANGELOG.md) · [Guide sources](GUIDE_SOURCES.md) · [Third-party references](THIRD_PARTY.md) · [Release verification](RELEASE_TESTS.md)

Companion reads local Cyberpunk 2077 saves and displays the results in your browser. Python 3.10 or newer is enough to run it, inspect your character and use either language. It requires no pip packages, account or internet connection. It never writes to the game's save files.

## Offline and online

**There is one version of Companion.** The panel runs on your computer at `127.0.0.1`. Connecting your computer to the internet does not change how the app starts.

| How you start Companion on Windows | Does Companion connect to the internet? | What you see in the panel |
|---|---|---|
| `.\run.ps1 -Port 9977`, without the optional catalog | No, even on first launch. | Character stats, equipment, stash, guides and exports work. Items outside the built-in list may show only an identifier or hash. |
| `.\run.ps1 -UpdateCatalog -Port 9977` | Yes, at your request: it downloads one public TSV from the NightCity Console project on GitHub, verifies its SHA-256 and then starts the local panel. | More items in your save have a readable name and category. No save, screenshot or export is uploaded. |
| `.\run.ps1 -Port 9977`, with the verified catalog already on disk | No. It reads `data/cet_catalog.tsv` from disk without checking for a newer version online. | The same additional names and categories are available after you disconnect. |

For example, the built-in catalog has no name for the standard pistol `Items.Preset_Lexington_Default`. With the optional TSV, Companion labels it **M-10AF LEXINGTON**. The catalog supplies the label; ownership still comes from an inventory or stash record in the selected save.

In 0.7.1, `run.ps1` tried to download the catalog by default when it was missing. From 0.8.0, you can work offline without passing `-NoCatalogDownload`. Opening a guide source or map is separate: only when you click its link does **your browser** open the external site.

## Quick start

Extract the **entire ZIP** into its own directory on a local drive and open a terminal there. On Windows:

```powershell
.\run.ps1 -Port 9977
```

From 0.8.1, both PowerShell scripts select the first `py` application on `PATH`, or the first `python` if there is no `py`. In 0.8.0 an error listing several `py.exe` paths as one command was a launcher bug unrelated to the port. To work around it or run the panel without changing your script execution policy:

```powershell
py -3 .\cp2077_companion.py --port 9977
```

On Linux, pass the local parent directory containing folders such as `ManualSave-660`:

```bash
python3 cp2077_companion.py --save-root "/path/to/local/saves" --port 9977
```

The program opens the [local panel](http://127.0.0.1:9977/). The default port is `8765` when no port is specified. Pass `--no-open` (PowerShell launcher: `-NoOpen`) to skip launching a browser and press Ctrl+C to stop the server. The default Windows save location is `%USERPROFILE%\Saved Games\CD Projekt Red\Cyberpunk 2077`. To use another directory, pass `-SaveRoot` in PowerShell or `--save-root` in Python. Administrator privileges are not required.

## What stays on your computer and what uses the internet

| Action | Data and destination | What leaves your computer |
|---|---|---|
| Start, select or refresh a save | `metadata.*.json`, `sav.dat` and, when displayed, the local `screenshot.png`. The browser obtains results, scripts, styles and translations from the server on this computer. | Nothing. Requests to `127.0.0.1` do not go out to the internet. |
| Guides, character, equipment and iconic weapons | Bundled data; a verified TSV on disk can supply additional item names. | Nothing. No analytics, remote fonts, CDN, translation API or AI requests. |
| Language and encounter checklist | Your browser remembers the language in a `companion_lang` cookie. Marks go into `data/hidden_encounters.sqlite3`. | Nothing. |
| Explicit export | A file downloaded from the local panel or a directory you select with `--once`. Exports can contain slot names, equipment and story progress. | Nothing automatically. If you share an export, its recipient can read the contents. |
| **Optional catalog download** | An HTTPS GET downloads a public list of items from `raw.githubusercontent.com` to `data/cet_catalog.tsv`. | The provider sees standard connection data including your public IP, request time, URL and HTTP headers. The program does not attach a save, screenshot, character ID, filesystem path or export. |
| Click a guide or map source | Your browser opens the site identified on that card, such as Cyberpunk Wiki, EIP or MapGenie. | Only then does the browser contact the selected site. Companion attaches no save data or Referer header. |

**Exact optional file:** [NightCity Console — runtime/cet_catalog.tsv](https://raw.githubusercontent.com/ysrdevs/nightcity-console-mac/f256a327d533f5058465c7f64e6f4773d0330535/runtime/cet_catalog.tsv). [Upstream repository](https://github.com/ysrdevs/nightcity-console-mac/tree/f256a327d533f5058465c7f64e6f4773d0330535). Each of its 7,667 records contains a TweakDB item identifier, display name, subcategory and category. Of these, the local resolver accepts 7,556 rows with Items., Ammo. and TEST. prefixes; it skips the rest, including 71 Keycards entries. A guide mentioning a storeroom key does not mean the key was detected in the selected save. This release accepts 514,951 bytes with SHA-256 `e69fbab9fcad414980f3ee6e898043912ba80dc2925a7d94f363c4e9bd1dcbf7`. The URL names a specific revision. The downloader does not track the upstream branch or execute the downloaded data.

To download the catalog without starting the panel:

```powershell
py -3 .\cp2077_companion.py --update-catalog
```

Equivalent: `.\update-item-catalog.ps1`. Running `.\run.ps1 -UpdateCatalog -Port 9977` verifies the download before starting the panel. A network error, redirect or mismatched hash leaves any previous copy untouched. Start without the update flag to work offline. A missing or unverified catalog does not block save analysis; some item labels will use a built-in name or an identifier.

## Using the panel

Select **Polski** or **English** at the top. Changing language keeps your active tab and save selection. Game identifiers, proper names, raw save values and some upstream item names keep their original spelling.

Automatic selection shows the most recent readable save. Manual selection identifies the **slot directory**, so two restored copies with the same character name or in-game label remain distinct. The panel covers character development, cyberware, active equipment slots, inventory, stash, quickhacks, iconic items and story decisions. The guides distinguish owning an item from meeting its acquisition conditions: an item missing from the scanned containers is not proof it was missed permanently. For example, the **Gris-Gris** card describes the key from Mr. Hands’ `Treating Symptoms` gig and the later opportunity to access Slider’s stash during `The Damned`. A story flag or player report does not prove that an item is in the selected save.

The hidden encounter checklist is separate for each playthrough identified by `playthroughID`. If the game does not expose that ID, marks apply only to the selected slot directory. The SQLite database is created when you write a mark or explicitly import one. Browser tabs connected to one process share the active save selection.

## Find a save for Firestarter

1. Select a save from the playthrough you want to search. Open **Choices and consequences → Find a save for the Firestarter decision** and click **Search this playthrough**.
2. Select **Manual** for manual slots only. This also recalculates the summary. The latest candidate has an active `q304` and no recognized later-stage marker. Beside it is the first later slot with positive route evidence. Without a candidate, the finder shows the earliest dated route evidence it found. Use the name and stage filters to narrow the table.
3. Compare the date and play time in the game’s **Load Game** menu. Check in the game whether the stadium dialogue is still ahead. Keep a separate manual save before connecting to the matrix if you can. Companion neither creates backups nor loads the slot in the game.

The finder currently supports the **Songbird/Reed decision in Firestarter**. On request it reads local `metadata.*.json` files, even beyond the main list limit (500 by default). It requires a matching `playthroughID` and never groups unknown profiles. It checks that `sav.dat` exists and is nonempty without decoding its contents for the search. Undated slots remain in the table but are not ranked; ties are not broken arbitrarily. A replay after loading an earlier save can leave evidence of both routes.

A positive `q304_songbirds_path` flag or recognized progress in `q306` indicates Songbird’s route; progress in `q305` indicates Reed’s. Completing `q304`, Hansen’s death or a zero-valued flag alone cannot identify the choice. Expand the guide card for the consequences of each route. The search works offline.

## Export and upgrade from 0.7.1

Opening the panel **does not produce an export**. Its download buttons save the selected file on request. To export the latest selected save without starting the panel:

```powershell
py -3 .\cp2077_companion.py --once --export-dir .\exports
```

The program writes `state.json`, `assistant-context.json` and `assistant-context.md` together into a new subdirectory named with UTC time and a unique suffix. Previous exports are preserved. Choose an export destination outside the game's save directory. An incomplete or undecodable selected save does not publish a new snapshot.

1. Stop the previous version and extract 0.8.3 to a new folder. Do not replace the new `data` directory with the old one.
2. To keep checklist marks from 0.7.1, copy just `data/hidden_encounters_status.json` into the new `data` directory. Select the intended character's save and use the import button in **Hidden Encounters**. The old format did not distinguish characters: you decide which character gets those marks. Repeated imports preserve existing marks and do not modify the old file.
3. You can copy the existing `cet_catalog.tsv` instead of downloading it again. Only a matching hash is used. When moving this version again, keep `data/hidden_encounters.sqlite3` after stopping the process.

## Security limits and development

The server accepts only loopback bindings and validates the Host header and the origin of state changes. A write from the panel also needs a random token for the current process. Do not expose the service through a proxy or tunnel. A process running as your OS user can still read your files. For input the program rejects symlinks, Windows reparse points, UNC paths, mapped Windows network drives and recognized Linux network filesystems. It cannot control OneDrive, Steam or browser sync; choose a normal local folder if you do not want OS-level synchronization.

Read limits: 64 MiB for `sav.dat`, 2 MiB per decompressed LZ4 block, 128 MiB total decompressed data, 1 MiB for metadata and 16 MiB for a screenshot. If a previously decoded slot becomes temporarily unreadable, the panel labels its last good view; exports and checklist writes are suspended until the next successful read. A modded save above these limits may not load. An unresolved name or an unconfirmed story outcome is left as such.

Panel strings and content translations live in `locales/ui.{pl,en}.json` and `locales/content.{pl,en}.json`. After editing the templates in `ui-src` or a UI label, run `python tools/build_ui.py`. Use `python tools/build_ui.py --check` in CI. Both panels are prebuilt in the ZIP; users do not install gettext or compile PO/MO files.
