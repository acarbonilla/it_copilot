"use client";

import { useLayoutEffect, useState } from "react";
import { ActivationForm } from "@/components/activation-form";

const TOKEN_PATTERN = /^[A-Za-z0-9_-]{43}$/;

export function ActivationBootstrap() {
  const [token, setToken] = useState<string | null>(null);
  const [ready, setReady] = useState(false);

  useLayoutEffect(() => {
    const fragment = window.location.hash;
    // Scrub before setting component state or allowing password entry.
    window.history.replaceState(window.history.state, "", "/activate");
    const match = /^#token=([A-Za-z0-9_-]{43})$/.exec(fragment);
    // Fragment access is necessarily post-hydration; keep the secret out of SSR props.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (match && TOKEN_PATTERN.test(match[1])) setToken(match[1]);
    setReady(true);
  }, []);

  if (!ready) return <p className="text-sm text-slate-600">Preparing activation…</p>;
  if (!token) return <p role="alert" className="text-sm text-slate-600">This activation link is invalid or has expired.</p>;
  return <ActivationForm token={token} />;
}
