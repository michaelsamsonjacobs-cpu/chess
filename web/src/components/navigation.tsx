"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";

const links = [
  { href: "/", label: "Overview" },
  { href: "/demo", label: "Analysis Demo" },
  { href: "/experiment/play", label: "Engine Session" },
  { href: "/waitlist", label: "Waitlist" },
];

export function NavBar() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);

  const toggle = () => setOpen((prev) => !prev);

  return (
    <header className="sticky top-0 z-50 backdrop-blur border-b border-white/5 bg-slate-950/80">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-4 sm:px-6">
        <Link href="/" className="flex items-center gap-2 text-lg font-semibold text-white">
          <span className="inline-flex h-8 w-8 items-center justify-center rounded-full bg-gradient-to-br from-violet-500 to-indigo-500 text-sm font-semibold text-white">
            CG
          </span>
          <span className="hidden sm:inline">ChessGuard</span>
        </Link>
        <nav className="hidden items-center gap-1 text-sm font-medium text-slate-200 md:flex">
          {links.map((link) => {
            const isActive = pathname === link.href;
            return (
              <Link
                key={link.href}
                href={link.href}
                className={`rounded-full px-4 py-2 transition-colors ${
                  isActive
                    ? "bg-white/10 text-white shadow-sm"
                    : "text-slate-300 hover:bg-white/10 hover:text-white"
                }`}
              >
                {link.label}
              </Link>
            );
          })}
          <Link
            href="/waitlist"
            className="ml-2 rounded-full bg-gradient-to-r from-violet-500 to-indigo-500 px-4 py-2 text-white shadow-lg shadow-indigo-500/20 transition hover:from-violet-400 hover:to-indigo-400"
          >
            Request Access
          </Link>
        </nav>
        <button
          type="button"
          onClick={toggle}
          className="flex h-10 w-10 items-center justify-center rounded-full border border-white/10 text-slate-200 transition hover:border-white/30 md:hidden"
          aria-expanded={open}
          aria-controls="mobile-nav"
        >
          <span className="sr-only">Toggle navigation</span>
          <svg
            className="h-5 w-5"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            {open ? (
              <path d="M6 6l12 12M6 18L18 6" />
            ) : (
              <>
                <path d="M4 6h16" />
                <path d="M4 12h16" />
                <path d="M4 18h16" />
              </>
            )}
          </svg>
        </button>
      </div>
      <div
        id="mobile-nav"
        className={`border-t border-white/5 bg-slate-950/95 transition-[max-height,opacity] duration-300 md:hidden ${
          open ? "max-h-96 opacity-100" : "max-h-0 overflow-hidden opacity-0"
        }`}
      >
        <div className="space-y-2 px-4 py-4 text-sm font-medium text-slate-200">
          {links.map((link) => {
            const isActive = pathname === link.href;
            return (
              <Link
                key={link.href}
                href={link.href}
                onClick={() => setOpen(false)}
                className={`block rounded-xl px-3 py-2 ${
                  isActive
                    ? "bg-white/10 text-white"
                    : "text-slate-300 hover:bg-white/10 hover:text-white"
                }`}
              >
                {link.label}
              </Link>
            );
          })}
          <Link
            href="/waitlist"
            onClick={() => setOpen(false)}
            className="block rounded-xl bg-gradient-to-r from-violet-500 to-indigo-500 px-3 py-2 text-center font-semibold text-white shadow-lg shadow-indigo-500/20"
          >
            Request Access
          </Link>
        </div>
      </div>
    </header>
  );
}
