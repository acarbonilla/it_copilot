import type { Metadata } from "next";
import { ActivationBootstrap } from "@/components/activation-bootstrap";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export const metadata: Metadata = { title: "Activate account", referrer: "no-referrer" };

export default function ActivationPage() {
  return <main className="grid min-h-screen place-items-center px-4 py-10">
    <Card className="w-full max-w-md">
      <CardHeader>
        <p className="text-sm font-semibold uppercase tracking-wider text-slate-500">IT Support Copilot</p>
        <CardTitle>Activate your account</CardTitle>
        <p className="text-sm text-slate-600">Create your password to finish activation.</p>
      </CardHeader>
      <CardContent><ActivationBootstrap /></CardContent>
    </Card>
  </main>;
}
