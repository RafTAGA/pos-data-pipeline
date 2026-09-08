# POS Data Pipeline

Pulls sales, labor, purchasing, and weather data from a restaurant's connected
systems into a Neon Postgres database, on an automated schedule, to feed a
Power BI executive dashboard.

## How data flows

```
Toast API  ─┐
MarginEdge ─┼─▶ raw JSON  ─▶  pandas / CSV  ─▶  Neon Postgres  ─▶  SQL views  ─▶  Power BI
Open-Meteo ─┘
```

1) Each source is extracted independently through its own GitHub Actions workflow (API KEYS need to be safely stored as GitHiub secrets). Extrcated JSON files get saved in folder(s) for the respective year of extrcation.

2) Turn the JSON file(s) into strucutred CSVs using Pandas, saved in the same folder containing the respective JSON files.

3) Upsert into its own Neon table.

4) Create Views out of base Neon tables (`daily_sales_summary`, `hourly_sales_view`, `monthly_sales_summary`). These views are made to mimic TOAST's Statistics API reports using the standard API's bulk extraction. Owning the Statistcs API will require to update the JSON extraction and will make the views uneccessary.

4) Power BI reads data and updates visuals.


## Services used
| Purpose                                   | Service         | Links |
|---                                        |---              |---    |
| POS: sales, labor, menu items             | Toast           | [API docs](https://doc.toasttab.com/doc/devguide/apiOverview.html) |
| Food & consumable purchases               | MarginEdge      | [API docs](https://developer.marginedge.com/#/guide/introduction) |
| Weather (crosscheck sales vs. conditions) | Open-Meteo      | [API docs](https://open-meteo.com/) |
| Database                                  | Neon (Postgres) | [Pricing](https://neon.com/pricing) · [Login](https://neon.com/login) |
| Dashboard                                 | Power BI Pro    | [Pricing](https://www.microsoft.com/en-us/power-platform/products/power-bi/pricing) · [Login](https://app.powerbi.com/) |

## Repo layout
- **`modules/`** 
  - `general_data_processing.py` resuable helper functions for processing constant input or data (e.g., Dates to extract given start and end tuples with year, month, day).
  - one `api_*.py` per data source (performs raw HTTP calls).
  - one `json_processing_*.py` per source (JSON → DataFrame).
  - `db_neon.py` (Neon load helpers).
  - `schemas.py` (column/type definitions shared by every table).
  
- **`scripts/`**  Python scripts that GitHub Actions calls using the YML files. These use functions from **`modules/`** to store the JSON and CSV files into artifact output directories.
  - `run_*_extraction_api.py` (hits the respective API, saves JSON). 
  - `process_*_to_df.py` (JSON to CSV).
  - `load_*_to_neon.py` (CSV → Neon) per source.

- **`local_drive_runs/`** Jupyter Notebooks that use functions from modules to recreate the pipeline steps implemented in **`scripts/`**.

- **`.github/workflows/`** — the three scheduled pipelines that run using Github Actions.
  - `toast_orders.yml` (catalogs, labor, refunds, orders). 
  - `marginedge_extraction.yml` (catalogs, purchaise orders, purchaised item information ).
  - `weather_extraction.yml`(weather data).

## Automation

All three workflows can:
- run automatically: **PLACEHOLDER: every Tuesday at 3am Central** (`0 8 * * 2` UTC) via GitHub Actions' `schedule` trigger.
  - resumes from the day after the most recent date already loaded into the relevant Neon table, through today. 
  - If a run fails or gets skipped, the next run just picks up from wherever Neon actually left off.
- run manually from the **Actions** tab (`Run workflow`) with an optional explicit date range.
  - **No date range given**: resumes from the day after the most recent date already loaded into the relevant Neon table, through today. 
  - If a run fails or gets skipped, the next run just picks up from wherever Neon actually left off.
  - **Date range given**: extracts exactly that window (used for backfills or targeted re-runs).

**Scheduled triggers only fire off the workflow file as it exists on `main` changes on a feature branch won't run until merged.**


## Required secrets

Set these under:
```
Settings ─▶ Security and quality ─▶ Secrets and variables ─▶ New repository secret / ✏️ / 🗑️
``` 

| Secret                                                                              | Used by |
|---                                                                                  |---       |
| `TOAST_HOSTNAME`, `TOAST_CLIENT_ID`, `TOAST_CLIENT_SECRET`, `TOAST_RESTAURANT_GUID` | Toast extraction |
| `MARGINEDGE_API_KEY`, `MARGINEDGE_RESTAURANT_UNIT_ID`                               | MarginEdge extraction |
| `NEON_CONNECTION_STRING`                                                            | All Neon loads |



## Running locally

You can run in Google Drive's Colab the Jupyter Notebooks provided as an introduction to the wrokflow and for a Backlog extraction for loading into Dataset.
```bash
pip install -r requirements.txt
```

## Known gotchas

- **DST drift**: the cron schedule is fixed in UTC, so the "3am Central" run
  time shifts by an hour between CST and CDT.
- **GitHub auto-disables schedules** after 60 days with no repository
  activity (commits) — check the Actions tab and re-enable if this repo goes
  quiet for a while.
- **Power BI needs its own stored Neon credentials** in the Service (under
  the dataset's *Data source credentials*) — separate from whatever's saved
  in Power BI Desktop.
