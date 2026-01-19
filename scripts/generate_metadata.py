#!/usr/bin/env python3
"""Generate structured metadata for the Kramnik detected engine games."""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path
from typing import Dict, Iterable, List

TAG_LINE_RE = re.compile(r"^\[(\w+)\s+\"(.*)\"\]$")

# Core PGN tags we expect to find in the dataset.
PGN_TAGS: List[str] = [
    "Event",
    "Site",
    "Date",
    "Round",
    "White",
    "Black",
    "Result",
    "ECO",
    "WhiteElo",
    "BlackElo",
    "PlyCount",
    "EventDate",
    "EventType",
    "EventRounds",
    "SourceTitle",
    "Source",
    "SourceDate",
]


def parse_pgn_headers(pgn_path: Path) -> List[Dict[str, str]]:
    """Parse PGN headers from *pgn_path* into a list of dictionaries."""
    if not pgn_path.exists():
        raise FileNotFoundError(f"PGN file not found: {pgn_path}")

    games: List[Dict[str, str]] = []
    current: Dict[str, str] = {}

    with pgn_path.open(encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line or not line.startswith("["):
                continue
            match = TAG_LINE_RE.match(line)
            if not match:
                continue
            key, value = match.groups()
            if key == "Event" and current:
                games.append(current)
                current = {}
            current[key] = value

    if current:
        games.append(current)

    return games


def derive_record(index: int, headers: Dict[str, str]) -> Dict[str, str]:
    """Build a metadata record enriched with derived values."""
    record: Dict[str, str] = {"game_index": str(index)}

    for tag in PGN_TAGS:
        record[tag] = headers.get(tag, "")

    white = headers.get("White", "")
    black = headers.get("Black", "")
    white_elo = headers.get("WhiteElo", "")
    black_elo = headers.get("BlackElo", "")
    result = headers.get("Result", "")

    if white.lower().startswith("kramnik") or white == "Kramnik, V.":
        color = "White"
        opponent = black
        opponent_elo = black_elo
        kramnik_elo = white_elo
    elif black.lower().startswith("kramnik") or black == "Kramnik, V.":
        color = "Black"
        opponent = white
        opponent_elo = white_elo
        kramnik_elo = black_elo
    else:
        color = ""
        opponent = ""
        opponent_elo = ""
        kramnik_elo = white_elo or black_elo

    record["kramnik_color"] = color
    record["opponent"] = opponent
    record["opponentElo"] = opponent_elo
    record["kramnikElo"] = kramnik_elo

    if result == "1-0":
        outcome = "win" if color == "White" else "loss" if color == "Black" else "unknown"
    elif result == "0-1":
        outcome = "loss" if color == "White" else "win" if color == "Black" else "unknown"
    elif result in {"1/2-1/2", "1/2", "½-½"}:
        outcome = "draw"
    else:
        outcome = "unknown"

    record["kramnik_result"] = outcome

    date = headers.get("Date", "")
    if date:
        parts = date.split(".")
        record["year"] = parts[0]
        if len(parts) >= 3:
            record["month"] = parts[1]
            record["day"] = parts[2]
        elif len(parts) == 2:
            record["month"] = parts[1]
            record["day"] = ""
        else:
            record["month"] = ""
            record["day"] = ""
    else:
        record["year"] = record["month"] = record["day"] = ""

    return record


def write_csv(records: Iterable[Dict[str, str]], csv_path: Path) -> None:
    records = list(records)
    if not records:
        raise ValueError("No records to write")

    fieldnames = list(records[0].keys())
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)


def write_json(records: Iterable[Dict[str, str]], json_path: Path) -> None:
    with json_path.open("w", encoding="utf-8") as handle:
        json.dump(list(records), handle, indent=2, ensure_ascii=False)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--pgn",
        type=Path,
        default=Path("data/pgn/kramnik_detected_engine_games.pgn"),
        help="Path to the PGN archive",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/metadata"),
        help="Directory where metadata artifacts will be written",
    )
    parser.add_argument(
        "--csv-name",
        default="kramnik_detected_engine_games.csv",
        help="Filename for the CSV metadata output",
    )
    parser.add_argument(
        "--json-name",
        default="kramnik_detected_engine_games.json",
        help="Filename for the JSON metadata output",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    games = parse_pgn_headers(args.pgn)
    if not games:
        raise SystemExit(f"No games parsed from PGN: {args.pgn}")

    records = [derive_record(index, headers) for index, headers in enumerate(games, start=1)]

    args.output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = args.output_dir / args.csv_name
    json_path = args.output_dir / args.json_name

    write_csv(records, csv_path)
    write_json(records, json_path)

    print(f"Processed {len(records)} games from {args.pgn}.")
    print(f"CSV metadata written to {csv_path}.")
    print(f"JSON metadata written to {json_path}.")


if __name__ == "__main__":
    main()
