import { getRunDetail, isMock } from "@/lib/api";
import { RunDetailView } from "@/components/sentinel/views/RunDetailView";

export const dynamic = "force-dynamic";

/** Execution trace for one run (`GET /runs/{run_id}`). */
export default async function RunDetailPage({
  params,
  searchParams,
}: {
  params: Promise<{ run_id: string }>;
  searchParams: Promise<{ mock?: string }>;
}) {
  const { run_id } = await params;
  const mock = isMock(await searchParams);
  const { data, source, error } = await getRunDetail(run_id, mock);
  return <RunDetailView detail={data} source={source} sourceError={error} mock={mock} />;
}
