"""Kaggle Chess Cheating Dataset adapter.

Dataset: "Spotting Cheaters: Chess cheating dataset"
URL: https://www.kaggle.com/datasets/...

This dataset contains 48,000 games played between bots where one side
may be using a strong chess engine (Stockfish or Maia). Each game has
a 'cheater' column indicating which side cheated.
"""

from __future__ import annotations

import csv
import json
import logging
from pathlib import Path
from typing import AsyncIterator, Optional, Dict, Any
from datetime import datetime

from .base import SyntheticAdapter, RawGame
from ..models import CheaterLabel

LOGGER = logging.getLogger(__name__)


class KaggleAdapter(SyntheticAdapter):
    """Adapter for the Kaggle Chess Cheating Dataset."""
    
    source_name = "kaggle"
    
    def __init__(self, data_path: str):
        """Initialize with path to the Kaggle dataset.
        
        Args:
            data_path: Path to the extracted Kaggle dataset directory
                      Should contain games.csv or games.json
        """
        super().__init__(data_path)
        self.data_dir = Path(data_path)
    
    async def fetch_games(self, limit: int = 1000, **kwargs) -> AsyncIterator[RawGame]:
        """Fetch games from the Kaggle dataset.
        
        Supports both CSV and JSON formats.
        """
        # Try JSON first (more flexible)
        json_file = self.data_dir / "games.json"
        csv_file = self.data_dir / "games.csv"
        
        if json_file.exists():
            async for game in self._parse_json(json_file, limit):
                yield game
        elif csv_file.exists():
            async for game in self._parse_csv(csv_file, limit):
                yield game
        else:
            LOGGER.error(f"No games.json or games.csv found in {self.data_dir}")
            return
    
    async def _parse_json(self, path: Path, limit: int) -> AsyncIterator[RawGame]:
        """Parse games from JSON format."""
        count = 0
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                if count >= limit:
                    break
                
                try:
                    data = json.loads(line)
                    yield self._to_raw_game(data)
                    count += 1
                except json.JSONDecodeError as e:
                    LOGGER.warning(f"Failed to parse JSON line: {e}")
                    continue
    
    async def _parse_csv(self, path: Path, limit: int) -> AsyncIterator[RawGame]:
        """Parse games from CSV format."""
        count = 0
        with open(path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if count >= limit:
                    break
                
                yield self._to_raw_game(row)
                count += 1
    
    def _to_raw_game(self, data: Dict[str, Any]) -> RawGame:
        """Convert Kaggle row to RawGame."""
        return RawGame(
            source_id=data.get("game_id", str(hash(data.get("pgn", "")))),
            pgn=data.get("pgn", ""),
            white_username=data.get("white", "bot_white"),
            black_username=data.get("black", "bot_black"),
            white_rating=self._safe_int(data.get("white_elo")),
            black_rating=self._safe_int(data.get("black_elo")),
            time_control=data.get("time_control"),
            time_class=data.get("time_class", "blitz"),
            game_date=self._parse_date(data.get("date")),
            result=data.get("result"),
            metadata={
                "cheater": data.get("cheater"),  # 'white', 'black', or 'none'
                "engine": data.get("engine"),    # Engine used for cheating
            }
        )
    
    def get_cheater_label(self, raw: RawGame) -> CheaterLabel:
        """Get label from Kaggle dataset's 'cheater' column."""
        cheater = raw.metadata.get("cheater", "none") if raw.metadata else "none"
        engine = raw.metadata.get("engine", "stockfish") if raw.metadata else "stockfish"
        
        # Normalize cheater value
        if cheater in ("white", "black"):
            side = cheater
            cheater_type = "engine_full"  # Kaggle dataset simulates full engine use
        elif cheater == "both":
            side = "both"
            cheater_type = "engine_full"
        else:
            side = "none"
            cheater_type = "unknown"
        
        return CheaterLabel(
            side=side,
            cheater_type=cheater_type,
            confirmed=True,  # Kaggle data is synthetically labeled
        )
    
    @staticmethod
    def _safe_int(value) -> Optional[int]:
        """Safely convert to int."""
        if value is None:
            return None
        try:
            return int(value)
        except (ValueError, TypeError):
            return None
    
    @staticmethod
    def _parse_date(value) -> Optional[datetime]:
        """Parse date string to datetime."""
        if not value:
            return None
        
        for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d/%m/%Y"):
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                continue
        return None


async def download_kaggle_dataset(output_dir: str, dataset_slug: str = "spotting-cheaters") -> Path:
    """Download the Kaggle dataset using the Kaggle API.
    
    Requires: pip install kaggle
    And Kaggle API credentials in ~/.kaggle/kaggle.json
    
    Args:
        output_dir: Directory to save the dataset
        dataset_slug: Kaggle dataset identifier
        
    Returns:
        Path to the extracted dataset directory
    """
    import subprocess
    
    output_path = Path(output_dir) / dataset_slug
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Download using Kaggle CLI
    cmd = [
        "kaggle", "datasets", "download",
        "-d", dataset_slug,
        "-p", str(output_path),
        "--unzip"
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        LOGGER.error(f"Kaggle download failed: {result.stderr}")
        raise RuntimeError(f"Failed to download Kaggle dataset: {result.stderr}")
    
    LOGGER.info(f"Downloaded Kaggle dataset to {output_path}")
    return output_path
