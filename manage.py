"""Command line helpers for dataset generation and engine tooling."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable, List

from server.datasets.queue import SessionQueue, SessionSpec


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="ChessGuard administrative CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    queue_parser = subparsers.add_parser(
        "queue",
        help="Queue dataset generation sessions",
    )
    queue_parser.add_argument(
        "--queue-path",
        type=Path,
        default=Path("var/session_queue.json"),
        help="Location of the queue JSON file.",
    )
    queue_sub = queue_parser.add_subparsers(dest="mode", required=True)

    self_play = queue_sub.add_parser(
        "self-play", help="Queue engine self-play sessions labelled as cheating"
    )
    self_play.add_argument("--games", type=int, default=1, help="Number of games to queue")
    self_play.add_argument(
        "--engine-depth", type=int, default=18, help="Search depth for the engine"
    )
    self_play.add_argument(
        "--movetime",
        type=int,
        default=None,
        help="Optional thinking time in milliseconds (overrides depth if set)",
    )
    self_play.add_argument(
        "--label",
        choices=["cheating", "clean"],
        default="cheating",
        help="Label assigned to generated games",
    )
    self_play.add_argument(
        "--notes", default=None, help="Free-form description stored alongside the job"
    )

    hvh = queue_sub.add_parser(
        "engine-vs-human",
        help="Queue matches between a human account and the configured engine",
    )
    hvh.add_argument("--human-id", required=True, help="Identifier for the human player")
    hvh.add_argument("--games", type=int, default=1, help="Number of games to queue")
    hvh.add_argument(
        "--label",
        choices=["cheating", "clean"],
        default="cheating",
        help="Ground truth label for the resulting games",
    )
    hvh.add_argument(
        "--engine-depth", type=int, default=18, help="Search depth for the engine"
    )
    hvh.add_argument(
        "--movetime",
        type=int,
        default=None,
        help="Optional thinking time in milliseconds",
    )
    hvh.add_argument(
        "--notes", default=None, help="Metadata string stored with the job"
    )

    list_parser = subparsers.add_parser("list", help="List queued sessions")
    list_parser.add_argument(
        "--queue-path",
        type=Path,
        default=Path("var/session_queue.json"),
        help="Location of the queue JSON file.",
    )
    list_parser.add_argument(
        "--status",
        default=None,
        help="Filter sessions by status (e.g., pending, complete)",
    )

    return parser


def _create_sessions(
    *,
    mode: str,
    games: int,
    label: str,
    engine_depth: int,
    movetime: int | None,
    notes: str | None,
    human_id: str | None = None,
) -> List[SessionSpec]:
    base_metadata = {"notes": notes} if notes else {}
    base_config = {"engine_depth": engine_depth}
    if movetime is not None:
        base_config["movetime"] = movetime

    sessions: List[SessionSpec] = []
    for _ in range(games):
        metadata = dict(base_metadata)
        if mode == "self-play":
            metadata["players"] = ["engine", "engine"]
        elif mode == "engine-vs-human":
            metadata["players"] = [human_id or "unknown", "engine"]

        sessions.append(
            SessionSpec.create(
                session_type=mode,
                label=label,
                config=dict(base_config),
                metadata=metadata,
            )
        )
    return sessions


def run_queue_command(args: argparse.Namespace) -> None:
    queue = SessionQueue(args.queue_path)

    sessions = _create_sessions(
        mode=args.mode,
        games=args.games,
        label=args.label,
        engine_depth=args.engine_depth,
        movetime=args.movetime,
        notes=args.notes,
        human_id=getattr(args, "human_id", None),
    )
    queue.bulk_enqueue(sessions)

    print(f"Queued {len(sessions)} session(s) at {args.queue_path}:")
    for session in sessions:
        print(f" - {session.session_type} {session.id} [{session.label}]")


def run_list_command(args: argparse.Namespace) -> None:
    queue = SessionQueue(args.queue_path)
    sessions = queue.list(status=args.status)
    if not sessions:
        print("No sessions queued.")
        return

    print(json.dumps([session.to_dict() for session in sessions], indent=2))


def main(argv: Iterable[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "queue":
        run_queue_command(args)
    elif args.command == "list":
        run_list_command(args)
    else:  # pragma: no cover - defensive
        parser.error(f"Unknown command {args.command}")


if __name__ == "__main__":
    main()
