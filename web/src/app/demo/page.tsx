"use client";

import { useEffect, useMemo, useState } from "react";
import type { ChangeEvent } from "react";

import Link from "next/link";

const pieceSymbols: Record<string, string> = {
  p: "♟",
  r: "♜",
  n: "♞",
  b: "♝",
  q: "♛",
  k: "♚",
  P: "♙",
  R: "♖",
  N: "♘",
  B: "♗",
  Q: "♕",
  K: "♔",
};

type ScenarioMove = {
  ply: number;
  move: string;
  evaluation: string;
  suspicion: string;
  commentary: string;
  board: string[];
};

type Scenario = {
  id: string;
  name: string;
  summary: string;
  event: string;
  timeControl: string;
  players: {
    white: string;
    black: string;
  };
  riskLevel: "Stable" | "Heightened" | "Critical";
  moves: ScenarioMove[];
};

type ApiResponse = {
  scenarios: Scenario[];
};

function boardFromRanks(ranks: string[]) {
  return ranks.map((rank) => rank.split(""));
}

function riskBadgeColor(level: Scenario["riskLevel"]) {
  switch (level) {
    case "Critical":
      return "bg-rose-500/20 text-rose-200";
    case "Heightened":
      return "bg-amber-400/20 text-amber-200";
    default:
      return "bg-emerald-500/20 text-emerald-200";
  }
}

