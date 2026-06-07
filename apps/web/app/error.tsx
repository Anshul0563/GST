"use client";

import { ErrorState } from "@/components/saas/ui";

export default function Error({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <main className="min-h-screen bg-[#f3f6fa] px-5 py-10 text-slate-950 dark:bg-[#07111f] dark:text-white">
      <div className="mx-auto max-w-3xl">
        <ErrorState
          title="Page could not load"
          body={error.message || "Something interrupted this screen. Please retry once, or refresh if the network is unstable."}
          onRetry={reset}
        />
      </div>
    </main>
  );
}
