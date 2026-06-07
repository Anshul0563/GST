import Link from "next/link";
import type { Route } from "next";
import { ArrowRight, CheckCircle2, FileJson, ReceiptText, Repeat2, ShieldCheck, UploadCloud } from "lucide-react";
import { AuthRedirect } from "@/components/saas/auth-redirect";
import { AppFooter } from "@/components/saas/footer";
import { API_BASE } from "@/lib/api";
import { absoluteUrl, siteDescription, siteName } from "@/lib/seo";

export const revalidate = 3600;

type MarketplaceCatalogItem = {
  key: string;
  name: string;
  status: string;
  category: string;
  parser: string;
};

async function loadMarketplaceCatalog() {
  if (!API_BASE) return [];
  try {
    const response = await fetch(`${API_BASE}/marketplaces`, {
      next: { revalidate: 3600 },
    });
    if (!response.ok) return [];
    const result = await response.json() as { marketplaces?: MarketplaceCatalogItem[] };
    return result.marketplaces || [];
  } catch {
    return [];
  }
}

const pricingPlans = [
  {
    name: "2A/2B Reconcile",
    price: "Free",
    tagline: "Match GST portal 2A/2B with purchase books and download reconciliation reports.",
    bullets: ["Upload portal and purchase files", "Mismatch categories and tax differences", "Excel reconciliation reports"],
    href: "/modules/reconcile",
  },
  {
    name: "GST Online Seller",
    price: "₹79/mo",
    tagline: "Import marketplace sales, clean transactions and generate GSTR-1 exports.",
    bullets: ["Marketplace import workflow", "Normalized sales data management", "GSTR-1 JSON and Excel reports"],
    href: "/billing?plan=online_seller",
    featured: true,
  },
  {
    name: "eCom to Tally",
    price: "₹199/mo",
    tagline: "Convert eCommerce transactions into mapped Tally vouchers and XML exports.",
    bullets: ["Tally company setup", "Ledger mapping templates", "Tally XML and voucher Excel export"],
    href: "/billing?plan=ecom_tally",
  },
];

function PublicLogoMark() {
  return (
    <div className="flex items-center gap-3">
      <div className="grid size-10 place-items-center rounded-xl bg-[#12284f] font-black text-white shadow-sm ring-1 ring-white/15">GB</div>
      <div>
        <p className="text-lg font-black tracking-tight text-slate-950">GST Bharat</p>
        <p className="-mt-0.5 text-[11px] font-bold uppercase tracking-[0.16em] text-slate-500">eCom GST OS</p>
      </div>
    </div>
  );
}

