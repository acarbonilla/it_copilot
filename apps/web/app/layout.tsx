import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = { title: "IT Support Copilot", description: "Secure IT support workspace" };

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body className="min-h-screen antialiased">{children}</body></html>;
}
