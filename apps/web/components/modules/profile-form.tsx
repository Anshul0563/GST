"use client";

import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { Building2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { Profile } from "@/lib/api";

const schema = z.object({
  gstin: z.string().length(15),
  legal_name: z.string().min(2),
  trade_name: z.string().optional(),
  filing_frequency: z.enum(["Monthly", "Quarterly"]),
  financial_year: z.string().min(7),
  return_period: z.string().length(6)
});

export function ProfileForm({ profile, onSave }: { profile?: Profile | null; onSave?: (payload: z.infer<typeof schema>) => Promise<void> | void }) {
  const form = useForm<z.infer<typeof schema>>({
    resolver: zodResolver(schema),
    values: {
      gstin: profile?.gstin || "",
      legal_name: profile?.legal_name || "",
      trade_name: profile?.trade_name || "",
      filing_frequency: (profile?.filing_frequency as "Monthly" | "Quarterly") || "Monthly",
      financial_year: profile?.financial_year || "2026-27",
      return_period: profile?.return_period || "042026"
    }
  });
  const gstin = form.watch("gstin");
  return (
    <Card id="gst-profile">
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle className="flex items-center gap-2"><Building2 className="size-4 text-primary" />GST Profile</CardTitle>
        <span className="rounded-md bg-slate-100 px-2 py-1 text-xs text-slate-600">State code: {gstin?.slice(0, 2) || "--"}</span>
      </CardHeader>
      <CardContent>
        <form className="grid gap-4 md:grid-cols-3" onSubmit={form.handleSubmit(async (values) => onSave?.(values))}>
          <div><Label>GSTIN</Label><Input {...form.register("gstin")} /></div>
          <div><Label>Legal name</Label><Input {...form.register("legal_name")} /></div>
          <div><Label>Trade name</Label><Input {...form.register("trade_name")} /></div>
          <div><Label>Filing frequency</Label><select className="h-10 w-full rounded-lg border border-slate-200 px-3 text-sm" {...form.register("filing_frequency")}><option>Monthly</option><option>Quarterly</option></select></div>
          <div><Label>Financial year</Label><Input {...form.register("financial_year")} /></div>
          <div><Label>Return period</Label><Input {...form.register("return_period")} /></div>
          <div className="md:col-span-3"><Button type="submit">Save profile</Button></div>
        </form>
      </CardContent>
    </Card>
  );
}
