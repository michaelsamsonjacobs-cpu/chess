"use client";

import { useState } from "react";
import type { FormEvent } from "react";

import Link from "next/link";

type FormState = {
  name: string;
  email: string;
  organization: string;
  message: string;
};

type SubmitState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "success"; reference: string }
  | { status: "error"; message: string };

const initialForm: FormState = {
  name: "",
  email: "",
  organization: "",
  message: "",
};

export default function WaitlistPage() {
  const [form, setForm] = useState<FormState>(initialForm);
  const [state, setState] = useState<SubmitState>({ status: "idle" });

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (state.status === "loading") return;

    setState({ status: "loading" });
    try {
      const response = await fetch("/api/waitlist", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(form),
      });

      if (!response.ok) {
        const error = await response.json().catch(() => ({ error: "Unable to submit" }));
        throw new Error(error.error ?? "Unable to submit");
      }

      const result = await response.json();
      setState({ status: "success", reference: result.reference });
      setForm(initialForm);
    } catch (err) {
      setState({ status: "error", message: err instanceof Error ? err.message : "Unexpected error" });
    }
  }

  function updateField(key: keyof FormState, value: string) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  return (
    <div className="mx-auto flex w-full max-w-5xl flex-col gap-12 px-4 pb-20 pt-16 sm:px-6 lg:pt-20">
      <div className="max-w-2xl space-y-4">
        <h1 className="text-4xl font-semibold text-white sm:text-5xl">Join the ChessGuard waitlist</h1>
        <p className="text-lg text-slate-300">
          We partner with federations, clubs, and digital platforms to deploy trustworthy integrity monitoring. Share a few
          details and our team will follow up within one business day.
        </p>
      </div>

      <section className="grid gap-8 lg:grid-cols-[3fr_2fr]">
        <form onSubmit={handleSubmit} className="space-y-6 rounded-3xl border border-white/10 bg-black/30 p-6">
          <div className="grid gap-4 sm:grid-cols-2">
            <label className="flex flex-col gap-2 text-sm text-slate-200">
              Full name
              <input
                type="text"
                required
                value={form.name}
                onChange={(event) => updateField("name", event.target.value)}
                placeholder="Alex Carter"
                className="rounded-2xl border border-white/10 bg-slate-950/80 px-4 py-3 text-sm text-white focus:border-indigo-400"
              />
            </label>
            <label className="flex flex-col gap-2 text-sm text-slate-200">
              Work email
              <input
                type="email"
                required
                value={form.email}
                onChange={(event) => updateField("email", event.target.value)}
                placeholder="you@organization.com"
                className="rounded-2xl border border-white/10 bg-slate-950/80 px-4 py-3 text-sm text-white focus:border-indigo-400"
              />
            </label>
          </div>
          <label className="flex flex-col gap-2 text-sm text-slate-200">
            Organization
            <input
              type="text"
              value={form.organization}
              onChange={(event) => updateField("organization", event.target.value)}
              placeholder="National Scholastic Federation"
              className="rounded-2xl border border-white/10 bg-slate-950/80 px-4 py-3 text-sm text-white focus:border-indigo-400"
            />
          </label>
          <label className="flex flex-col gap-2 text-sm text-slate-200">
            How can we help?
            <textarea
              required
              value={form.message}
              onChange={(event) => updateField("message", event.target.value)}
              placeholder="Tell us about your upcoming events, online platform, or compliance goals."
              className="min-h-[140px] rounded-2xl border border-white/10 bg-slate-950/80 px-4 py-3 text-sm text-white focus:border-indigo-400"
            />
          </label>

          {state.status === "error" && (
            <p className="rounded-2xl bg-rose-500/10 px-4 py-3 text-sm text-rose-200">{state.message}</p>
          )}

          {state.status === "success" && (
            <div className="rounded-2xl border border-emerald-400/30 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-100">
              Thank you! Your request ({state.reference}) is confirmed. A ChessGuard specialist will reach out shortly.
            </div>
          )}

          <button
            type="submit"
            disabled={state.status === "loading"}
            className="inline-flex w-full items-center justify-center rounded-full bg-gradient-to-r from-indigo-500 to-violet-500 px-6 py-3 text-sm font-semibold text-white shadow-lg shadow-indigo-500/20 transition disabled:cursor-not-allowed disabled:from-indigo-500/40 disabled:to-violet-500/40"
          >
            {state.status === "loading" ? "Submitting…" : "Request access"}
          </button>
          <p className="text-xs text-slate-500">
            By submitting, you agree to receive onboarding information and fair play best practices from ChessGuard. No spam—we
            promise.
          </p>
        </form>
        <aside className="space-y-6">
          <div className="rounded-3xl border border-white/10 bg-white/5 p-6 text-sm text-slate-200">
            <h2 className="text-lg font-semibold text-white">What to expect</h2>
            <ul className="mt-3 space-y-3 text-slate-300">
              <li>• Discovery call with a ChessGuard integrity specialist.</li>
              <li>• Custom scoring model aligned to your player pool.</li>
              <li>• Launch plan covering data ingestion and stakeholder training.</li>
            </ul>
          </div>
          <div className="rounded-3xl border border-white/10 bg-black/30 p-6 text-sm text-slate-200">
            <h2 className="text-lg font-semibold text-white">Prefer email?</h2>
            <p className="mt-2 text-slate-300">Reach us directly and we will respond within one business day.</p>
            <Link
              href="mailto:hello@chessguard.ai"
              className="mt-4 inline-flex items-center justify-center rounded-full border border-white/20 px-5 py-2 text-sm font-semibold text-white transition hover:border-white/50"
            >
              hello@chessguard.ai
            </Link>
          </div>
        </aside>
      </section>
    </div>
  );
}
