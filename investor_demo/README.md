# ObserveOS Investor Demo

This is the standalone investor demo UI. It does not modify or depend on the
intern-owned Python modules.

## What Changed

- The old inline HTML demo was shifted into a TypeScript source app.
- The runnable browser bundle is in `dist/main.js`.
- Styling is in `src/styles.css`.
- The Operations view tries `/api/v1/health/` and falls back to sample state
  when a live backend is not wired.
- The demo uses:
  - TypeScript for typed state, rendering, and event handling.
  - GSAP for panel, toast, modal, and view animations.
  - Lenis for smooth scrolling.

## Run Immediately

Open from a local web server:

```powershell
python -m http.server 4173 -d investor_demo
```

Then visit:

```text
http://127.0.0.1:4173/
```

The committed `dist/main.js` runs directly. Internet access is needed for the
CDN-loaded GSAP and Lenis modules. If a CDN is unavailable, the demo falls
back to normal UI behavior.

## Optional Package Workflow

When frontend dependencies are installed:

```powershell
cd investor_demo
npm install
npm run check
npm run dev
```

`package-lock.json` is committed so demo installs are reproducible.

## Scope Boundary

The interns remain assigned to Python/backend/system modules. This TypeScript
demo is a separate product UI track for the investor presentation.

Sensitive production features stay represented as gated demo states until
consent, audit, retention, and legal review are completed.
