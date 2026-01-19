'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

type Colour = 'white' | 'black';

interface ExperimentSession {
  session_id: string;
  player_id: string;
  mode: string;
  status: string;
  metadata: Record<string, string>;
}

interface ExperimentMoveEvaluation {
  fen: string;
  depth?: number | null;
  score_cp?: number | null;
  mate_in?: number | null;
  bestmove?: string | null;
  pv: string[];
  raw_info: string[];
}

interface ExperimentSessionMove {
  ply: number;
  actor: 'human' | 'engine';
  move_uci: string;
  move_san: string;
  fen_before: string;
  evaluation: ExperimentMoveEvaluation;
  reference?: ExperimentMoveEvaluation | null;
  centipawn_loss?: number | null;
  label: string;
}

interface ExperimentSessionState {
  session: ExperimentSession;
  board_fen: string;
  moves: ExperimentSessionMove[];
  history: string[];
  next_to_move: Colour;
  outcome?: string | null;
}

interface ExperimentMoveLabel {
  ply: number;
  label: string;
  confidence: number;
  notes?: string | null;
}

interface ExperimentExport {
  session_id: string;
  pgn: string;
  move_labels: ExperimentMoveLabel[];
  notes: string[];
}

interface ExperimentMoveResponse {
  player?: ExperimentSessionMove | null;
  engine?: ExperimentSessionMove | null;
  state: ExperimentSessionState;
  export?: ExperimentExport | null;
}

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, '') ?? 'http://localhost:8000';

const pieceSymbols: Record<string, string> = {
  p: '♟',
  r: '♜',
  n: '♞',
  b: '♝',
  q: '♛',
  k: '♚',
  P: '♙',
  R: '♖',
  N: '♘',
  B: '♗',
  Q: '♕',
  K: '♔',
};

function expandFenRow(row: string): string[] {
  const squares: string[] = [];
  for (const char of row) {
    const digit = Number.parseInt(char, 10);
    if (Number.isInteger(digit)) {
      squares.push(...Array(digit).fill(''));
    } else {
      squares.push(char);
    }
  }
  return squares;
}

function fenToBoard(fen: string): string[][] {
  const [placement] = fen.split(' ');
  return placement.split('/').map(expandFenRow);
}

function orientationFromMetadata(metadata: Record<string, string> | undefined): Colour {
  const value = metadata?.player_color?.toLowerCase();
  return value === 'black' ? 'black' : 'white';
}

function squareFromIndices(row: number, col: number): string {
  const file = String.fromCharCode('a'.charCodeAt(0) + col);
  const rank = 8 - row;
  return `${file}${rank}`;
}

function buildWebSocketUrl(sessionId: string): string {
  const url = new URL(API_BASE);
  url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:';
  url.pathname = `/experiment/play/session/${sessionId}/stream`;
  url.search = '';
  return url.toString();
}

function formatScore(evaluation: ExperimentMoveEvaluation): string {
  if (evaluation.mate_in !== null && evaluation.mate_in !== undefined) {
    const sign = evaluation.mate_in > 0 ? '+' : '';
    return `Mate ${sign}${evaluation.mate_in}`;
  }
  if (evaluation.score_cp !== null && evaluation.score_cp !== undefined) {
    const score = (evaluation.score_cp / 100).toFixed(2);
    return `${score}`;
  }
  return '—';
}

