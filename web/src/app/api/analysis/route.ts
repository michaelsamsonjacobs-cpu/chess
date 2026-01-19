import { NextResponse } from "next/server";

type BoardRank = string;

type AnalysisMove = {
  ply: number;
  move: string;
  evaluation: string;
  suspicion: string;
  commentary: string;
  board: BoardRank[];
};

type AnalysisScenario = {
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
  moves: AnalysisMove[];
};

const scenarios: AnalysisScenario[] = [
  {
    id: "club-final",
    name: "Club Championship Final",
    summary:
      "Repeated depth-30 matches combined with sub-second move cadence point to outside assistance in a critical playoff game.",
    event: "City Rapid Finals, Board 1",
    timeControl: "15+5",
    players: {
      white: "IM L. Cho",
      black: "FM P. Ortega",
    },
    riskLevel: "Heightened",
    moves: [
      {
        ply: 55,
        move: "28...Qe5!!",
        evaluation: "-0.3",
        suspicion: "97% engine match and a 0.7s decision time.",
        commentary:
          "Black finds a forcing queen transfer that aligns with the engine's only top move. Time usage dropped well below the player's usual pace, triggering the first alert.",
        board: [
          "r..k..r.",
          ".pp.qp..",
          "...p.b..",
          "....p..p",
          "...P.P..",
          "..N..B..",
          "PP..Q.PP",
          "...R.K..",
        ],
      },
      {
        ply: 57,
        move: "29.Re1 Re8",
        evaluation: "-0.7",
        suspicion: "Second consecutive precision hit at depth 26.",
        commentary:
          "After White stabilizes, Black instantly mirrors the top Stockfish line, increasing the live risk score from 18% to 34%.",
        board: [
          "r..k.r..",
          ".pp.qp..",
          "...p.b..",
          "....p..p",
          "...P.P..",
          "..N..B..",
          "PP..Q.PP",
          "...RRK..",
        ],
      },
      {
        ply: 59,
        move: "30.Qg2 Qe3+",
        evaluation: "-1.4",
        suspicion: "Blunder chance below 2% given historical baseline.",
        commentary:
          "Black's queen conversion keeps up the pressure while preserving every tactical nuance. ChessGuard escalates the alert to the arbiter with supporting evidence clips.",
        board: [
          "r..k.r..",
          ".pp..p..",
          "...p.b..",
          "....p..p",
          "...P.P..",
          "..N.qB..",
          "PP..Q.PQ",
          "...RRK..",
        ],
      },
      {
        ply: 61,
        move: "31.Rf1 Qd4+",
        evaluation: "-2.6",
        suspicion: "Threat score crosses 70% confidence threshold.",
        commentary:
          "The system highlights the forcing mate net and recommends a floor-judge intervention. Players are separated and devices inspected.",
        board: [
          "r..k.r..",
          ".pp..p..",
          "...p.b..",
          "....p..p",
          "...q.P..",
          "..N..B..",
          "PP..Q.PQ",
          "...RRK..",
        ],
      },
    ],
  },
  {
    id: "junior-open",
    name: "Junior Open Round 6",
    summary:
      "A young player's rapid-fire accuracy is flagged, but contextual data keeps the case in a monitoring state for review.",
    event: "State Junior Open",
    timeControl: "10+0",
    players: {
      white: "WCM R. Banerjee",
      black: "A. Nguyen",
    },
    riskLevel: "Stable",
    moves: [
      {
        ply: 35,
        move: "18.Bxf7+ Kxf7",
        evaluation: "+0.4",
        suspicion: "Clean tactical conversion following a pre-built prep line.",
        commentary:
          "White sacrifices on f7—prep reported by the coach pre-event. ChessGuard logs the tactic but keeps the risk score low thanks to the shared opening file.",
        board: [
          "r.bq.nr.",
          ".ppp.kpp",
          "..n.....",
          "p..p.p..",
          "..PP.P..",
          "P.P...NP",
          ".R.BQP.B",
          "...R.K..",
        ],
      },
      {
        ply: 37,
        move: "19.Qd5+ Qe6",
        evaluation: "+1.1",
        suspicion: "0.95 evaluation swing captured with normal cadence.",
        commentary:
          "The follow-up forces Black's king to the center. Sensor data shows regular breathing rate, supporting a legitimate sequence.",
        board: [
          "r.b..r.",
          ".ppp.kpp",
          "..n.q...",
          "p..PQp..",
          "..P..P..",
          "P.P...NP",
          ".R.B.R.B",
          "...R.K..",
        ],
      },
      {
        ply: 39,
        move: "20.Rae1 Qxd5",
        evaluation: "+0.6",
        suspicion: "Engine match under 65%; alert auto-dismissed.",
        commentary:
          "Once queens come off, accuracy normalizes. ChessGuard documents the surge and shares a post-round confidence summary with coaches.",
        board: [
          "r.b..r.",
          ".ppp.kpp",
          "..n.....",
          "p..qRp..",
          "..P..P..",
          "P.P...NP",
          ".R.B.R.B",
          "...R.K..",
        ],
      },
    ],
  },
];

export async function GET() {
  return NextResponse.json({ scenarios });
}
