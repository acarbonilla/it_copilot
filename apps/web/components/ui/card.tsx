import * as React from "react";
import { cn } from "@/lib/utils";

export function Card({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) { return <div className={cn("rounded-xl border border-slate-200 bg-white shadow-sm", className)} {...props} />; }
export function CardHeader(props: React.HTMLAttributes<HTMLDivElement>) { return <div className="space-y-1.5 p-6" {...props} />; }
export function CardTitle(props: React.HTMLAttributes<HTMLHeadingElement>) { return <h2 className="text-xl font-semibold" {...props} />; }
export function CardContent(props: React.HTMLAttributes<HTMLDivElement>) { return <div className="p-6 pt-0" {...props} />; }
