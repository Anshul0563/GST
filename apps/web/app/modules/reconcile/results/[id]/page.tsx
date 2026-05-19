import { ReconcileResultsPage } from "@/components/saas/reconcile-v2-page";

export default function Page({ params }: { params: { id: string } }) {
  return <ReconcileResultsPage id={Number(params.id)} />;
}

