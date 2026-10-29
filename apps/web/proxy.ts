const LEGACY_REJECTION = "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\"><meta name=\"robots\" content=\"noindex\"><title>Activation link invalid</title></head><body><main><h1>Activation link invalid</h1><p>This activation link is invalid or has expired.</p></main></body></html>";

export function proxy() {
  return new Response(LEGACY_REJECTION, {
    status: 404,
    headers: {
      "Cache-Control": "no-store",
      "Content-Type": "text/html; charset=utf-8",
      "Referrer-Policy": "no-referrer",
      "X-Robots-Tag": "noindex",
    },
  });
}

export const config = { matcher: "/activate/:legacyToken+" };
