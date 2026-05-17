"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";
import { loginUser } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("demo@gstbharat.example.com");
  const [password, setPassword] = useState("Password123");
  const [error, setError] = useState("");
  async function submit(event: FormEvent) {
    event.preventDefault();
    try {
      const token = await loginUser({ email, password });
      window.localStorage.setItem("gst_bharat_token", token.access_token);
      router.push("/dashboard");
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Login failed");
    }
  }
  return (
    <main className="grid min-h-screen bg-white lg:grid-cols-[42%_58%]">
      <section className="relative hidden min-h-screen items-center justify-center overflow-hidden bg-[#071a35] px-12 text-white lg:flex">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_30%_20%,rgba(245,130,32,0.22),transparent_28%),radial-gradient(circle_at_70%_80%,rgba(15,159,110,0.18),transparent_24%)]" />
        <div className="relative max-w-md text-center"><div className="text-5xl font-black">GST<span className="text-saffron">Bharat</span></div><p className="mt-8 text-2xl font-black leading-10">Welcome back to your eCommerce GST command center.</p><p className="mt-5 text-sm leading-7 text-white/70">Imports, validations, GSTR-1 files, Tally XML and reconciliation in one premium workspace.</p></div>
      </section>
      <section className="flex min-h-screen items-center justify-center px-6">
        <form onSubmit={submit} className="w-full max-w-md">
          <p className="text-sm font-bold uppercase tracking-[0.2em] text-[#1746A2]">GST Bharat</p>
          <h1 className="mt-3 text-4xl font-black tracking-tight">Login</h1>
          <p className="mt-2 text-slate-500">Use your account credentials. Demo is prefilled.</p>
          <label className="mt-8 block text-sm font-bold">Email<input value={email} onChange={(event) => setEmail(event.target.value)} className="mt-2 h-12 w-full rounded-2xl border border-slate-200 px-4 outline-none focus:border-[#1746A2]" /></label>
          <label className="mt-5 block text-sm font-bold">Password<input type="password" value={password} onChange={(event) => setPassword(event.target.value)} className="mt-2 h-12 w-full rounded-2xl border border-slate-200 px-4 outline-none focus:border-[#1746A2]" /></label>
          {error && <div className="mt-4 rounded-2xl bg-rose-50 p-3 text-sm text-rose-700">{error}</div>}
          <button className="mt-6 h-12 w-full rounded-2xl bg-[#10244d] font-bold text-white shadow-xl shadow-blue-950/20">Login</button>
          <p className="mt-5 text-center text-sm text-slate-500">New to GST Bharat? <Link className="font-bold text-[#1746A2]" href="/register">Create account</Link></p>
        </form>
      </section>
    </main>
  );
}