export default function DemoPage() {
  const [data, setData] = useState<Scenario[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const response = await fetch("/api/analysis");
        if (!response.ok) {
          throw new Error("Unable to load scenarios");
        }
        const json: ApiResponse = await response.json();
        if (!cancelled) {
          setData(json.scenarios);
          setSelectedId(json.scenarios[0]?.id ?? null);
          setCurrentIndex(0);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Unexpected error");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    load();

    return () => {
      cancelled = true;
    };
  }, []);

  const activeScenario = useMemo(() => {
    if (!selectedId) {
      return undefined;
    }
    return data.find((scenario) => scenario.id === selectedId);
  }, [data, selectedId]);

  const activeMove = activeScenario?.moves[currentIndex];
  const board = activeMove ? boardFromRanks(activeMove.board) : [];

  const maxIndex = (activeScenario?.moves.length ?? 0) - 1;

  function goTo(index: number) {
    if (!activeScenario) return;
    const next = Math.max(0, Math.min(index, maxIndex));
    setCurrentIndex(next);
  }

  function handleScenarioChange(event: ChangeEvent<HTMLSelectElement>) {
    const nextId = event.target.value;
    setSelectedId(nextId);
    setCurrentIndex(0);
  }

  return (
    <div className="mx-auto flex w-full max-w-6xl flex-col gap-12 px-4 pb-20 pt-16 sm:px-6 lg:pt-20">
      <div className="flex flex-col gap-6">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="space-y-2">
            <p className="text-sm font-semibold uppercase tracking-wide text-indigo-200">Live fairness console</p>
            <h1 className="text-4xl font-semibold text-white sm:text-5xl">Game analysis demo</h1>
          </div>
          <Link
            href="/waitlist"
            className="inline-flex items-center justify-center rounded-full border border-white/20 px-5 py-2 text-sm font-semibold text-white transition hover:border-white/50"
          >
            Talk to an analyst
          </Link>
        </div>
        <p className="max-w-2xl text-lg text-slate-300">
          Explore how ChessGuard blends statistical models, behavioural telemetry, and human context to surface the right alerts at the right moment. Select a scenario to replay the exact evidence an arbiter receives.
        </p>
      </div>

      <section className="grid gap-10 lg:grid-cols-[2fr_3fr] lg:items-start">
        <div className="flex flex-col gap-6 rounded-3xl border border-white/10 bg-black/30 p-6">
          <label className="text-xs font-semibold uppercase tracking-wide text-slate-400" htmlFor="scenario-select">
            Scenario
          </label>
          <select
            id="scenario-select"
            className="w-full rounded-2xl border border-white/10 bg-slate-950/80 px-4 py-3 text-sm text-white focus:border-indigo-400"
            value={selectedId ?? ""}
            onChange={handleScenarioChange}
          >
            {data.map((scenario) => (
              <option key={scenario.id} value={scenario.id}>
                {scenario.name}
              </option>
            ))}
          </select>

          {loading && <p className="text-sm text-slate-400">Loading scenarios…</p>}
          {error && !loading && (
            <p className="rounded-2xl bg-rose-500/10 p-4 text-sm text-rose-200">{error}</p>
          )}

          {activeScenario && !loading && !error && (
            <div className="space-y-5 text-sm text-slate-300">
              <div className="flex items-center gap-3">
                <span className={`rounded-full px-3 py-1 text-xs font-semibold ${riskBadgeColor(activeScenario.riskLevel)}`}>
                  {activeScenario.riskLevel}
                </span>
                <span className="text-xs uppercase tracking-wide text-slate-400">{activeScenario.timeControl}</span>
              </div>
              <div className="space-y-1 text-slate-200">
                <p className="text-base font-semibold">{activeScenario.event}</p>
                <p>
                  {activeScenario.players.white} (White) vs {activeScenario.players.black} (Black)
                </p>
              </div>
              <p>{activeScenario.summary}</p>
              <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">Move timeline</p>
                <ul className="mt-3 space-y-3">
                  {activeScenario.moves.map((move, index) => (
                    <li key={move.ply}>
                      <button
                        type="button"
                        onClick={() => goTo(index)}
                        className={`flex w-full items-start justify-between rounded-xl px-3 py-2 text-left transition ${
                          index === currentIndex
                            ? "bg-indigo-500/20 text-indigo-100"
                            : "hover:bg-white/10"
                        }`}
                      >
                        <span>
                          <span className="text-xs uppercase tracking-wide text-slate-400">Ply {move.ply}</span>
                          <span className="block text-sm font-semibold text-white">{move.move}</span>
                        </span>
                        <span className="text-xs text-slate-400">{move.evaluation}</span>
                      </button>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          )}
        </div>

        <div className="flex flex-col gap-6">
          <div className="rounded-3xl border border-white/10 bg-black/40 p-6">
            {activeMove ? (
              <>
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="text-xs uppercase tracking-wide text-slate-400">Move {currentIndex + 1}</p>
                    <h2 className="text-2xl font-semibold text-white">{activeMove.move}</h2>
                  </div>
                  <span className="rounded-full bg-white/10 px-3 py-1 text-xs font-semibold text-indigo-200">
                    Eval {activeMove.evaluation}
                  </span>
                </div>
                <div className="mt-6 flex flex-col gap-6 lg:flex-row">
                  <div className="mx-auto w-full max-w-sm">
                    <div className="grid aspect-square grid-cols-8 overflow-hidden rounded-3xl border border-white/10">
                      {board.map((rank, rankIndex) =>
                        rank.map((square, fileIndex) => {
                          const isDark = (rankIndex + fileIndex) % 2 === 1;
                          return (
                            <div
                              key={`${rankIndex}-${fileIndex}`}
                              className={`${
                                isDark ? "bg-slate-800" : "bg-slate-700/80"
                              } flex items-center justify-center text-2xl`}
                            >
                              <span>{pieceSymbols[square] ?? ""}</span>
                            </div>
                          );
                        }),
                      )}
                    </div>
                    <div className="mt-3 flex items-center justify-between text-xs text-slate-400">
                      <span>White to move</span>
                      <span>Engine similarity {activeMove.suspicion.split(" ")[0]}</span>
                    </div>
                  </div>
                  <div className="flex-1 space-y-4 text-sm text-slate-300">
                    <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
                      <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">Suspicion signal</p>
                      <p className="mt-2 text-slate-200">{activeMove.suspicion}</p>
                    </div>
                    <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
                      <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">Analyst commentary</p>
                      <p className="mt-2 leading-relaxed">{activeMove.commentary}</p>
                    </div>
                    <div className="flex gap-3">
                      <button
                        type="button"
                        onClick={() => goTo(currentIndex - 1)}
                        disabled={currentIndex === 0}
                        className="flex-1 rounded-full border border-white/20 px-4 py-2 text-sm font-semibold text-white transition enabled:hover:border-white/50 disabled:cursor-not-allowed disabled:border-white/10 disabled:text-slate-500"
                      >
                        Previous
                      </button>
                      <button
                        type="button"
                        onClick={() => goTo(currentIndex + 1)}
                        disabled={currentIndex === maxIndex}
                        className="flex-1 rounded-full bg-gradient-to-r from-indigo-500 to-violet-500 px-4 py-2 text-sm font-semibold text-white shadow-lg shadow-indigo-500/20 transition disabled:cursor-not-allowed disabled:from-indigo-500/40 disabled:to-violet-500/40"
                      >
                        Next
                      </button>
                    </div>
                  </div>
                </div>
              </>
            ) : (
              <div className="flex min-h-[300px] items-center justify-center text-sm text-slate-400">
                {loading ? "Loading board…" : "Select a move to inspect its context."}
              </div>
            )}
          </div>
          <div className="rounded-3xl border border-white/10 bg-indigo-500/10 p-6 text-sm text-indigo-100">
            <h3 className="text-lg font-semibold text-white">Shareable evidence packets</h3>
            <p className="mt-2">
              Export this investigation as a PDF or send a secure link to coaches and arbiters. Each packet includes video clips, biometric readings, and move-by-move comparisons.
            </p>
          </div>
        </div>
      </section>
    </div>
  );
}
