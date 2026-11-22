# Reference tables

The hand-checked tables the pipeline joins everything else to. The endpoints they come from, the date they were checked and infosoud's backend version at the time are in [`sources.json`](sources.json).

| File | One row per | Columns |
| --- | --- | --- |
| [`courts.csv`](courts.csv) | district-level court (86) | infosoud's code, its regional court's code, infosoud's name, the names rozhodnuti uses, the area it serves |
| [`events.csv`](events.csv) | event code (28) or case status (4) | kind (`event` or `status`), code, Czech label, tooltip and description from infosoud's app, English gloss |

## courts.csv

The courts in scope are the district-level courts: 75 okresní soudy, Prague's 10 obvodní soudy and Městský soud v Brně, which acts as Brno's district court. That's every court infosoud lists under a regional court (`GET organizace/podrizene/lov`) on 2026-11-22. The two high courts list none, and Městský soud v Praze is itself a regional-level court, so it's out of scope.

- **`code`** and **`regional_code`** are what infosoud's case lookup takes as `okresniSoud` and `druhOrganizace`, e.g. `OSVYCNA` and `KSVYCHK` for Náchod.
- **`name`** is infosoud's: "Okresní soud Náchod".
- **`rozhodnuti_names`** are the names rozhodnuti's open data gives in `soud`, separated by `; `. They're in the locative ("Okresní soud v Náchodě"), so they can't be derived from infosoud's. Three courts have a branch with a name of its own: Bruntál (Krnov), Karviná (Havířov) and Vsetín (Valašské Meziřičí). They come from the old project's court map, `references/court_map.yaml` in [SOUDAI_data_scraping](https://github.com/Mark-Bugden/SOUDAI_data_scraping), at the commit in `sources.json`.
- **`area`** names what the court serves: an okres, or for Prague's courts, a Prague district (`Praha 1` to `Praha 10`). Městský soud v Brně serves Brno-město, and Okresní soud v Ostravě serves Ostrava-město. infosoud writes three okres names with a capital after the hyphen ("Plzeň-Město", "Praha-Východ", "Praha-Západ"), and `area` uses their official spelling. The exact boundaries of the court districts are a question for the map (see "Open questions" in the plan).

`uv run soudai courts` fetches infosoud's lists again and reports any court that's new, gone or changed. `--write` writes the table afresh, from infosoud and the court map.

**Checked by hand on 2026-11-22:** the 86 codes and names against infosoud's lists, and the areas against the 76 okresy. Every rozhodnuti name maps to exactly one court. In six whole days of published decisions (3,403 decisions from 2021 to 2026), every district-level court name maps to a court, and 85 of the 86 courts appear. The one missing is Hodonín, so its rozhodnuti name ("Okresní soud v Hodoníně") is still to be confirmed by the full listing in milestone 3.

## events.csv

- **Events** are the codes in a case's timeline (`udalosti[].udalost`). The Czech label, tooltip and description come from infosoud's JS bundle. The bundle has two sets: one for the Supreme Court (`ns`), where `ZAHAJ_RIZ` reads "Došlo Nejvyššímu soudu", and one for the other courts. The table uses the second. Tooltips lose their HTML tags.
- **Statuses** are the strings the API returns as a case's `stav`. The bundle has no labels for them, so `code` and `label_cs` are the string itself. All four were seen in 54 cases at Okresní soud Náchod, senate 15, filed in 2022, 2025 and 2026.
- **`gloss_en`** is written by hand, short enough for the demo to show. Mark checks the glosses.

`uv run soudai events` finds the chunk of the current bundle that holds the labels, refreshes the Czech columns, and keeps the glosses and the status rows. It reports any code that's new (with no gloss yet) or gone.

Two codes, `PR_VEC_NS` and `VR_SP_NS`, carry the Supreme Court's suffix but are in both sets. Neither has turned up in a district-court timeline yet.
