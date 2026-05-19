import { ReconcileResultsPage } from "@/components/saas/reconcile-v2-page";

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <ReconcileResultsPage id={Number(id)} />;
}
