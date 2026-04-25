import { fetchIPServer } from "@/lib/api-server";
import { IPClient } from "./IPClient";

export default async function IPPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string>>;
}) {
  const params = await searchParams;
  const {
    q = "",
    status = "",
    jurisdiction = "",
    sort = "到期日",
    order = "asc",
    page = "1",
  } = params;

  const initialData = await fetchIPServer({
    q,
    status,
    jurisdiction,
    sort,
    order,
    page,
    page_size: "50",
  });

  return <IPClient initialData={initialData} />;
}
