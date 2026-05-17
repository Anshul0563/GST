"use client";

import { useMemo, useState } from "react";
import { ColumnDef, flexRender, getCoreRowModel, getFilteredRowModel, useReactTable } from "@tanstack/react-table";
import { Edit3, RefreshCcw, Search, Trash2 } from "lucide-react";
import { transactions as fallbackTransactions } from "@/lib/mock-data";
import type { Transaction } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { formatCurrency } from "@/lib/utils";

type Txn = Transaction;

export function TransactionsTable({ rows }: { rows?: Transaction[] }) {
  const [globalFilter, setGlobalFilter] = useState("");
  const data = (rows?.length ? rows : fallbackTransactions.map((row, index) => ({ id: index + 1, gstin: "", etin: null, filing_period: "042026", order_item_id: null, buyer_state_name: null, product_name: null, sku: null, qty: 1, cess: 0, gross_amount: 0, discount_seller: 0, discount_platform: 0, settlement_amount: 0, validation_status: "valid", validation_errors: null, ...row }))) as Transaction[];
  const columns = useMemo<ColumnDef<Txn>[]>(() => [
    { accessorKey: "platform", header: "Platform" },
    { accessorKey: "invoice_no", header: "Invoice number" },
    { accessorKey: "order_id", header: "Order ID" },
    { accessorKey: "invoice_date", header: "Date" },
    { accessorKey: "buyer_state_code", header: "State/POS" },
    { accessorKey: "hsn", header: "HSN" },
    { accessorKey: "taxable_value", header: "Taxable value", cell: ({ row }) => formatCurrency(Number(row.original.taxable_value)) },
    { accessorKey: "gst_rate", header: "GST rate", cell: ({ row }) => `${row.original.gst_rate}%` },
    { accessorKey: "igst", header: "IGST" },
    { accessorKey: "cgst", header: "CGST" },
    { accessorKey: "sgst", header: "SGST" },
    { accessorKey: "tcs", header: "TCS" },
    { accessorKey: "tds", header: "TDS" },
    { accessorKey: "doc_type", header: "Doc type" },
    { accessorKey: "source_file", header: "Source file" },
    { id: "actions", header: "", cell: () => <div className="flex gap-1"><Button variant="ghost" size="icon" title="Edit row"><Edit3 className="size-4" /></Button><Button variant="ghost" size="icon" title="Delete row"><Trash2 className="size-4" /></Button></div> }
  ], []);
  const table = useReactTable({ data, columns, state: { globalFilter }, onGlobalFilterChange: setGlobalFilter, getCoreRowModel: getCoreRowModel(), getFilteredRowModel: getFilteredRowModel() });

  return (
    <Card id="manage-data">
      <CardHeader className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <CardTitle>Merged Transaction Database</CardTitle>
        <div className="flex flex-wrap gap-2">
          <div className="relative w-64"><Search className="absolute left-3 top-2.5 size-4 text-slate-400" /><Input className="pl-9" placeholder="Search invoices, orders, states" value={globalFilter} onChange={(event) => setGlobalFilter(event.target.value)} /></div>
          <select className="h-10 rounded-lg border border-slate-200 px-3 text-sm"><option>All platforms</option><option>Amazon</option><option>Flipkart</option><option>Meesho</option></select>
          <select className="h-10 rounded-lg border border-slate-200 px-3 text-sm"><option>All GST rates</option><option>3%</option><option>5%</option><option>18%</option></select>
          <Button variant="outline"><RefreshCcw className="size-4" />Recalculate GST</Button>
          <Button variant="secondary">Export error rows</Button>
        </div>
      </CardHeader>
      <CardContent>
        <div className="table-scroll overflow-x-auto">
          <table className="min-w-[1400px] text-left text-sm">
            <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
              {table.getHeaderGroups().map((headerGroup) => (
                <tr key={headerGroup.id}>{headerGroup.headers.map((header) => <th key={header.id} className="whitespace-nowrap px-3 py-3 font-semibold">{flexRender(header.column.columnDef.header, header.getContext())}</th>)}</tr>
              ))}
            </thead>
            <tbody className="divide-y divide-slate-100">
              {table.getRowModel().rows.map((row) => (
                <tr key={row.id} className="hover:bg-slate-50">{row.getVisibleCells().map((cell) => <td key={cell.id} className="whitespace-nowrap px-3 py-3 text-slate-700">{flexRender(cell.column.columnDef.cell, cell.getContext())}</td>)}</tr>
              ))}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  );
}
