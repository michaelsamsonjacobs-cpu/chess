"""Terminal dashboard for ChessGuard risk alerts."""

from __future__ import annotations

import argparse
import os
import sys
import textwrap
from typing import Dict, Iterable, List, Optional

import requests


DEFAULT_BASE_URL = os.getenv("CHESSGUARD_API_URL", "http://localhost:8000")
DEFAULT_API_KEY = os.getenv("CHESSGUARD_API_KEY", "director-key")


class ChessGuardClient:
    """Simple REST client for the ChessGuard API."""

    def __init__(self, base_url: str, api_key: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    # ------------------------------------------------------------------
    def submit_game(
        self,
        event_id: str,
        player_id: str,
        pgn: str,
        round: Optional[int] = None,
        metadata: Optional[Dict[str, str]] = None,
    ) -> Dict[str, object]:
        payload = {
            "event_id": event_id,
            "player_id": player_id,
            "pgn": pgn,
            "metadata": metadata or {},
        }
        if round is not None:
            payload["round"] = round
        return self._request("POST", "/games", json=payload)

    def get_risk(self, game_id: str) -> Dict[str, object]:
        return self._request("GET", f"/games/{game_id}/risk")

    def get_explanation(self, game_id: str) -> Dict[str, object]:
        return self._request("GET", f"/games/{game_id}/explanation")

    def get_alerts(
        self,
        event_id: Optional[str] = None,
        threshold: Optional[float] = None,
    ) -> List[Dict[str, object]]:
        params: Dict[str, object] = {}
        if threshold is not None:
            params["threshold"] = threshold
        if event_id:
            response = self._request("GET", f"/events/{event_id}/alerts", params=params)
        else:
            response = self._request("GET", "/alerts", params=params)
        return list(response.get("alerts", []))

    # ------------------------------------------------------------------
    def _request(self, method: str, path: str, **kwargs) -> Dict[str, object]:
        url = f"{self.base_url}{path}"
        headers = kwargs.pop("headers", {})
        if self.api_key:
            headers.setdefault("X-API-Key", self.api_key)
        response = requests.request(method, url, headers=headers, **kwargs)
        if response.status_code >= 400:
            raise RuntimeError(
                f"{method} {path} failed with {response.status_code}: {response.text.strip()}"
            )
        if response.content:
            return response.json()
        return {}


# ----------------------------------------------------------------------
# CLI helpers
# ----------------------------------------------------------------------

def parse_metadata(pairs: Iterable[str]) -> Dict[str, str]:
    metadata: Dict[str, str] = {}
    for pair in pairs:
        if "=" not in pair:
            raise argparse.ArgumentTypeError(
                f"Metadata '{pair}' must be in key=value format"
            )
        key, value = pair.split("=", 1)
        metadata[key.strip()] = value.strip()
    return metadata


def render_risk(risk: Dict[str, object]) -> str:
    tier = risk["risk"]["tier"]
    score = risk["risk"]["score"]
    recommendations = risk["risk"].get("recommended_actions", [])
    lines = [
        f"Risk Score: {score:.1f} ({tier})",
        f"Event: {risk['event_id']}  Player: {risk['player_id']}",
    ]
    if recommendations:
        lines.append("Recommended actions:")
        for action in recommendations:
            lines.append(f"  - {action}")
    return "\n".join(lines)


def render_explanation(explanation: Dict[str, object]) -> str:
    payload = explanation["explanation"]
    lines = ["Model Explanation:", textwrap.fill(payload["summary"], width=80, initial_indent="  ", subsequent_indent="  ")]
    factors = payload.get("top_factors", [])
    if factors:
        lines.append("Top contributing factors:")
        for factor in factors:
            lines.append(
                f"  - {factor['feature']}: {factor['score_contribution']} (raw={factor['raw_value']})"
            )
    return "\n".join(lines)


def render_alerts(alerts: List[Dict[str, object]]) -> str:
    if not alerts:
        return "No alerts above the configured threshold."

    headers = ["Game", "Player", "Score", "Tier", "Submitted", "By"]
    column_widths = [len(header) for header in headers]
    rows: List[List[str]] = []
    for alert in alerts:
        row = [
            alert["game_id"],
            alert["player_id"],
            f"{alert['risk_score']:.1f}",
            alert["tier"],
            alert["submitted_at"],
            alert["submitted_by"],
        ]
        rows.append(row)
        column_widths = [max(col, len(value)) for col, value in zip(column_widths, row)]

    def format_row(row: List[str]) -> str:
        return " | ".join(value.ljust(width) for value, width in zip(row, column_widths))

    lines = [format_row(headers), "-+-".join("-" * width for width in column_widths)]
    lines.extend(format_row(row) for row in rows)
    lines.append("")
    lines.append("Recommended follow-ups:")
    for alert in alerts:
        for action in alert.get("recommended_actions", []):
            lines.append(f"  - Game {alert['game_id']}: {action}")
    return "\n".join(lines)


# ----------------------------------------------------------------------
# Command implementations
# ----------------------------------------------------------------------

def command_submit(args: argparse.Namespace, client: ChessGuardClient) -> None:
    metadata = parse_metadata(args.metadata or [])
    if args.pgn_file:
        with open(args.pgn_file, "r", encoding="utf-8") as handle:
            pgn = handle.read()
    else:
        pgn = args.pgn
    response = client.submit_game(
        event_id=args.event,
        player_id=args.player,
        pgn=pgn,
        round=args.round,
        metadata=metadata,
    )
    print("Submission accepted. Game ID:", response["game_id"])
    print(render_explanation(response))


def command_risk(args: argparse.Namespace, client: ChessGuardClient) -> None:
    risk = client.get_risk(args.game_id)
    print(render_risk(risk))


def command_explain(args: argparse.Namespace, client: ChessGuardClient) -> None:
    explanation = client.get_explanation(args.game_id)
    print(render_explanation(explanation))


def command_alerts(args: argparse.Namespace, client: ChessGuardClient) -> None:
    alerts = client.get_alerts(event_id=args.event, threshold=args.threshold)
    print(render_alerts(alerts))


COMMANDS = {
    "submit": command_submit,
    "risk": command_risk,
    "explain": command_explain,
    "alerts": command_alerts,
}


# ----------------------------------------------------------------------
# Entrypoint
# ----------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="ChessGuard terminal dashboard")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="ChessGuard API base URL")
    parser.add_argument("--api-key", default=DEFAULT_API_KEY, help="API key for authentication")

    subparsers = parser.add_subparsers(dest="command", required=True)

    submit_parser = subparsers.add_parser("submit", help="Submit a live PGN for assessment")
    submit_parser.add_argument("--event", required=True, help="Event identifier")
    submit_parser.add_argument("--player", required=True, help="Player identifier")
    submit_parser.add_argument("--round", type=int, help="Round number")
    submit_parser.add_argument("--pgn", help="Raw PGN string")
    submit_parser.add_argument("--pgn-file", help="Path to a PGN file")
    submit_parser.add_argument(
        "--metadata",
        nargs="*",
        default=[],
        help="Additional metadata in key=value form",
    )

    risk_parser = subparsers.add_parser("risk", help="Display risk details for a game")
    risk_parser.add_argument("game_id", help="Game identifier returned during submission")

    explain_parser = subparsers.add_parser("explain", help="Show explanation factors for a game")
    explain_parser.add_argument("game_id", help="Game identifier returned during submission")

    alerts_parser = subparsers.add_parser("alerts", help="List high risk alerts")
    alerts_parser.add_argument("--event", help="Filter alerts by event identifier")
    alerts_parser.add_argument(
        "--threshold", type=float, default=70.0, help="Minimum score required to surface"
    )

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.api_key:
        parser.error("An API key is required. Pass --api-key or set CHESSGUARD_API_KEY.")
    if args.command == "submit" and not (args.pgn or args.pgn_file):
        parser.error("Submit command requires either --pgn or --pgn-file")

    client = ChessGuardClient(base_url=args.base_url, api_key=args.api_key)
    handler = COMMANDS.get(args.command)
    try:
        handler(args, client)
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entrypoint
    sys.exit(main())
