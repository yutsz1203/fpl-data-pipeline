import csv
import os
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

COLUMNS = {"gameweek", "team_id", "opponent_id", "home", "expected_gf", "expected_ga"}


@dataclass
class Forecast:
    note: str
    fixtures: dict[tuple[int, int, int], tuple[float, float]] = field(
        default_factory=dict
    )
    first_gameweek: int | None = None
    last_gameweek: int | None = None
    updated_at: datetime | None = None


def load_forecast() -> Forecast:
    path = os.environ.get("FORECAST_CSV")
    if not path:
        return Forecast("No forecast is set up. Showing FPL difficulty only.")
    file = Path(path)
    if not file.is_file():
        return Forecast(
            "The forecast file does not exist yet. Showing FPL difficulty only."
        )
    with file.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if not COLUMNS <= set(reader.fieldnames or ()):
            return Forecast(
                "The forecast file has the wrong columns. Showing FPL difficulty only."
            )
        fixtures = {
            (int(row["gameweek"]), int(row["team_id"]), int(row["opponent_id"])): (
                float(row["expected_gf"]),
                float(row["expected_ga"]),
            )
            for row in reader
        }
    if not fixtures:
        return Forecast("The forecast file is empty. Showing FPL difficulty only.")
    gameweeks = [gameweek for gameweek, _, _ in fixtures]
    return Forecast(
        note="",
        fixtures=fixtures,
        first_gameweek=min(gameweeks),
        last_gameweek=max(gameweeks),
        updated_at=datetime.fromtimestamp(file.stat().st_mtime, UTC),
    )
