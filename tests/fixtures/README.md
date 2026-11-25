# Test fixtures

Real responses, saved from the cache (`data/raw/cache.sqlite`) on 2026-11-22, so the tests never touch the network. Each JSON file records the request (`method`, `url`, `body`), the `status` and `content_type`, and the parsed `response`.

| File | What it is |
| --- | --- |
| `infosoud/case_found.json` | 15 C 384/2022 at Okresní soud Náchod: filed, heard, decided, legally final and closed. |
| `infosoud/case_not_found.json` | 15 C 9999/2022 at Náchod: the API's not-found 400, `RIZENI_0000`. |
| `infosoud/case_open.json` | 15 C 300/2026: open, with only its filing. |
| `infosoud/case_cancelled_hearing.json` | 15 C 1/2022: a hearing scheduled and cancelled (`zruseno`). |
| `infosoud/case_suspended.json` | 15 C 4/2022: suspended and resumed. |
| `infosoud/case_disposed.json`, `case_legally_final.json` | 15 C 236/2026 and 15 C 200/2026: the two statuses between decision and closing. |
| `infosoud/regional_courts.json`, `district_courts_KSVYCHK.json`, `env.json` | The court lists, and the backend version. |
| `infosoud/labels_chunk.js` | From the app's JS bundle (`chunk-KZJVN2ZT.js`), cut to its resource bundle: the event labels and error messages. |
| `rozhodnuti/years.json`, `months_2023.json`, `days_2023_03.json` | The year, month and day indexes. |
| `rozhodnuti/day_2023_03_15_page_0.json` | The first page of 2023-03-15's decisions, with every `autor` (the judge's name) replaced by `REDACTED`. |
| `infodata/results_2022.html` | InfoData's search results for S_AS_40 in 2022 (saved 2026-11-25), cut to the results table. |
| `infodata/s_as_40_2022.xml.gz` | The 2022 S_AS_40 report itself, as InfoData's XML spreadsheet, gzipped. |
