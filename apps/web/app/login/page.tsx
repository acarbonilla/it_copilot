import { LoginForm } from "@/components/login-form";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function LoginPage() {
  return <main className="grid min-h-screen place-items-center px-4 py-10"><Card className="w-full max-w-md"><CardHeader><p className="text-sm font-semibold uppercase tracking-wider text-slate-500">IT Support Copilot</p><CardTitle>Welcome back</CardTitle><p className="text-sm text-slate-600">Sign in with your organization account.</p></CardHeader><CardContent><LoginForm /></CardContent></Card></main>;
}
