"""Utilities for interacting with UCI-compatible chess engines.

This module provides a thin wrapper around a Stockfish-compatible engine
process.  The :class:`UCIEngineRunner` class handles engine life-cycle,
parsing of analysis output, and exposes synchronous evaluation helpers that
can be reused by higher level services.

The implementation intentionally keeps dependencies minimal so it can run in
restricted environments.  It only relies on the standard library and a UCI
engine binary being available on the host.
"""
from __future__ import annotations

import os
import queue
import subprocess
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

__all__ = [
    "EngineEvaluation",
    "UCIEngineError",
    "UCIEngineTimeout",
    "UCIEngineRunner",
]


class UCIEngineError(RuntimeError):
    """Raised when the engine reports an unexpected error."""


class UCIEngineTimeout(TimeoutError):
    """Raised when the engine fails to respond in the allotted time."""


@dataclass
class EngineEvaluation:
    """Represents a single evaluation returned by the engine."""

    fen: str
    depth: Optional[int] = None
    score_cp: Optional[int] = None
    mate_in: Optional[int] = None
    pv: List[str] = field(default_factory=list)
    bestmove: Optional[str] = None
    raw_info: List[str] = field(default_factory=list)
    multipv_info: List[Dict[str, object]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, object]:
        """Convert the evaluation to a serialisable dictionary."""

        return {
            "fen": self.fen,
            "depth": self.depth,
            "score_cp": self.score_cp,
            "mate_in": self.mate_in,
            "pv": list(self.pv),
            "bestmove": self.bestmove,
            "bestmove": self.bestmove,
            "raw_info": list(self.raw_info),
            "multipv_info": self.multipv_info,
        }


