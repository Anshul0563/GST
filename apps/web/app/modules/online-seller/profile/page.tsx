import { Suspense } from "react";
import { ProfilePage } from "@/components/saas/utility-pages";
import { EmptyState } from "@/components/saas/ui";

export default function Page() {
  return (
    <Suspense fallback={<EmptyState title="Loading GST profile" body="Preparing the smart profile setup." />}>
      <ProfilePage />
    </Suspense>
  );
}
