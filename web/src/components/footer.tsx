import Link from "next/link";

const resources = [
  {
    title: "Product",
    links: [
      { href: "/demo", label: "Live analysis demo" },
      { href: "/waitlist", label: "Request early access" },
    ],
  },
  {
    title: "Company",
    links: [
      { href: "mailto:hello@chessguard.ai", label: "Contact" },
      { href: "https://www.linkedin.com", label: "LinkedIn" },
    ],
  },
  {
    title: "Resources",
    links: [
      { href: "https://lichess.org/", label: "Trusted platforms" },
      { href: "https://www.fide.com/", label: "FIDE guidelines" },
    ],
  },
];

export function Footer() {
  return (
    <footer className="border-t border-white/10 bg-slate-950/80">
      <div className="mx-auto flex max-w-6xl flex-col gap-8 px-4 py-10 text-sm text-slate-300 sm:flex-row sm:justify-between sm:px-6">
        <div className="max-w-sm space-y-3">
          <p className="text-lg font-semibold text-white">ChessGuard</p>
          <p>
            Safeguarding competitive chess with integrity insights, anomaly detection, and coaching tools designed for clubs,
            leagues, and online platforms.
          </p>
        </div>
        <div className="grid flex-1 grid-cols-1 gap-6 sm:grid-cols-3">
          {resources.map((section) => (
            <div key={section.title}>
              <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-400">
                {section.title}
              </h3>
              <ul className="mt-3 space-y-2">
                {section.links.map((link) => (
                  <li key={link.href}>
                    <Link
                      href={link.href}
                      className="transition hover:text-white"
                    >
                      {link.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </div>
      <div className="border-t border-white/5 bg-black/40 py-4">
        <p className="mx-auto max-w-6xl px-4 text-xs text-slate-500 sm:px-6">
          © {new Date().getFullYear()} ChessGuard. All rights reserved.
        </p>
      </div>
    </footer>
  );
}
