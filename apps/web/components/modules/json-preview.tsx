import { AlertTriangle, Download, FileJson } from "lucide-react";
import { b2cs as fallbackB2cs } from "@/lib/mock-data";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { formatCurrency } from "@/lib/utils";
import type { Gstr1Payload } from "@/lib/api";

export function JsonPreview({ payload, onGenerate }: { payload?: Gstr1Payload | null; onGenerate?: () => void }) {
  const b2cs = payload?.b2cs?.length ? payload.b2cs : fallbackB2cs;
  return (
    <Card id="gstr-1-json">
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle className="flex items-center gap-2"><FileJson className="size-4 text-primary" />GSTR-1 JSON Preview</CardTitle>
        <Button onClick={onGenerate}><Download className="size-4" />Generate JSON</Button>
      </CardHeader>
      <CardContent className="grid gap-6 lg:grid-cols-[1.3fr_0.7fr]">
        <div className="overflow-hidden rounded-lg border border-slate-200">
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-50 text-xs uppercase text-slate-500"><tr><th className="p-3">Supply</th><th className="p-3">Rate</th><th className="p-3">POS</th><th className="p-3">Taxable</th><th className="p-3">IGST</th><th className="p-3">CGST</th><th className="p-3">SGST</th></tr></thead>
            <tbody className="divide-y divide-slate-100">
              {b2cs.map((row) => <tr key={`${row.sply_ty}-${row.pos}-${row.rt}`}><td className="p-3">{row.sply_ty}</td><td className="p-3">{row.rt}%</td><td className="p-3">{row.pos}</td><td className="p-3">{formatCurrency(row.txval)}</td><td className="p-3">{row.iamt}</td><td className="p-3">{row.camt}</td><td className="p-3">{row.samt}</td></tr>)}
            </tbody>
          </table>
        </div>
        <div className="space-y-3">
          {[
            `SUPECO summary: ${payload?.supeco?.supeco_det?.length ?? 3} operator groups`,
            `Document issue: ${payload?.doc_issue?.doc_det?.length ?? 2} document groups ready`,
            `GSTIN: ${payload?.gstin ?? "07ABCDE1234F1Z5"}`,
            `Return period: ${payload?.fp ?? "042026"}`
          ].map((item) => <div key={item} className="rounded-lg bg-slate-50 p-3 text-sm text-slate-700">{item}</div>)}
          <div className="flex gap-2 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800"><AlertTriangle className="mt-0.5 size-4 shrink-0" />2 rows need ETIN or POS correction before final filing.</div>
        </div>
      </CardContent>
    </Card>
  );
}
