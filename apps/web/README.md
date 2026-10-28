# Web application

IC-005 implements the Next.js App Router shell with TypeScript, Tailwind CSS,
shadcn/ui-style primitives, and Django session authentication.

## Windows setup

From `apps/web`:

```powershell
npm install
npm run dev
```

The frontend runs at `http://localhost:3000` and expects Django at
`http://localhost:8000`. Override the API origin only when required with
`NEXT_PUBLIC_API_BASE_URL`. Run `npm run typecheck`, `npm run lint`, `npm test`,
and `npm run build` before submitting changes. Never store passwords, session
identifiers, or CSRF values in browser storage.

## Activation-token boundary

The IC-006 link uses `/activate/[token]`, so the initial local HTTP request and
Next.js server receive the token in the path. Next.js serializes the token in
the client-component hydration payload even though it is not rendered as
visible text. After hydration, the form replaces the browser history URL with
the tokenless `/activate` fallback; after success it replaces that entry with
`/login`. `Referrer-Policy: no-referrer` and the absence of third-party assets
prevent outgoing referrer disclosure.

These mitigations do not remove the initial URL from browser network/devtools,
the server-rendered response source, process memory, or upstream access logs.
The flow is therefore local-MVP only. Do not enable request-path logging for
activation URLs, and require explicit redaction before any hosted deployment.

