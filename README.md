# Judging the Journey

An interactive look at how civil cases move through Czech district courts, and where they pile up. Visitors follow the journey of a civil case from filing to a final decision (the routes cases take, how many take each one, and how long each step lasts), compare one court's journey with the national one, and see the district courts on a map coloured by cases filed per year, backlog or typical time to a decision. A side panel shows how close an estimate of a court's caseload, made from its published decisions alone (the German tank method), gets to the exact count.

The project is descriptive. It makes no predictions about individual cases, makes no claims about why courts differ, and isn't legal advice.

**Status:** being rebuilt from scratch, as of November 2026. The demo on the site is still a stub. The plan, design decisions and milestones are in [docs/plan.md](docs/plan.md), which records how far the rebuild has got.

## Repository layout

| Path | What it is |
| --- | --- |
| [`demo/`](demo/) | The interactive demo for [mark-bugden.github.io](https://mark-bugden.github.io/), built with [demo-kit](https://github.com/Mark-Bugden/demo-kit). Its README explains how to run and build it. |
| [`src/soudai/`](src/soudai/) | Python: the scrapers, the parse steps and the analysis. |
| [`tests/`](tests/) | Python tests. They never touch the network. |
| [`docs/`](docs/) | The plan. |

The plan's "Repo layout" section lists what each part will hold as the rebuild goes on, including `reference/` (hand-checked tables) and `data/derived/` (the parsed tables).

## Running the pipeline

The pipeline uses [uv](https://docs.astral.sh/uv/):

```sh
uv sync
uv run pytest
```

Each stage will run as `uv run soudai <stage>`, in this order. The plan gives each stage's inputs, outputs and rough cost.

| Stage | What it does | Milestone |
| --- | --- | --- |
| `courts`, `events` | Build the reference tables of district courts and event codes. | 2 |
| `decisions` | List every published decision since 2020. | 3 |
| `senates`, `intake` | Find each court's senates, and count the cases each one filed per year. | 4 |
| `sample` | Fetch the timelines of a random sample of cases. | 5 |
| `analyse`, `export` | Compute the journeys, waits, estimates and backlog, and write the demo's data. | 6–7 |
| `status` | Report each stage's progress. | 2 |

Every response is cached in `data/raw/cache.sqlite`, which is never committed, and every stage resumes where it stopped. The scrapers make at most one request a second across the whole project.

## Data

- **Published decisions** come from the open data of [rozhodnuti.justice.cz](https://rozhodnuti.justice.cz/), the public database of anonymised Czech court decisions. The demo uses their case numbers, courts and dates. Full texts are never fetched, and the judge's name, which the open data includes, is dropped when the listing is parsed, so no derived table, export or demo holds it.
- **Case timelines** come from [infosoud.gov.cz](https://infosoud.gov.cz/), the courts' public case-tracking service. Its responses hold no names.

## Licence

The code is under the [MIT License](LICENSE).

## History

The project started as two repositories, one scraping court data and one training a PyTorch model to predict how long a case would take. In November 2026 it was rebuilt from scratch in this repository as a descriptive, interactive demo. The old code remains in this repository's history and in [SOUDAI_data_scraping](https://github.com/Mark-Bugden/SOUDAI_data_scraping).
