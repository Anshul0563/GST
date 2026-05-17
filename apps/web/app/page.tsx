import Link from "next/link";
import { ArrowRight, CheckCircle2, FileJson, ReceiptText, Repeat2, ShieldCheck, UploadCloud } from "lucide-react";
import { LogoMark } from "@/components/saas/app-shell";

export default function LandingPage() {
  const features = [
    { title: "Marketplace automation", body: "Upload Meesho, Amazon, Flipkart and custom reports into one normalized GST database.", icon: UploadCloud },
    { title: "GSTR-1 filing studio", body: "Preview B2CS, SUPECO and document issue before generating JSON and Excel.", icon: FileJson },
    { title: "Tally + reconciliation", body: "Generate Tally XML and manage 2A/2B reconciliation workflows.", icon: Repeat2 }
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
            <Link href="/dashboard" className="inline-flex items-center gap-2 rounded-2xl bg-[#10244d] px-6 py-4 font-bold text-white shadow-2xl shadow-blue-950/20">Open demo workspace <ArrowRight className="size-4" /></Link>
            <Link href="/marketplaces" className="rounded-2xl border border-slate-200 bg-white px-6 py-4 font-bold text-slate-700">Explore integrations</Link>
          </div>
        </div>
        <div className="rounded-[2rem] border border-white bg-white p-4 shadow-2xl shadow-slate-300/60">
          <div className="rounded-[1.5rem] bg-gradient-to-br from-[#10244d] via-[#1746A2] to-[#0F9F6E] p-6 text-white">
            <p className="text-sm font-bold uppercase tracking-[0.2em] text-orange-200">April 2026 Filing</p>
            <div className="mt-8 grid grid-cols-2 gap-4">
              {["Taxable ₹21,565.87", "GST ₹646.97", "B2CS 24", "Documents 238"].map((item) => <div key={item} className="rounded-3xl bg-white/12 p-5 backdrop-blur"><p className="text-2xl font-black">{item.split(" ")[1]}</p><p className="text-sm text-white/70">{item.split(" ")[0]}</p></div>)}
            </div>
            <div className="mt-6 rounded-3xl bg-white p-5 text-slate-950">
              <p className="font-black">Ready checklist</p>
              {["Meesho parsed", "Flipkart cashback adjustments", "Amazon MTR mapped", "GSTR-1 preview ready"].map((item) => <p key={item} className="mt-3 flex items-center gap-2 text-sm font-semibold text-slate-600"><CheckCircle2 className="size-4 text-emerald-600" />{item}</p>)}
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
