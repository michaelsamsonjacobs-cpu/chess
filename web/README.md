# ChessGuard Web Experience

This Next.js + TypeScript application powers the ChessGuard marketing site and interactive analysis demo. It provides:

- A brand-focused landing page that introduces ChessGuard's integrity analytics platform.
- A live gameplay analysis simulator backed by mock API endpoints that mirror arbiter workflows.
- A waitlist form connected to a mock submission API to capture high-intent leads.

## Getting started

```bash
cd web
npm install
npm run dev
```

Visit [http://localhost:3000](http://localhost:3000) to explore the experience. The demo page fetches scenarios from `/api/analysis` and the waitlist form posts data to `/api/waitlist`.

## Available scripts

- `npm run dev` – start the Turbopack development server.
- `npm run build` – create an optimized production build.
- `npm run start` – serve the production build.
- `npm run lint` – lint the project using the Next.js base configuration.

## Project structure

```
web/
├─ src/app/
│  ├─ page.tsx           # Landing page
│  ├─ demo/page.tsx      # Gameplay analysis demo
│  ├─ waitlist/page.tsx  # Waitlist & contact form
│  └─ api/
│     ├─ analysis/       # Mock analysis scenarios
│     └─ waitlist/       # Mock waitlist submission handler
├─ src/components/       # Shared layout components
└─ public/              # Static assets for illustrations and icons
```

## Mock integrations

The mock API routes live under `src/app/api/` and are implemented with the Next.js App Router. They simulate realistic latency, validations, and payloads so that the user flows feel production-ready without relying on external services.