class UCIEngineRunner:
    """Lifecycle and communication manager for a single UCI engine process."""

    def __init__(
        self,
        engine_path: Optional[str] = None,
        *,
        options: Optional[Dict[str, object]] = None,
        startup_timeout: float = 10.0,
        command_timeout: float = 15.0,
        debug: bool = False,
    ) -> None:
        self.engine_path = engine_path or os.getenv("CHESSGUARD_STOCKFISH_PATH")
        if not self.engine_path:
            # Try to find bundled Stockfish
            project_root = Path(__file__).resolve().parent.parent.parent
            bundled = project_root / "bin" / "stockfish-windows-x86-64-avx2.exe"
            if bundled.exists():
                self.engine_path = str(bundled)
            else:
                self.engine_path = "stockfish"  # fallback to PATH
        self.options = options or {}
        self.startup_timeout = startup_timeout
        self.command_timeout = command_timeout
        self.debug = debug

        self._process: Optional[subprocess.Popen[str]] = None
        self._stdout_queue: "queue.Queue[Optional[str]]" = queue.Queue()
        self._reader_thread: Optional[threading.Thread] = None
        self._lock = threading.RLock()
        self._is_ready = False

    # ------------------------------------------------------------------
    # Engine lifecycle helpers
    # ------------------------------------------------------------------
    def start(self) -> None:
        """Start the engine process if it is not already running."""

        with self._lock:
            if self._process and self._process.poll() is None:
                return

            if not self._binary_exists():
                raise UCIEngineError(
                    f"Unable to find engine binary at '{self.engine_path}'. "
                    "Configure CHESSGUARD_STOCKFISH_PATH or pass engine_path."
                )

            self._process = subprocess.Popen(
                [self.engine_path],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1,
            )
            assert self._process.stdout is not None
            self._reader_thread = threading.Thread(
                target=self._enqueue_stdout,
                name="uci-engine-stdout",
                args=(self._process.stdout,),
                daemon=True,
            )
            self._reader_thread.start()

            self._send_command("uci")
            self._consume_until(lambda line: line.strip() == "uciok", self.startup_timeout)

            for option, value in self.options.items():
                self._send_command(f"setoption name {option} value {value}")

            self._send_command("isready")
            self._consume_until(lambda line: line.strip() == "readyok", self.startup_timeout)
            self._is_ready = True

    def stop(self) -> None:
        """Terminate the engine process."""

        with self._lock:
            if not self._process:
                return

            if self._process.poll() is None:
                try:
                    self._send_command("quit")
                except BrokenPipeError:
                    pass

                try:
                    self._process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    self._process.kill()

            self._process = None
            self._is_ready = False

    def __enter__(self) -> "UCIEngineRunner":
        self.start()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.stop()

    # ------------------------------------------------------------------
    # Evaluation API
    # ------------------------------------------------------------------
    def evaluate_position(
        self,
        fen: str,
        *,
        moves: Optional[Sequence[str]] = None,
        depth: Optional[int] = 15,
        movetime: Optional[int] = None,
        search_moves: Optional[Iterable[str]] = None,
        multipv: int = 1,
    ) -> EngineEvaluation:
        """Request an evaluation for a given position.

        Parameters
        ----------
        fen:
            A FEN string describing the position to analyse.
        moves:
            Optional sequence of UCI moves that should be played after the
            given FEN.  This mirrors the behaviour of the UCI ``position``
            command.
        depth:
            Fixed search depth.  If ``None`` the engine will rely on the
            provided ``movetime`` limit.
        movetime:
            Milliseconds the engine is allowed to think.  Mutually exclusive
            with ``depth``.
        search_moves:
            Optional iterable restricting the search to specific moves.
        multipv:
            Number of principal variations to request.  Defaults to ``1``.
        """

        with self._lock:
            self.start()
            assert self._process is not None

            self._send_command("ucinewgame")
            if moves:
                move_list = " ".join(moves)
                self._send_command(f"position fen {fen} moves {move_list}")
            else:
                self._send_command(f"position fen {fen}")

            if multipv > 1:
                self._send_command(f"setoption name MultiPV value {multipv}")

            go_args: List[str] = []
            if depth is not None:
                go_args.extend(["depth", str(int(depth))])
            if movetime is not None:
                go_args.extend(["movetime", str(int(movetime))])
            if search_moves:
                go_args.append("searchmoves")
                go_args.extend(list(search_moves))

            go_command = "go" + (" " + " ".join(go_args) if go_args else "")
            self._send_command(go_command)

            info_lines, bestmove_line = self._collect_analysis_output()
            evaluation = self._parse_engine_output(
                fen,
                info_lines,
                bestmove_line,
            )

            if multipv > 1:
                # Reset MultiPV for future single PV searches.
                self._send_command("setoption name MultiPV value 1")

            return evaluation

    def evaluate_move(
        self,
        fen: str,
        move: str,
        *,
        depth: Optional[int] = 15,
        movetime: Optional[int] = None,
    ) -> EngineEvaluation:
        """Convenience wrapper that evaluates a single forced move."""

        return self.evaluate_position(
            fen,
            depth=depth,
            movetime=movetime,
            search_moves=[move],
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _binary_exists(self) -> bool:
        """Return ``True`` if the configured engine binary is available."""

        engine_path = Path(self.engine_path)
        if engine_path.is_file():
            return os.access(engine_path, os.X_OK)

        for directory in os.getenv("PATH", "").split(os.pathsep):
            candidate = Path(directory) / self.engine_path
            if candidate.is_file() and os.access(candidate, os.X_OK):
                return True
        return False

    def _enqueue_stdout(self, stream) -> None:
        """Background reader thread that pushes stdout lines onto a queue."""

        for line in iter(stream.readline, ""):
            self._stdout_queue.put(line.rstrip("\n"))
        self._stdout_queue.put(None)

    def _send_command(self, command: str) -> None:
        if self.debug:
            print(f"[engine->] {command}")

        if not self._process or self._process.stdin is None:
            raise UCIEngineError("Engine process is not running.")

        try:
            self._process.stdin.write(command + "\n")
            self._process.stdin.flush()
        except BrokenPipeError as exc:
            raise UCIEngineError("Engine process terminated unexpectedly.") from exc

    def _consume_until(self, predicate, timeout: float) -> List[str]:
        """Consume stdout until the predicate returns True."""

        deadline = time.time() + timeout
        lines: List[str] = []
        while time.time() < deadline:
            remaining = max(0.0, deadline - time.time())
            try:
                line = self._stdout_queue.get(timeout=remaining)
            except queue.Empty as exc:  # pragma: no cover - defensive
                raise UCIEngineTimeout("Engine response timed out.") from exc

            if line is None:
                break

            if self.debug:
                print(f"[engine<-] {line}")

            lines.append(line)
            if predicate(line):
                return lines

        raise UCIEngineTimeout("Engine response timed out.")

    def _collect_analysis_output(self) -> Tuple[List[str], Optional[str]]:
        """Collect analysis lines until the ``bestmove`` response."""

        info_lines: List[str] = []
        bestmove_line: Optional[str] = None
        deadline = time.time() + self.command_timeout

        while time.time() < deadline:
            remaining = max(0.0, deadline - time.time())
            try:
                line = self._stdout_queue.get(timeout=remaining)
            except queue.Empty as exc:
                raise UCIEngineTimeout("Timed out waiting for bestmove.") from exc

            if line is None:
                break

            if self.debug:
                print(f"[engine<-] {line}")

            stripped = line.strip()
            if stripped.startswith("info"):
                info_lines.append(stripped)
            elif stripped.startswith("bestmove"):
                bestmove_line = stripped
                break
            else:
                info_lines.append(stripped)

        if bestmove_line is None:
            raise UCIEngineTimeout("Engine did not return a bestmove response.")

        return info_lines, bestmove_line

    def _parse_engine_output(
        self,
        fen: str,
        info_lines: Sequence[str],
        bestmove_line: str,
    ) -> EngineEvaluation:
        """Parse accumulated engine output into a structured evaluation."""

        depth: Optional[int] = None
        score_cp: Optional[int] = None
        mate_in: Optional[int] = None
        pv: List[str] = []
        multipv_data: List[Dict[str, object]] = []

        for line in info_lines:
            tokens = line.split()
            if "depth" in tokens:
                idx = tokens.index("depth")
                try:
                    current_depth = int(tokens[idx + 1])
                except (IndexError, ValueError):
                    current_depth = None
            else:
                current_depth = None

            if depth is None or (
                current_depth is not None and depth is not None and current_depth >= depth
            ):
                if current_depth is not None:
                    depth = current_depth

                if "score" in tokens:
                    score_index = tokens.index("score")
                    try:
                        score_type = tokens[score_index + 1]
                        value = tokens[score_index + 2]
                    except IndexError:
                        score_type = None
                        value = None

                    if score_type == "cp" and value is not None:
                        try:
                            score_cp = int(value)
                            mate_in = None
                        except ValueError:
                            pass
                    elif score_type == "mate" and value is not None:
                        try:
                            mate_in = int(value)
                            score_cp = None
                        except ValueError:
                            pass

                    if "pv" in tokens:
                        pv_index = tokens.index("pv")
                        curr_pv = tokens[pv_index + 1 :]
                        
                        # Store per-PV info if multipv is present
                        if "multipv" in tokens:
                            try:
                                mpv_idx = tokens.index("multipv")
                                mpv_id = int(tokens[mpv_idx + 1])
                                # Ensure list is big enough
                                while len(multipv_data) < mpv_id:
                                    multipv_data.append({})
                                
                                multipv_data[mpv_id - 1] = {
                                    "depth": current_depth,
                                    "score_cp": score_cp if score_type == "cp" else None,
                                    "mate_in": mate_in if score_type == "mate" else None,
                                    "pv": curr_pv
                                }
                            except (ValueError, IndexError):
                                pass

        bestmove_tokens = bestmove_line.split()
        bestmove = bestmove_tokens[1] if len(bestmove_tokens) > 1 else None

        return EngineEvaluation(
            fen=fen,
            depth=depth,
            score_cp=score_cp,
            mate_in=mate_in,
            pv=pv,
            bestmove=bestmove,
            raw_info=list(info_lines),
            multipv_info=multipv_data,
        )
