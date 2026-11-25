# Judging the Journey

An interactive look at how civil cases move through Czech district courts, and where they pile up. A model forecasts the chance that a case ends within a given time, from its history so far. Visitors try it on a real past case, picked at random or by court and case number, or on a case they describe, and see how well it does against simpler methods. They also follow the journey of a civil case from filing to a final decision (the routes cases take, how many take each one, and how long each step lasts), and compare one court's journey with the national one. A later tab shows the district courts on a map coloured by cases filed per year, backlog or typical time to a decision, and how close an estimate of a court's caseload, made from its published decisions alone (the German tank method), gets to the exact count.

The project makes no claims about why courts differ, and isn't legal advice.

**Status:** being rebuilt from scratch, as of November 2026. The demo on the site is still a stub. The plan, design decisions and milestones are in [docs/plan.md](docs/plan.md), which records how far the rebuild has got.

## Repository layout

| Path | What it is |
| --- | --- |
| [`demo/`](demo/) | The interactive demo for [mark-bugden.github.io](https://mark-bugden.github.io/), built with [demo-kit](https://github.com/Mark-Bugden/demo-kit). Its README explains how to run and build it. |
| [`src/soudai/`](src/soudai/) | Python: the scrapers, the parse steps and the analysis. |
| [`reference/`](reference/) | The hand-checked tables of district courts and event codes, and a record of the sources. Its README explains how they're made and checked. |
| [`tests/`](tests/) | Python tests. They never touch the network: they run on real responses saved in `tests/fixtures/`. |
| [`docs/`](docs/) | The plan, and notes for the write-up. |

The plan's "Repo layout" section lists what each part will hold as the rebuild goes on, including `data/derived/` (the parsed tables).

## Running the pipeline

The pipeline uses [uv](https://docs.astral.sh/uv/):

```sh
uv sync
uv run pytest
```

Each stage runs as `uv run soudai <stage>`, in this order. The stages from milestone 7 on aren't built yet. The plan gives each stage's inputs, outputs and rough cost.

| Stage | What it does | Milestone |
| --- | --- | --- |
| `courts`, `events` | Check the reference tables of district courts and event codes against infosoud. | 2 |
| `decisions` | List every published decision since 2020, and parse them into `data/derived/decisions.parquet`. | 3 |
| `senates`, `intake` | Find each court's senates, and count the cases each one registered per year. | 4 |
| `sample` | Fetch the timelines of a random sample of cases. | 5 |
| `official` | Compare the case counts with the Ministry of Justice's official statistics. | 6 |
| `analyse` | Compute the journeys: how many cases take each route, and how long each step takes. | 6 |
| `model`, `export` | Train and score the forecasting models, and write the demo's data. | 7–8 |
| `status` | Report each stage's progress. | 2 |

Every response is cached in `data/raw/cache.sqlite`, which is never committed, and every stage resumes where it stopped. The scrapers make at most three requests a second across the whole project, even when two run at once, and each run logs every request to `data/raw/logs/`.

## Data

- **Published decisions** come from the open data of [rozhodnuti.justice.cz](https://rozhodnuti.justice.cz/), the public database of anonymised Czech court decisions. The demo uses their case numbers, courts and dates. Full texts are never fetched, and the judge's name, which the open data includes, is dropped when the listing is parsed, so no derived table, export or demo holds it.
- **Case timelines** come from [infosoud.gov.cz](https://infosoud.gov.cz/), the courts' public case-tracking service. Its responses hold no names.

## Licence

The code is under the [MIT License](LICENSE).

## History

The project started as two repositories, one scraping court data and one training a PyTorch model to predict how long a case would take. In November 2026 it was rebuilt from scratch in this repository as an interactive demo. The old code remains in this repository's history and in [SOUDAI_data_scraping](https://github.com/Mark-Bugden/SOUDAI_data_scraping).
