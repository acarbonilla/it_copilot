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