function MoveList({ moves }: { moves: ExperimentSessionMove[] }) {
  return (
    <div className="mt-6 overflow-hidden rounded-lg border border-slate-700">
      <table className="min-w-full divide-y divide-slate-800">
        <thead className="bg-slate-900/80">
          <tr className="text-left text-sm text-slate-300">
            <th className="px-3 py-2 font-medium">Ply</th>
            <th className="px-3 py-2 font-medium">Actor</th>
            <th className="px-3 py-2 font-medium">Move</th>
            <th className="px-3 py-2 font-medium">Label</th>
            <th className="px-3 py-2 font-medium">Score</th>
            <th className="px-3 py-2 font-medium">Δ CP</th>
          </tr>
        </thead>
        <tbody className="bg-slate-950/60 text-sm text-slate-200">
          {moves.map((move) => (
            <tr key={move.ply} className="odd:bg-slate-950/40">
              <td className="px-3 py-2 font-mono text-slate-300">{move.ply}</td>
              <td className="px-3 py-2 capitalize text-slate-300">{move.actor}</td>
              <td className="px-3 py-2 font-mono text-slate-100">{move.move_san}</td>
              <td className="px-3 py-2 text-slate-300">{move.label}</td>
              <td className="px-3 py-2 text-slate-200">{formatScore(move.evaluation)}</td>
              <td className="px-3 py-2 text-slate-200">
                {move.centipawn_loss !== null && move.centipawn_loss !== undefined
                  ? move.centipawn_loss
                  : '—'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

interface BoardProps {
  fen: string;
  orientation: Colour;
  disabled?: boolean;
  selected?: string | null;
  onSelect(square: string): void;
}

function Board({ fen, orientation, disabled, selected, onSelect }: BoardProps) {
  const board = useMemo(() => fenToBoard(fen), [fen]);

  const squares = useMemo(() => {
    const rendered: {
      coord: string;
      piece: string;
      isDark: boolean;
    }[] = [];

    for (let displayRow = 0; displayRow < 8; displayRow += 1) {
      const actualRow = orientation === 'white' ? displayRow : 7 - displayRow;
      const row = board[actualRow] ?? Array(8).fill('');

      for (let displayCol = 0; displayCol < 8; displayCol += 1) {
        const actualCol = orientation === 'white' ? displayCol : 7 - displayCol;
        const coord = squareFromIndices(actualRow, actualCol);
        const piece = row[actualCol] ?? '';
        const isDark = (actualRow + actualCol) % 2 === 1;
        rendered.push({ coord, piece, isDark });
      }
    }

    return rendered;
  }, [board, orientation]);

  return (
    <div className="grid grid-cols-8 overflow-hidden rounded-xl border border-slate-700 shadow-xl">
      {squares.map(({ coord, piece, isDark }) => {
        const glyph = pieceSymbols[piece] ?? '';
        const isSelected = selected === coord;
        const squareClasses = [
          'flex h-16 w-16 items-center justify-center text-3xl transition-colors',
          isDark ? 'bg-slate-700/80' : 'bg-slate-300/80',
          isSelected ? 'ring-4 ring-amber-400 ring-offset-2 ring-offset-slate-900' : '',
          disabled ? 'cursor-not-allowed opacity-80' : 'cursor-pointer hover:brightness-110',
        ]
          .filter(Boolean)
          .join(' ');

        return (
          <button
            key={coord}
            type="button"
            className={squareClasses}
            onClick={() => !disabled && onSelect(coord)}
            disabled={disabled}
            aria-label={coord}
          >
            <span className="drop-shadow-[0_1px_1px_rgba(0,0,0,0.6)]">{glyph}</span>
          </button>
        );
      })}
    </div>
  );
}

export default function PlayExperimentPage() {
  const [playerId, setPlayerId] = useState('');
  const [mode, setMode] = useState('clean');
  const [playerColor, setPlayerColor] = useState<Colour>('white');
  const [consent, setConsent] = useState(false);
  const [timeControl, setTimeControl] = useState('');
  const [session, setSession] = useState<ExperimentSessionState | null>(null);
  const [selectedSquare, setSelectedSquare] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [exportData, setExportData] = useState<ExperimentExport | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  const activeColour = orientationFromMetadata(session?.session.metadata);
  const isPlayersTurn =
    session && session.session.status !== 'completed'
      ? session.next_to_move === activeColour
      : false;

  const sessionId = session?.session.session_id;

  useEffect(() => {
    return () => {
      wsRef.current?.close();
    };
  }, []);

  const updateFromResponse = useCallback((response: ExperimentMoveResponse) => {
    setSession(response.state);
    if (response.export) {
      setExportData(response.export);
    }
  }, []);

  const connectWebSocket = useCallback(
    (id: string) => {
      try {
        const ws = new WebSocket(buildWebSocketUrl(id));
        wsRef.current?.close();
        wsRef.current = ws;

        ws.onopen = () => {
          setStatus('Connected to live engine stream.');
        };

        ws.onmessage = (event) => {
          const payload = JSON.parse(event.data);
          if (payload.type === 'state') {
            setSession(payload.payload);
          } else if (payload.type === 'update') {
            setSession(payload.state);
            setStatus('Move processed by engine.');
          } else if (payload.type === 'complete') {
            setSession(payload.state);
            setExportData(payload.export);
            setStatus('Session completed. Export ready.');
          } else if (payload.type === 'error') {
            setError(payload.detail ?? 'Engine reported an error.');
          }
        };

        ws.onerror = () => {
          setError('Lost connection to engine stream. Falling back to REST.');
        };

        ws.onclose = () => {
          setStatus('Engine stream closed.');
        };
      } catch (err) {
        console.error(err);
        setError('Unable to establish engine stream.');
      }
    },
    [],
  );

  const startSession = useCallback(async () => {
    if (!consent) {
      setError('You must provide informed consent to start the experiment.');
      return;
    }

    setIsLoading(true);
    setError(null);
    setStatus('Starting session…');
    setExportData(null);

    const payload = {
      player_id: playerId || 'anonymous-volunteer',
      mode,
      consent: true,
      time_control: timeControl || undefined,
      metadata: {
        player_color: playerColor,
      },
    };

    try {
      const response = await fetch(`${API_BASE}/experiment/play/session`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        const detail = await response.json().catch(() => ({}));
        throw new Error(detail.detail ?? 'Unable to start session.');
      }

      const data: ExperimentSessionState = await response.json();
      setSession(data);
      setSelectedSquare(null);
      setStatus('Session ready. Make your first move.');
      connectWebSocket(data.session.session_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error starting session.');
    } finally {
      setIsLoading(false);
    }
  }, [consent, playerId, mode, timeControl, playerColor, connectWebSocket]);

  const submitMove = useCallback(
    async (uci: string) => {
      if (!sessionId) {
        return;
      }

      setIsLoading(true);
      setError(null);
      setStatus(`Submitting move ${uci}…`);

      const socket = wsRef.current;
      if (socket && socket.readyState === WebSocket.OPEN) {
        socket.send(JSON.stringify({ type: 'move', move: uci }));
        setIsLoading(false);
        return;
      }

      try {
        const response = await fetch(
          `${API_BASE}/experiment/play/session/${sessionId}/move`,
          {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ move: uci }),
          },
        );

        if (!response.ok) {
          const detail = await response.json().catch(() => ({}));
          throw new Error(detail.detail ?? 'Move rejected by engine.');
        }

        const data: ExperimentMoveResponse = await response.json();
        updateFromResponse(data);
        setStatus(`Move ${uci} accepted.`);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Move submission failed.');
      } finally {
        setIsLoading(false);
      }
    },
    [sessionId, updateFromResponse],
  );

  const completeSession = useCallback(async () => {
    if (!sessionId) {
      return;
    }

    setIsLoading(true);
    setStatus('Finalising session…');

    const socket = wsRef.current;
    if (socket && socket.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify({ type: 'complete' }));
      setIsLoading(false);
      return;
    }

    try {
      const response = await fetch(
        `${API_BASE}/experiment/play/session/${sessionId}/complete`,
        { method: 'POST' },
      );

      if (!response.ok) {
        const detail = await response.json().catch(() => ({}));
        throw new Error(detail.detail ?? 'Unable to complete session.');
      }

      const data: ExperimentMoveResponse = await response.json();
      updateFromResponse(data);
      setStatus('Session completed. Export ready.');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to complete session.');
    } finally {
      setIsLoading(false);
    }
  }, [sessionId, updateFromResponse]);

  const handleSquareSelect = useCallback(
    (square: string) => {
      if (!session || !isPlayersTurn) {
        return;
      }

      if (!selectedSquare) {
        setSelectedSquare(square);
        return;
      }

      if (selectedSquare === square) {
        setSelectedSquare(null);
        return;
      }

      const move = `${selectedSquare}${square}`;
      setSelectedSquare(null);
      void submitMove(move);
    },
    [session, isPlayersTurn, selectedSquare, submitMove],
  );

  return (
    <main className="min-h-screen bg-gradient-to-b from-slate-950 via-slate-900 to-slate-950 text-slate-100">
      <div className="mx-auto max-w-6xl px-6 py-12">
        <header className="mb-10">
          <p className="text-sm uppercase tracking-[0.2em] text-amber-400">ChessGuard Lab</p>
          <h1 className="mt-3 text-4xl font-semibold text-white sm:text-5xl">
            Play controlled sessions against the ChessGuard engine
          </h1>
          <p className="mt-4 max-w-3xl text-lg text-slate-300">
            Launch a labelled experiment session to capture PGN, engine responses, and move-level
            annotations for downstream training. Every move you play is evaluated in real time so you
            can export precise centipawn feedback when the session concludes.
          </p>
        </header>

        <section className="rounded-2xl border border-slate-800 bg-slate-950/60 p-6 shadow-xl backdrop-blur">
          <h2 className="text-2xl font-semibold text-white">Session setup</h2>
          <p className="mt-2 text-sm text-slate-400">
            Configure your colour, mode, and time control. Sessions run entirely in-memory and stream
            moves to the backend engine. Consent is required because moves are persisted for research
            exports.
          </p>

          <div className="mt-6 grid gap-6 sm:grid-cols-2">
            <label className="flex flex-col gap-2 text-sm">
              <span className="text-slate-300">Player identifier</span>
              <input
                value={playerId}
                onChange={(event) => setPlayerId(event.target.value)}
                placeholder="eg. volunteer-42"
                className="rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-slate-100 focus:border-amber-400 focus:outline-none"
              />
            </label>

            <label className="flex flex-col gap-2 text-sm">
              <span className="text-slate-300">Experiment mode</span>
              <select
                value={mode}
                onChange={(event) => setMode(event.target.value)}
                className="rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-slate-100 focus:border-amber-400 focus:outline-none"
              >
                <option value="clean">Clean (no assistance)</option>
                <option value="assisted_10">Assisted 10%</option>
                <option value="assisted_20">Assisted 20%</option>
                <option value="assisted_40">Assisted 40%</option>
              </select>
            </label>

            <label className="flex flex-col gap-2 text-sm">
              <span className="text-slate-300">Preferred colour</span>
              <select
                value={playerColor}
                onChange={(event) => setPlayerColor(event.target.value as Colour)}
                className="rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-slate-100 focus:border-amber-400 focus:outline-none"
              >
                <option value="white">White</option>
                <option value="black">Black</option>
              </select>
            </label>

            <label className="flex flex-col gap-2 text-sm">
              <span className="text-slate-300">Time control (optional)</span>
              <input
                value={timeControl}
                onChange={(event) => setTimeControl(event.target.value)}
                placeholder="eg. 5+0 rapid"
                className="rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-slate-100 focus:border-amber-400 focus:outline-none"
              />
            </label>
          </div>

          <label className="mt-6 flex items-center gap-3 text-sm text-slate-300">
            <input
              type="checkbox"
              checked={consent}
              onChange={(event) => setConsent(event.target.checked)}
              className="h-4 w-4 rounded border-slate-600 bg-slate-900 text-amber-400 focus:ring-amber-500"
            />
            I consent to my moves being stored and labelled for ChessGuard research.
          </label>

          <div className="mt-6 flex flex-wrap items-center gap-4">
            <button
              type="button"
              onClick={() => void startSession()}
              disabled={isLoading}
              className="rounded-lg bg-amber-500 px-5 py-2 text-sm font-semibold text-black shadow hover:bg-amber-400 disabled:cursor-not-allowed disabled:bg-amber-800/40"
            >
              {session ? 'Restart session' : 'Start session'}
            </button>

            {session ? (
              <button
                type="button"
                onClick={() => void completeSession()}
                disabled={isLoading}
                className="rounded-lg border border-amber-500 px-5 py-2 text-sm font-semibold text-amber-300 hover:bg-amber-500/10 disabled:cursor-not-allowed disabled:border-slate-600 disabled:text-slate-500"
              >
                Complete &amp; export
              </button>
            ) : null}

            {status ? <span className="text-sm text-slate-400">{status}</span> : null}
          </div>

          {error ? (
            <div className="mt-4 rounded-lg border border-red-500/40 bg-red-500/10 px-4 py-3 text-sm text-red-200">
              {error}
            </div>
          ) : null}
        </section>

        {session ? (
          <section className="mt-10 grid gap-8 lg:grid-cols-[minmax(0,_480px)_1fr]">
            <div className="flex flex-col gap-4">
              <Board
                fen={session.board_fen}
                orientation={activeColour}
                disabled={!isPlayersTurn || isLoading || session.session.status === 'completed'}
                selected={selectedSquare}
                onSelect={handleSquareSelect}
              />
              <div className="rounded-xl border border-slate-800 bg-slate-950/60 p-4 text-sm text-slate-300">
                <p>
                  Session ID: <span className="font-mono text-slate-100">{session.session.session_id}</span>
                </p>
                <p className="mt-1">
                  Next to move: <span className="font-semibold text-amber-400">{session.next_to_move}</span>
                </p>
                {session.outcome ? (
                  <p className="mt-1 text-emerald-400">Game concluded · Result {session.outcome}</p>
                ) : null}
              </div>
            </div>

            <div>
              <h3 className="text-xl font-semibold text-white">Move log</h3>
              <p className="mt-2 text-sm text-slate-400">
                Engine evaluations and centipawn deltas are captured automatically. Labels update as
                you play to reflect human accuracy, mistakes, and engine responses.
              </p>
              <MoveList moves={session.moves} />

              {exportData ? (
                <div className="mt-8 space-y-4 rounded-2xl border border-emerald-500/30 bg-emerald-500/5 p-6">
                  <div>
                    <h4 className="text-lg font-semibold text-emerald-300">PGN export</h4>
                    <pre className="mt-2 max-h-48 overflow-auto rounded-lg bg-slate-900/80 p-3 text-xs text-emerald-100">
                      {exportData.pgn}
                    </pre>
                  </div>
                  <div>
                    <h4 className="text-lg font-semibold text-emerald-300">Move labels</h4>
                    <ul className="mt-2 space-y-1 text-sm text-emerald-200">
                      {exportData.move_labels.map((label) => (
                        <li key={label.ply} className="flex items-center justify-between rounded border border-emerald-500/20 bg-emerald-500/10 px-3 py-2">
                          <span className="font-mono">Ply {label.ply}</span>
                          <span>{label.label}</span>
                          <span className="text-xs text-emerald-300/80">confidence {Math.round(label.confidence * 100)}%</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>
              ) : null}
            </div>
          </section>
        ) : null}
      </div>
    </main>
  );
}
