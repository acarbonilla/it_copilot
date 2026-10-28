import type { Metadata } from "next";
import { ActivationForm } from "@/components/activation-form";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export const metadata: Metadata = { title: "Activate account", referrer: "no-referrer" };

export default async function ActivationPage({ params }: { params: Promise<{ token: string }> }) {
  const { token } = await params;
  return <main className="grid min-h-screen place-items-center px-4 py-10">
    <Card className="w-full max-w-md">
      <CardHeader>
        <p className="text-sm font-semibold uppercase tracking-wider text-slate-500">IT Support Copilot</p>
        <CardTitle>Activate your account</CardTitle>
        <p className="text-sm text-slate-600">Create your password to finish activation.</p>
      </CardHeader>
      <CardContent><ActivationForm token={token} /></CardContent>
    </Card>
  </main>;
}
