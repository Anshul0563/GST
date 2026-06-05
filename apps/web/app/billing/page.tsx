import { BillingPage } from "@/components/saas/utility-pages";

export default async function Page({
  searchParams,
}: {
  searchParams?: Promise<{ plan?: string }>;
}) {
  const params = await searchParams;
  return <BillingPage selectedPlanId={params?.plan} />;
}
