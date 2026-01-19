"""Telemetry data structures for modelling player behaviour."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, List, Optional


@dataclass
class MoveTiming:
    """Represents the think time for a single move."""

    move_number: int
    player: str  # "white" or "black"
    seconds: float

    def clamp(self, minimum: float = 0.0) -> "MoveTiming":
        """Return a new :class:`MoveTiming` with non-negative duration."""

        return MoveTiming(move_number=self.move_number, player=self.player, seconds=max(self.seconds, minimum))


@dataclass
class SessionTelemetry:
    """Collection of timing samples for a single game."""

    entries: List[MoveTiming] = field(default_factory=list)

    def add(self, timing: MoveTiming) -> None:
        self.entries.append(timing)

    def players(self) -> List[str]:
        seen = []
        for entry in self.entries:
            if entry.player not in seen:
                seen.append(entry.player)
        return seen

    def average_time(self, player: Optional[str] = None) -> float:
        relevant = [e.seconds for e in self.entries if player is None or e.player == player]
        if not relevant:
            return 0.0
        return sum(relevant) / len(relevant)

    def stdev(self, player: Optional[str] = None) -> float:
        relevant = [e.seconds for e in self.entries if player is None or e.player == player]
        if len(relevant) < 2:
            return 0.0
        mean = sum(relevant) / len(relevant)
        variance = sum((value - mean) ** 2 for value in relevant) / (len(relevant) - 1)
        return variance ** 0.5

    def as_dict(self) -> List[dict]:
        return [dict(move_number=e.move_number, player=e.player, seconds=e.seconds) for e in self.entries]

    @classmethod
    def from_iterable(cls, records: Iterable[dict]) -> "SessionTelemetry":
        session = cls()
        for record in records:
            session.add(MoveTiming(move_number=int(record["move_number"]), player=str(record["player"]).lower(), seconds=float(record["seconds"])))
        return session
