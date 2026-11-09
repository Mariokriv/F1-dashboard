"""Download historical F1 data into a local SQLite database."""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path
from typing import Iterable

from api import F1Api


SCHEMA = """
CREATE TABLE IF NOT EXISTS seasons (season TEXT PRIMARY KEY);
CREATE TABLE IF NOT EXISTS circuits (
    circuit_id TEXT PRIMARY KEY, name TEXT NOT NULL, locality TEXT, country TEXT
);
CREATE TABLE IF NOT EXISTS drivers (
    driver_id TEXT PRIMARY KEY, code TEXT, given_name TEXT, family_name TEXT,
    date_of_birth TEXT, nationality TEXT, url TEXT
);
CREATE TABLE IF NOT EXISTS constructors (
    constructor_id TEXT PRIMARY KEY, name TEXT NOT NULL, nationality TEXT, url TEXT
);
CREATE TABLE IF NOT EXISTS races (
    season TEXT NOT NULL, round INTEGER NOT NULL, race_name TEXT NOT NULL,
    circuit_id TEXT, date TEXT, time TEXT, url TEXT,
    PRIMARY KEY (season, round), FOREIGN KEY (circuit_id) REFERENCES circuits(circuit_id)
);
CREATE TABLE IF NOT EXISTS results (
    season TEXT NOT NULL, round INTEGER NOT NULL, driver_id TEXT NOT NULL,
    constructor_id TEXT, number TEXT, grid INTEGER, position INTEGER,
    points REAL, laps INTEGER, status TEXT, fastest_lap INTEGER,
    fastest_lap_time TEXT, fastest_lap_speed REAL,
    PRIMARY KEY (season, round, driver_id)
);
CREATE TABLE IF NOT EXISTS qualifying (
    season TEXT NOT NULL, round INTEGER NOT NULL, driver_id TEXT NOT NULL,
    constructor_id TEXT, position INTEGER, q1 TEXT, q2 TEXT, q3 TEXT,
    PRIMARY KEY (season, round, driver_id)
);
CREATE INDEX IF NOT EXISTS idx_results_driver ON results(driver_id);
CREATE INDEX IF NOT EXISTS idx_results_constructor ON results(constructor_id);
"""


def _integer(value: object) -> int | None:
    try:
        return int(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _float(value: object) -> float | None:
    try:
        return float(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _insert_reference_data(connection: sqlite3.Connection, races: Iterable[dict]) -> None:
    for race in races:
        circuit = race.get("Circuit", {})
        location = circuit.get("Location", {})
        if circuit.get("circuitId") and circuit.get("circuitName"):
            connection.execute(
                "INSERT OR REPLACE INTO circuits VALUES (?, ?, ?, ?)",
                (circuit.get("circuitId"), circuit.get("circuitName"), location.get("locality"), location.get("country")),
            )
        for driver in race.get("_drivers", []):
            if driver.get("driverId"):
                connection.execute(
                    "INSERT OR REPLACE INTO drivers VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (driver.get("driverId"), driver.get("code"), driver.get("givenName"),
                     driver.get("familyName"), driver.get("dateOfBirth"), driver.get("nationality"), driver.get("url")),
                )
        for constructor in race.get("_constructors", []):
            if constructor.get("constructorId") and constructor.get("name"):
                connection.execute(
                    "INSERT OR REPLACE INTO constructors VALUES (?, ?, ?, ?)",
                    (constructor.get("constructorId"), constructor.get("name"),
                     constructor.get("nationality"), constructor.get("url")),
                )


def download_season(api: F1Api, connection: sqlite3.Connection, season: str) -> int:
    races = api.get_all(season + "/races")
    stored_results = 0
    for race in races:
        round_number = _integer(race.get("round"))
        if round_number is None:
            continue
        circuit = race.get("Circuit", {})
        connection.execute(
            "INSERT OR REPLACE INTO seasons VALUES (?)", (season,)
        )
        connection.execute(
            "INSERT OR REPLACE INTO races VALUES (?, ?, ?, ?, ?, ?, ?)",
            (season, round_number, race.get("raceName"), circuit.get("circuitId"),
             race.get("date"), race.get("time"), race.get("url")),
        )
        results = api.get_all(f"{season}/{round_number}/results")
        qualifying = api.get_all(f"{season}/{round_number}/qualifying")
        references: list[dict] = [race]
        for row in results + qualifying:
            references.append(row)
            references[-1]["_drivers"] = [row.get("Driver", {})]
            references[-1]["_constructors"] = [row.get("Constructor", {})]
        _insert_reference_data(connection, references)
        for result in results:
            fastest = result.get("FastestLap", {})
            connection.execute(
                "INSERT OR REPLACE INTO results VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (season, round_number, result.get("Driver", {}).get("driverId"),
                 result.get("Constructor", {}).get("constructorId"), result.get("number"),
                 _integer(result.get("grid")), _integer(result.get("position")),
                 _float(result.get("points")), _integer(result.get("laps")), result.get("status"),
                 _integer(fastest.get("lap")), fastest.get("Time", {}).get("time"),
                 _float(fastest.get("AverageSpeed", {}).get("speed"))),
            )
            stored_results += 1
        for row in qualifying:
            connection.execute(
                "INSERT OR REPLACE INTO qualifying VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (season, round_number, row.get("Driver", {}).get("driverId"),
                 row.get("Constructor", {}).get("constructorId"), _integer(row.get("position")),
                 row.get("Q1"), row.get("Q2"), row.get("Q3")),
            )
    connection.commit()
    return stored_results


def main() -> None:
    parser = argparse.ArgumentParser(description="Download Ergast-compatible F1 data")
    parser.add_argument("--season", action="append", required=True, help="Season year; repeat for multiple seasons")
    parser.add_argument("--database", default="f1.db", help="SQLite output path")
    args = parser.parse_args()
    Path(args.database).parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(args.database) as connection:
        connection.executescript(SCHEMA)
        api = F1Api()
        for season in args.season:
            print(f"Downloading {season}...")
            print(f"Stored {download_season(api, connection, season)} race results.")


if __name__ == "__main__":
    main()