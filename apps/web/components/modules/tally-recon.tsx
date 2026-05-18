import { ArrowRightLeft, BookOpenCheck, Download, Settings2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

const ledgers = ["Sales ledger", "IGST ledger", "CGST ledger", "SGST ledger", "TCS ledger", "TDS ledger", "Discount ledger", "Round-off ledger", "Party ledger", "Stock item", "UQC"];

export function TallyRecon() {
  return (
    <div className="grid gap-6 xl:grid-cols-2">
      <Card id="ecom-to-tally">
        <CardHeader><CardTitle className="flex items-center gap-2"><BookOpenCheck className="size-4 text-primary" />eCom to Tally XML</CardTitle></CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-3 md:grid-cols-2">
            <div><Label>Tally company</Label><Input placeholder="Select or add company" /></div>
            <div><Label>Return period</Label><Input placeholder="Return period from GST profile" /></div>
          </div>
          <div className="grid gap-3 md:grid-cols-2">
            {ledgers.map((ledger) => <div key={ledger}><Label>{ledger}</Label><Input placeholder={ledger.replace(" ledger", "")} /></div>)}
          </div>
          <div className="flex gap-2"><Button><Settings2 className="size-4" />Generate XML</Button><Button variant="outline"><Download className="size-4" />Download</Button></div>
        </CardContent>
      </Card>
      <Card id="2a2b-recon">
        <CardHeader><CardTitle className="flex items-center gap-2"><ArrowRightLeft className="size-4 text-primary" />2A/2B Reconciliation</CardTitle></CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-3 md:grid-cols-2">
            <div><Label>GST portal 2A/2B file</Label><Input type="file" /></div>
            <div><Label>Purchase register Excel</Label><Input type="file" /></div>
          </div>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-3">
            {["Matched", "Amount mismatch", "Invoice mismatch", "Missing in 2B", "Missing in books", "Pending"].map((item) => <div key={item} className="rounded-lg bg-slate-50 p-4"><p className="text-xl font-bold text-slate-950">0</p><p className="text-xs text-slate-500">{item}</p></div>)}
          </div>
          <Button variant="secondary"><Download className="size-4" />Export reconciliation Excel</Button>
        </CardContent>
      </Card>
    </div>
  );
}
