import Link from "next/link";
import { ArrowRight, CheckCircle2, FileJson, ReceiptText, Repeat2, ShieldCheck, UploadCloud } from "lucide-react";
import { LogoMark } from "@/components/saas/app-shell";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://127.0.0.1:8000";

type MarketplaceCatalogItem = {
  key: string;
  name: string;
  status: string;
  category: string;
  parser: string;
};

async function loadMarketplaceCatalog() {
  try {
    const response = await fetch(`${API_BASE}/marketplaces`, { cache: "no-store" });
    if (!response.ok) return [];
    const result = await response.json() as { marketplaces?: MarketplaceCatalogItem[] };
    return result.marketplaces || [];
  } catch {
    return [];
  }
}

export default async function LandingPage() {
  const marketplaces = await loadMarketplaceCatalog();
  const activeParsers = marketplaces.filter((item) => item.status === "Active").length;
  const betaParsers = marketplaces.filter((item) => item.status === "Beta").length;
  const categories = new Set(marketplaces.map((item) => item.category)).size;
  const features = [
    { title: "Marketplace automation", body: `${activeParsers} active parsers and ${betaParsers} beta parsers loaded from backend.`, icon: UploadCloud },
    { title: "GSTR-1 filing studio", body: `${marketplaces.length} platform inputs can flow into the GSTR-1 preview/export engine.`, icon: FileJson },
    { title: "Tally + reconciliation", body: `${categories} marketplace categories available for accounting and reconciliation workflows.`, icon: Repeat2 }
  ];
  const workflow = [
    `${marketplaces.length} backend parsers available`,
    `${activeParsers} active upload parsers`,
    `${betaParsers} beta upload parsers`,
    `${categories} marketplace categories`
  ];
  return (
    <main className="min-h-screen bg-[#f6f8fb] text-slate-950">
      <header className="mx-auto flex max-w-7xl items-center justify-between px-6 py-6">
        <LogoMark />
        <nav className="hidden items-center gap-8 text-sm font-semibold text-slate-600 md:flex">
          <a href="#features">Features</a>
          <a href="#security">Security</a>
          <Link href="/login">Login</Link>
          <Link href="/register" className="rounded-2xl bg-[#10244d] px-5 py-3 text-white">Start free</Link>
        </nav>
      </header>
      <section className="relative mx-auto grid max-w-7xl gap-10 px-6 py-16 lg:grid-cols-[1.05fr_0.95fr] lg:py-24">
        <div>
          <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-emerald-200 bg-emerald-50 px-4 py-2 text-sm font-bold text-emerald-700"><ShieldCheck className="size-4" /> Built for Indian eCommerce GST teams</div>
          <h1 className="text-5xl font-black tracking-tight md:text-7xl">GST filing OS for marketplace sellers.</h1>
          <p className="mt-6 max-w-2xl text-lg leading-8 text-slate-600">GST Bharat turns messy platform reports into normalized transactions, validation insights, GSTR-1 JSON/Excel, Tally XML and reconciliation workflows.</p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Link href="/register" className="inline-flex items-center gap-2 rounded-2xl bg-[#10244d] px-6 py-4 font-bold text-white shadow-2xl shadow-blue-950/20">Create workspace <ArrowRight className="size-4" /></Link>
            <Link href="/modules/online-seller/marketplaces" className="rounded-2xl border border-slate-200 bg-white px-6 py-4 font-bold text-slate-700">Explore integrations</Link>
          </div>
        </div>
        <div className="rounded-[2rem] border border-white bg-white p-4 shadow-2xl shadow-slate-300/60">
          <div className="rounded-[1.5rem] bg-gradient-to-br from-[#10244d] via-[#1746A2] to-[#0F9F6E] p-6 text-white">
            <p className="text-sm font-bold uppercase tracking-[0.2em] text-orange-200">Backend-connected workflow</p>
            <div className="mt-8 grid gap-4">
              {workflow.map((item, index) => <div key={item} className="flex items-center gap-3 rounded-3xl bg-white/12 p-5 backdrop-blur"><span className="grid size-9 place-items-center rounded-2xl bg-white/20 text-sm font-black">{index + 1}</span><p className="font-black">{item}</p></div>)}
            </div>
            <div className="mt-6 rounded-3xl bg-white p-5 text-slate-950">
              <p className="font-black">Backend parser catalog</p>
              {marketplaces.slice(0, 4).map((item) => <p key={item.key} className="mt-3 flex items-center gap-2 text-sm font-semibold text-slate-600"><CheckCircle2 className="size-4 text-emerald-600" />{item.name} / {item.status} / {item.parser}</p>)}
              {!marketplaces.length ? <p className="mt-3 text-sm font-semibold text-slate-600">Backend catalog unavailable.</p> : null}
            </div>
          </div>
        </div>
      </section>
      <section id="features" className="mx-auto grid max-w-7xl gap-5 px-6 pb-20 md:grid-cols-3">
        {features.map((feature) => {
          const Icon = feature.icon;
          return <div key={feature.title} className="rounded-3xl border border-white bg-white p-6 shadow-xl shadow-slate-200/70"><Icon className="size-7 text-[#1746A2]" /><h2 className="mt-5 text-xl font-black">{feature.title}</h2><p className="mt-3 text-sm leading-6 text-slate-500">{feature.body}</p></div>;
        })}
      </section>
      <section id="security" className="border-t border-slate-200 bg-white px-6 py-10 text-center text-sm text-slate-500"><ReceiptText className="mx-auto mb-3 size-6 text-saffron" />GST Bharat is original software. Backend calculations remain connected to the existing FastAPI engine.</section>
    </main>
  );
}
