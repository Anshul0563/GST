import { BarChart3, Database, FileJson, Landmark, LayoutDashboard, ReceiptText, RefreshCcw, UploadCloud } from "lucide-react";

const items = [
  { icon: LayoutDashboard, label: "Dashboard" },
  { icon: Landmark, label: "GST Profile" },
  { icon: UploadCloud, label: "Marketplace Upload" },
  { icon: Database, label: "Manage Data" },
  { icon: FileJson, label: "GSTR-1 JSON" },
  { icon: ReceiptText, label: "GSTR-1 Excel" },
  { icon: BarChart3, label: "eCom to Tally" },
  { icon: RefreshCcw, label: "2A/2B Recon" }
];

export function Sidebar() {
  return (
    <aside className="hidden min-h-screen w-72 border-r border-slate-200 bg-white px-4 py-5 lg:block">
      <div className="flex items-center gap-3 px-2">
        <div className="flex size-11 items-center justify-center rounded-lg bg-primary text-lg font-bold text-white">GB</div>
        <div>
          <p className="text-lg font-bold text-slate-950">GST Bharat</p>
          <p className="text-xs text-slate-500">eCommerce GST automation</p>
        </div>
      </div>
      <nav className="mt-8 space-y-1">
        {items.map((item, index) => (
          <a key={item.label} href={`#${item.label.toLowerCase().replaceAll(" ", "-").replaceAll("/", "")}`} className={`flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium ${index === 0 ? "bg-primary text-white" : "text-slate-600 hover:bg-slate-100 hover:text-slate-950"}`}>
            <item.icon className="size-4" />
            {item.label}
          </a>
        ))}
      </nav>
    </aside>
  );
}

