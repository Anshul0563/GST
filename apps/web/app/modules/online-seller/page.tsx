import { redirect } from "next/navigation";

export default function Page() {
  redirect("/modules/online-seller/profile?next=/modules/online-seller/marketplaces");
}
