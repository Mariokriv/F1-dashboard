# F1-dashboard

Historical F1 comparison dashboard backed by an Ergast-compatible API.

The downloader uses [Jolpica F1](https://api.jolpi.ca/ergast/f1/), the maintained
Ergast-compatible source, and stores comparable race, qualifying, driver, team,
circuit, and result data in SQLite.

```powershell
cd F1_database_project
python src\pipeline.py --season 2023 --season 2024 --database data\f1.db
```

The schema keeps seasons separate while using stable driver and constructor IDs,
so comparisons across eras can be made with SQL without relying on display names.
