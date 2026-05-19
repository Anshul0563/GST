import { Suspense } from "react";
import { ImportsPage } from "@/components/saas/imports-page";
import { EmptyState } from "@/components/saas/ui";

export default function Page() {
  return (
    <Suspense fallback={<EmptyState title="Loading marketplace upload" body="Preparing the marketplace upload workspace." />}>
      <ImportsPage />
    </Suspense>
  );
}