export default async function LandingPage() {
  const marketplaces = await loadMarketplaceCatalog();
  const activeParsers = marketplaces.filter((item) => item.status === "Active").length;
  const betaParsers = marketplaces.filter((item) => item.status === "Beta").length;
  const categories = new Set(marketplaces.map((item) => item.category)).size;
  const features = [
    { title: "Marketplace automation", body: `${activeParsers} active parsers and ${betaParsers} beta parsers loaded from backend.`, icon: UploadCloud },
    { title: "GSTR-1 filing studio", body: `${marketplaces.length} platform inputs can flow into the GSTR-1 preview/export engine.`, icon: FileJson },
    { title: "Tally + reconciliation", body: `${categories} marketplace categories available for accounting and reconciliation workflows.`, icon: Repeat2 },
  ];
  const workflow = [
    `${marketplaces.length} backend parsers available`,
    `${activeParsers} active upload parsers`,
    `${betaParsers} beta upload parsers`,
    `${categories} marketplace categories`,
  ];
  const jsonLd = {
    "@context": "https://schema.org",
    "@graph": [
      {
        "@type": "Organization",
        "@id": absoluteUrl("/#organization"),
        name: siteName,
        url: absoluteUrl("/"),
        logo: absoluteUrl("/logo.png"),
      },
      {
        "@type": "WebSite",
        "@id": absoluteUrl("/#website"),
        name: siteName,
        url: absoluteUrl("/"),
        publisher: { "@id": absoluteUrl("/#organization") },
        inLanguage: "en-IN",
      },
      {
        "@type": "SoftwareApplication",
        "@id": absoluteUrl("/#software"),
        name: siteName,
        applicationCategory: "BusinessApplication",
        operatingSystem: "Web",
        url: absoluteUrl("/"),
        description: siteDescription,
        offers: pricingPlans.map((plan) => ({
          "@type": "Offer",
          name: plan.name,
          price: plan.price === "Free" ? "0" : plan.price.replace(/[^\d]/g, ""),
          priceCurrency: "INR",
          url: absoluteUrl(plan.href),
        })),
        featureList: [
          "Marketplace GST report imports",
          "GSTR-1 JSON and Excel generation",
          "Tally XML voucher export",
          "2A/2B reconciliation reports",
          "GST validation and audit checks",
        ],
      },
      {
        "@type": "FAQPage",
        "@id": absoluteUrl("/#faq"),
        mainEntity: [
          {
            "@type": "Question",
            name: "What does GST Bharat do?",
            acceptedAnswer: {
              "@type": "Answer",
              text: "GST Bharat converts marketplace sales reports into normalized GST transactions, GSTR-1 files, Tally XML exports, and reconciliation reports.",
            },
          },
          {
            "@type": "Question",
            name: "Which marketplaces are supported?",
            acceptedAnswer: {
              "@type": "Answer",
              text: "GST Bharat supports Amazon, Flipkart, Meesho, Myntra, JioMart, Snapdeal, and custom CSV or Excel marketplace data workflows.",
            },
          },
        ],
      },
    ],
  };

  return (
    <main className="relative min-h-screen overflow-hidden bg-[#f6f8fb] text-slate-950">
      <AuthRedirect />
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
      />
      <div className="absolute inset-x-0 top-0 h-80 bg-gradient-to-br from-[#eaf2ff] via-[#f6f8fb] to-transparent opacity-90" />
      <div className="absolute right-0 top-24 hidden h-72 w-72 rounded-full bg-[#1746A2]/10 blur-3xl md:block" />
      <header className="sticky top-0 z-40 border-b border-slate-200/70 bg-white/90 backdrop-blur-xl shadow-sm">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-4">
          <PublicLogoMark />
          <nav className="hidden items-center gap-8 text-sm font-semibold text-slate-600 md:flex">
            <a href="#features" className="transition hover:text-[#1746A2]">Features</a>
            <a href="#pricing" className="transition hover:text-[#1746A2]">Pricing</a>
            <a href="#security" className="transition hover:text-[#1746A2]">Security</a>
          </nav>
          <div className="hidden items-center gap-3 md:flex">
            <Link href="/login" className="text-sm font-semibold text-slate-600 transition hover:text-[#1746A2]">Login</Link>
          </div>
        </div>
      </header>

      <section className="mx-auto grid max-w-7xl gap-10 px-6 py-16 lg:grid-cols-[1.1fr_0.9fr] lg:py-24">
        <div className="relative z-10">
          <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-emerald-200 bg-emerald-50 px-4 py-2 text-sm font-bold text-emerald-700 shadow-sm shadow-emerald-100/60">
            <ShieldCheck className="size-4" /> Built for Indian marketplace GST teams
          </div>
          <h1 className="text-5xl font-black tracking-tight text-slate-950 md:text-7xl">GST Bharat is the GST operating system for eCommerce sellers.</h1>
          <p className="mt-6 max-w-2xl text-lg leading-8 text-slate-600">Turn marketplace sales reports into normalized transactions, validation intelligence, GSTR-1 exports, Tally XML and reconciliation workflows — all from a single connected dashboard.</p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Link href="/register" className="inline-flex items-center gap-2 rounded-2xl bg-[#10244d] px-6 py-4 font-bold text-white shadow-2xl shadow-blue-950/20 transition hover:bg-[#1746A2]">Create workspace <ArrowRight className="size-4" /></Link>
            <Link href="/billing" className="rounded-2xl border border-slate-200 bg-white px-6 py-4 font-bold text-slate-700 transition hover:border-[#1746A2] hover:text-[#1746A2]">View pricing</Link>
          </div>
          <div className="mt-10 grid gap-4 sm:grid-cols-2">
            <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-soft">
              <p className="text-sm font-semibold uppercase tracking-[0.18em] text-[#1746A2]">Supported platforms</p>
              <p className="mt-4 text-3xl font-black">{marketplaces.length}</p>
              <p className="mt-2 text-sm text-slate-500">Marketplace parsers loaded from backend catalog.</p>
            </div>
            <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-soft">
              <p className="text-sm font-semibold uppercase tracking-[0.18em] text-[#1746A2]">Live workflows</p>
              <p className="mt-4 text-3xl font-black">{activeParsers + betaParsers}</p>
              <p className="mt-2 text-sm text-slate-500">Active and beta parser templates available today.</p>
            </div>
          </div>
        </div>

        <div className="relative overflow-hidden rounded-[2rem] border border-white bg-white p-4 shadow-2xl shadow-slate-300/50">
          <div className="absolute inset-x-0 top-0 h-24 bg-gradient-to-b from-[#10244d] via-[#1746A2] to-transparent opacity-90" />
          <div className="relative rounded-[1.5rem] bg-[#10244d] p-6 text-white shadow-xl">
            <p className="text-sm font-bold uppercase tracking-[0.2em] text-orange-200">Workflow snapshot</p>
            <div className="mt-8 grid gap-4">
              {workflow.map((item, index) => (
                <div key={item} className="flex items-center gap-3 rounded-3xl bg-white/12 p-5 backdrop-blur transition hover:bg-white/20">
                  <span className="grid h-11 w-11 place-items-center rounded-2xl bg-white/20 text-sm font-black">{index + 1}</span>
                  <p className="font-black">{item}</p>
                </div>
              ))}
            </div>
            <div className="mt-6 rounded-3xl bg-white p-5 text-slate-950 shadow-soft">
              <p className="font-black">Parser catalog highlights</p>
              {marketplaces.slice(0, 4).map((item) => (
                <p key={item.key} className="mt-3 flex items-center gap-2 text-sm font-semibold text-slate-600"><CheckCircle2 className="size-4 text-emerald-600" />{item.name} / {item.status} / {item.parser}</p>
              ))}
              {!marketplaces.length ? <p className="mt-3 text-sm font-semibold text-slate-600">Backend catalog unavailable.</p> : null}
            </div>
          </div>
        </div>
      </section>

      <section id="features" className="mx-auto max-w-7xl px-6 pb-20">
        <div className="mb-10 flex flex-col gap-3 text-center">
          <p className="text-sm font-semibold uppercase tracking-[0.24em] text-[#1746A2]">Core capabilities</p>
          <h2 className="text-4xl font-black tracking-tight text-slate-950">Designed to match your GST seller journey.</h2>
          <p className="mx-auto max-w-2xl text-sm leading-7 text-slate-600">A unified platform for marketplaces, GSTR-1 filing, reconciliation and Tally export — built to look and feel like a modern SaaS workflow.</p>
        </div>
        <div className="grid gap-6 md:grid-cols-3">
          {features.map((feature) => {
            const Icon = feature.icon;
            return (
              <div key={feature.title} className="rounded-[2rem] border border-slate-200 bg-white p-8 shadow-soft transition hover:-translate-y-1 hover:border-[#1746A2]/40 hover:shadow-xl">
                <div className="flex h-14 w-14 items-center justify-center rounded-3xl bg-[#eef4ff] text-[#1746A2]"><Icon className="size-6" /></div>
                <h3 className="mt-6 text-xl font-black text-slate-950">{feature.title}</h3>
                <p className="mt-4 text-sm leading-7 text-slate-600">{feature.body}</p>
              </div>
            );
          })}
        </div>
      </section>

      <section id="pricing" className="mx-auto max-w-7xl px-6 pb-24">
        <div className="mb-12 flex flex-col gap-3 text-center">
          <p className="text-sm font-semibold uppercase tracking-[0.24em] text-[#1746A2]">Pricing</p>
          <h2 className="text-4xl font-black tracking-tight text-slate-950">Simple plans for GST and accounting workflows.</h2>
          <p className="mx-auto max-w-2xl text-sm leading-7 text-slate-600">Start with free reconciliation, then add marketplace GST filing or Tally export when your workflow needs it.</p>
        </div>
        <div className="grid gap-6 lg:grid-cols-3">
          {pricingPlans.map((plan) => (
            <div key={plan.name} className={`rounded-[2rem] border p-8 shadow-soft transition hover:-translate-y-1 ${plan.featured ? "border-[#1746A2] bg-[#f5f8ff]" : "border-slate-200 bg-white"}`}>
              <div className="inline-flex rounded-full bg-[#eef4ff] px-4 py-2 text-sm font-semibold text-[#1746A2]">{plan.name}</div>
              <p className="mt-6 text-5xl font-black tracking-tight text-slate-950">{plan.price}</p>
              <p className="mt-4 text-sm leading-7 text-slate-600">{plan.tagline}</p>
              <ul className="mt-8 space-y-3 text-sm text-slate-600">
                {plan.bullets.map((bullet) => <li key={bullet} className="flex items-center gap-3"><CheckCircle2 className="size-4 text-emerald-600" /><span>{bullet}</span></li>)}
              </ul>
              <Link href={plan.href as Route} className={`mt-8 inline-flex w-full items-center justify-center rounded-2xl px-5 py-4 text-sm font-bold transition ${plan.featured ? "bg-[#1746A2] text-white" : "border border-slate-200 bg-white text-slate-900 hover:bg-slate-50"}`}>
                {plan.featured ? "Choose GST Online Seller" : plan.price === "Free" ? "Open free tool" : "View plan"}
              </Link>
            </div>
          ))}
        </div>
      </section>

      <section id="security" className="border-t border-slate-200 bg-white px-6 py-14 text-center text-sm text-slate-500">
        <div className="mx-auto max-w-3xl">
          <ReceiptText className="mx-auto mb-4 size-6 text-saffron" />
          <p className="text-xl font-black text-slate-950">Secure, transparent and connected to your backend engine.</p>
          <p className="mt-4 leading-7">GST Bharat is original software that uses the existing FastAPI backend for real-time marketplace parser, transaction normalization and GST filing workflows.</p>
        </div>
      </section>
      <AppFooter variant="public" />
    </main>
  );
}
