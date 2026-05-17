import Link from "next/link";

export default function RegisterPage() {
  return (
    <main className="grid min-h-screen bg-white lg:grid-cols-[40%_60%]">
      <section className="gst-pattern relative hidden min-h-screen items-center justify-center px-12 text-center text-white lg:flex">
        <div>
          <div className="mx-auto mb-8 w-fit text-[34px] font-black leading-none">
            GST<span className="block -mt-1 text-[18px] text-[#f59e0b]">BHARAT</span>
          </div>
          <p className="mx-auto max-w-md text-xl leading-9 text-white/90">
            Create your seller workspace for GST reports, Tally XML and 2B/2A reconciliation.
          </p>
        </div>
        <div className="absolute bottom-10 left-0 right-0 flex justify-center gap-8 text-xs text-white/70">
          <span>Marketplace Imports</span>
          <span>Secure Filing</span>
          <span>Clean Exports</span>
        </div>
      </section>
      <section className="flex min-h-screen items-center justify-center px-6">
        <div className="w-full max-w-[28rem]">
          <div className="mb-10 text-center">
            <h1 className="text-3xl font-bold text-slate-950">Create account</h1>
            <p className="mt-2 text-sm text-slate-500">Start using GST Bharat tools.</p>
          </div>
          <form className="space-y-5">
            <label className="block text-sm font-semibold text-slate-700">Full Name<input className="mt-2 h-12 w-full rounded-md border border-slate-200 px-4 text-sm outline-none focus:border-[#3478ff]" placeholder="Aarav Sharma" /></label>
            <label className="block text-sm font-semibold text-slate-700">Email or Mobile Number<input className="mt-2 h-12 w-full rounded-md border border-slate-200 px-4 text-sm outline-none focus:border-[#3478ff]" placeholder="email@site.com or 98981xxxxx" /></label>
            <label className="block text-sm font-semibold text-slate-700">Password<input type="password" className="mt-2 h-12 w-full rounded-md border border-slate-200 px-4 text-sm outline-none focus:border-[#3478ff]" placeholder="4+ characters required" /></label>
            <button className="h-12 w-full rounded-md bg-[#3478ff] text-sm font-bold text-white">Create account</button>
            <p className="text-center text-sm text-slate-500">Already registered? <Link className="font-semibold text-[#3478ff]" href="/login">Login here</Link></p>
          </form>
        </div>
      </section>
    </main>
  );
}
