import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function ActivationWithoutTokenPage() {
  return <main className="grid min-h-screen place-items-center px-4 py-10">
    <Card className="w-full max-w-md">
      <CardHeader>
        <p className="text-sm font-semibold uppercase tracking-wider text-slate-500">IT Support Copilot</p>
        <CardTitle>Activation link required</CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-sm text-slate-600">Open the complete invitation link from your local delivery mailbox.</p>
      </CardContent>
    </Card>
  </main>;
}
