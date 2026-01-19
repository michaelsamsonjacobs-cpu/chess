import Link from "next/link";

const features = [
  {
    title: "Live integrity scoring",
    description:
      "Blend engine-move matching, time usage, and behavioural signals into a single trust score that updates after every move.",
    icon: (
      <svg viewBox="0 0 24 24" fill="none" className="h-6 w-6 text-indigo-400">
        <path
          d="M12 3l8 4v6c0 5-3 8-8 8s-8-3-8-8V7l8-4z"
          stroke="currentColor"
          strokeWidth="1.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        <path
          d="M9 12l2 2 4-4"
          stroke="currentColor"
          strokeWidth="1.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    ),
  },
  {
    title: "Explainable alerts",
    description:
      "Drill into engine comparisons, historical baselines, and suspicious time swings with analyst-ready commentary for each event.",
    icon: (
      <svg viewBox="0 0 24 24" fill="none" className="h-6 w-6 text-indigo-400">
        <path
          d="M12 3a9 9 0 100 18 9 9 0 000-18z"
          stroke="currentColor"
          strokeWidth="1.5"
        />
        <path
          d="M9 10h6M9 14h3"
          stroke="currentColor"
          strokeWidth="1.5"
          strokeLinecap="round"
        />
        <path
          d="M12 6v1M12 17v1"
          stroke="currentColor"
          strokeWidth="1.5"
          strokeLinecap="round"
        />
      </svg>
    ),
  },
  {
    title: "Coaching insights",
    description:
      "Share annotated clips, accuracy trends, and recommended study lines directly with players after each event.",
    icon: (
      <svg viewBox="0 0 24 24" fill="none" className="h-6 w-6 text-indigo-400">
        <path
          d="M5 5h14l-1 12H6L5 5z"
          stroke="currentColor"
          strokeWidth="1.5"
          strokeLinejoin="round"
        />
        <path
          d="M9 9h6"
          stroke="currentColor"
          strokeWidth="1.5"
          strokeLinecap="round"
        />
        <path
          d="M12 17v2"
          stroke="currentColor"
          strokeWidth="1.5"
          strokeLinecap="round"
        />
      </svg>
    ),
  },
];

const steps = [
  {
    title: "Ingest",
    description:
      "Stream PGN, board cameras, or Lichess/Chess.com API feeds securely into ChessGuard from on-site or online events.",
  },
  {
    title: "Detect",
    description:
      "Our engine farm benchmarks every move against peer cohorts, timing models, and device telemetry to surface anomalies.",
  },
  {
    title: "Act",
    description:
      "Trigger director alerts, auto-generate fair play reports, or push guidance to coaches with one click.",
  },
];

const useCases = [
  {
    name: "Scholastic leagues",
    detail:
      "Run weekend events without extra staff. ChessGuard spots aberrations so TDs can focus on creating great experiences.",
  },
  {
    name: "Elite tournaments",
    detail:
      "Back up critical rulings with defensible evidence packages trusted by arbiters and broadcast partners alike.",
  },
  {
    name: "Online platforms",
    detail:
      "Deploy API-first detection with scoring tuned to your rating pools, time controls, and anti-abuse policies.",
  },
];

export default function Home() {
  return (
    <div className="mx-auto flex w-full max-w-6xl flex-col gap-24 px-4 pb-20 pt-16 sm:px-6 lg:pt-24">
      <section className="grid gap-16 lg:grid-cols-[3fr_2fr] lg:items-center">
        <div className="space-y-8">
          <span className="inline-flex items-center gap-2 rounded-full bg-white/10 px-4 py-2 text-sm font-medium text-indigo-200">
            <span className="h-2 w-2 rounded-full bg-emerald-400" aria-hidden />
            Trusted insights for directors & coaches
          </span>
          <div className="space-y-6">
            <h1 className="text-4xl font-semibold tracking-tight text-white sm:text-5xl lg:text-6xl">
              Safeguard every move with ChessGuard intelligence.
            </h1>
            <p className="text-lg text-slate-300 sm:text-xl">
              Monitor games in real time, quantify risk, and brief stakeholders with explainable data stories—all in a single,
              battle-tested workflow.
            </p>
          </div>
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center">
            <Link
              href="/demo"
              className="inline-flex items-center justify-center rounded-full bg-gradient-to-r from-indigo-500 to-violet-500 px-6 py-3 text-sm font-semibold text-white shadow-xl shadow-indigo-500/30 transition hover:from-indigo-400 hover:to-violet-400"
            >
              Explore the live demo
            </Link>
            <Link
              href="/waitlist"
              className="inline-flex items-center justify-center rounded-full border border-white/20 px-6 py-3 text-sm font-semibold text-white transition hover:border-white/50"
            >
              Join the early access list
            </Link>
          </div>
          <div className="grid gap-4 text-sm text-slate-300 sm:grid-cols-2">
            <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
              <p className="text-2xl font-semibold text-white">98.7%</p>
              <p className="mt-2 text-slate-400">Average precision across 40k+ adjudicated games.</p>
            </div>
            <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
              <p className="text-2xl font-semibold text-white">90s</p>
              <p className="mt-2 text-slate-400">Median time-to-alert for over-the-board events.</p>
            </div>
          </div>
        </div>
        <div className="relative flex justify-center lg:justify-end">
          <div className="relative w-full max-w-md rounded-3xl border border-white/10 bg-gradient-to-br from-slate-900 to-slate-950 p-6 shadow-2xl shadow-indigo-500/20">
            <div className="flex items-center justify-between text-xs uppercase tracking-wide text-slate-400">
              <span>LIVE DASHBOARD</span>
              <span>ChessGuard v3.2</span>
            </div>
            <div className="mt-6 grid grid-cols-2 gap-4 text-sm">
              <div className="rounded-2xl border border-white/5 bg-black/40 p-4">
                <p className="text-xs uppercase tracking-wide text-indigo-300">Risk score</p>
                <p className="mt-3 text-4xl font-semibold text-white">12%</p>
                <p className="mt-2 text-xs text-slate-400">Below event average</p>
              </div>
              <div className="rounded-2xl border border-white/5 bg-black/40 p-4">
                <p className="text-xs uppercase tracking-wide text-indigo-300">Engine match</p>
                <p className="mt-3 text-4xl font-semibold text-white">87%</p>
                <p className="mt-2 text-xs text-slate-400">Alert threshold: 93%</p>
              </div>
              <div className="col-span-2 rounded-2xl border border-white/5 bg-black/40 p-4">
                <p className="text-xs uppercase tracking-wide text-indigo-300">Latest finding</p>
                <p className="mt-2 font-semibold text-white">Round 4 vs. GM Keller</p>
                <p className="mt-1 text-xs text-slate-400">
                  Move 23...Nc5 matched depth-30 engine line with 0.2s think time. Flagged for human review.
                </p>
              </div>
            </div>
            <div className="mt-6 flex items-center justify-between rounded-2xl border border-white/10 bg-black/60 px-4 py-3 text-xs text-slate-300">
              <span>Alert routing: Arbiters & coaches</span>
              <span className="rounded-full bg-emerald-500/20 px-3 py-1 text-emerald-300">Stable</span>
            </div>
          </div>
        </div>
      </section>

      <section className="space-y-12">
        <div className="max-w-2xl">
          <h2 className="text-3xl font-semibold text-white sm:text-4xl">Everything directors need in one workspace.</h2>
          <p className="mt-3 text-lg text-slate-300">
            Tailored dashboards combine statistical rigor with storytelling so you can respond decisively in moments that
            matter.
          </p>
        </div>
        <div className="grid gap-6 md:grid-cols-3">
          {features.map((feature) => (
            <div
              key={feature.title}
              className="flex h-full flex-col gap-4 rounded-3xl border border-white/10 bg-black/40 p-6 text-sm text-slate-300"
            >
              <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-indigo-500/10 text-indigo-400">
                {feature.icon}
              </div>
              <div className="space-y-2">
                <h3 className="text-lg font-semibold text-white">{feature.title}</h3>
                <p>{feature.description}</p>
              </div>
            </div>
          ))}
        </div>
      </section>

      <section className="grid gap-10 lg:grid-cols-[2fr_3fr] lg:items-start">
        <div className="space-y-4">
          <h2 className="text-3xl font-semibold text-white sm:text-4xl">How ChessGuard keeps games fair.</h2>
          <p className="text-lg text-slate-300">
            Built with arbiters and platform operators, ChessGuard orchestrates collection, scoring, and reporting so you can
            focus on the players.
          </p>
        </div>
        <div className="grid gap-4">
          {steps.map((step, index) => (
            <div
              key={step.title}
              className="flex flex-col gap-3 rounded-3xl border border-white/10 bg-black/30 p-6 text-sm text-slate-300 shadow-lg shadow-indigo-500/5"
            >
              <span className="inline-flex h-10 w-10 items-center justify-center rounded-2xl bg-indigo-500/20 text-base font-semibold text-indigo-200">
                {index + 1}
              </span>
              <div>
                <h3 className="text-lg font-semibold text-white">{step.title}</h3>
                <p className="mt-1">{step.description}</p>
              </div>
            </div>
          ))}
        </div>
      </section>

      <section className="space-y-10">
        <div className="grid gap-6 md:grid-cols-[2fr_3fr] md:items-end">
          <div className="space-y-3">
            <h2 className="text-3xl font-semibold text-white sm:text-4xl">Made for the entire chess ecosystem.</h2>
            <p className="text-lg text-slate-300">
              Flexible deployment models and role-based access mean ChessGuard grows with your organization.
            </p>
          </div>
          <p className="text-sm text-slate-400">
            &ldquo;ChessGuard let us adjudicate suspicious games in minutes instead of hours, while sharing transparent feedback
            with our players.&rdquo; — Midwest Collegiate League Director
          </p>
        </div>
        <div className="grid gap-6 md:grid-cols-3">
          {useCases.map((useCase) => (
            <div key={useCase.name} className="rounded-3xl border border-white/10 bg-black/30 p-6 text-sm text-slate-300">
              <h3 className="text-lg font-semibold text-white">{useCase.name}</h3>
              <p className="mt-2">{useCase.detail}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="rounded-3xl border border-white/10 bg-gradient-to-r from-indigo-500/20 via-violet-500/20 to-fuchsia-500/20 p-10 text-center shadow-[0_24px_80px_-48px_rgba(129,140,248,0.6)]">
        <h2 className="text-3xl font-semibold text-white sm:text-4xl">Ready to deliver trusted events?</h2>
        <p className="mt-3 text-lg text-slate-200">
          Join the waitlist to collaborate with our product team and tailor ChessGuard to your federation or platform.
        </p>
        <div className="mt-6 flex flex-col items-center justify-center gap-4 sm:flex-row">
          <Link
            href="/waitlist"
            className="inline-flex items-center justify-center rounded-full bg-white px-6 py-3 text-sm font-semibold text-slate-900 transition hover:bg-slate-200"
          >
            Request a strategy session
          </Link>
          <Link
            href="mailto:hello@chessguard.ai"
            className="inline-flex items-center justify-center rounded-full border border-white/20 px-6 py-3 text-sm font-semibold text-white transition hover:border-white/50"
          >
            hello@chessguard.ai
          </Link>
        </div>
      </section>
    </div>
  );
}
