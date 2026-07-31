from __future__ import annotations

import csv
import json
import sqlite3
from pathlib import Path

from .models import DomainResult


class ResultStore:
    def __init__(self, directory: Path) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        self.directory = directory
        self.connection = sqlite3.connect(directory / "results.sqlite3")
        self.connection.execute("CREATE TABLE IF NOT EXISTS results (domain_ascii TEXT PRIMARY KEY, payload TEXT NOT NULL)")
        self.connection.commit()
        self.jsonl = directory / "results.jsonl"

    def get(self, domain_ascii: str) -> DomainResult | None:
        row = self.connection.execute("SELECT payload FROM results WHERE domain_ascii = ?", (domain_ascii,)).fetchone()
        return DomainResult.model_validate_json(row[0]) if row else None

    def put(self, result: DomainResult) -> None:
        payload = result.model_dump_json()
        self.connection.execute("INSERT INTO results(domain_ascii, payload) VALUES(?, ?) ON CONFLICT(domain_ascii) DO UPDATE SET payload=excluded.payload", (result.domain_ascii, payload))
        self.connection.commit()
        with self.jsonl.open("a", encoding="utf-8") as file:
            file.write(payload + "\n")

    def all(self) -> list[DomainResult]:
        return [DomainResult.model_validate_json(row[0]) for row in self.connection.execute("SELECT payload FROM results ORDER BY domain_ascii")]

    def export(self) -> tuple[Path, Path]:
        results = self.all()
        json_path = self.directory / "results.json"
        json_path.write_text(json.dumps([item.as_json_dict() for item in results], ensure_ascii=False, indent=2), encoding="utf-8")
        csv_path = self.directory / "results.csv"
        fields = list(DomainResult.model_fields)
        with csv_path.open("w", encoding="utf-8-sig", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=fields)
            writer.writeheader()
            for item in results:
                row = item.model_dump(mode="json")
                for key, value in row.items():
                    if isinstance(value, (list, dict)):
                        row[key] = json.dumps(value, ensure_ascii=False)
                writer.writerow(row)
        return csv_path, json_path

    def close(self) -> None:
        self.connection.close()
