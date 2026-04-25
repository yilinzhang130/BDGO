import { fetchDealsServer, fetchDealsByTypeServer } from "@/lib/api-server";
import { DealsClient } from "./DealsClient";

export default async function DealsPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string>>;
}) {
  const params = await searchParams;
  const {
    q = "",
    type = "",
    sort = "宣布日期",
    order = "desc",
    page = "1",
  } = params;

  const [initialData, initialDealTypes] = await Promise.all([
    fetchDealsServer({ q, type, sort, order, page, page_size: "50" }),
    fetchDealsByTypeServer(),
  ]);

  return <DealsClient initialData={initialData} initialDealTypes={initialDealTypes} />;
}
