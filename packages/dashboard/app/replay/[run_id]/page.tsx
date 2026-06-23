import { DASHBOARD_URL, getRunDetail, isMock } from "@/lib/api";
import { ReplayView } from "@/components/sentinel/views/ReplayView";

export const dynamic = "force-dynamic";

/** Replay view: launch a deterministic replay or bisect two runs. */
export default async function ReplayPage({
  params,
  searchParams,
}: {
  params: Promise<{ run_id: string }>;
  searchParams: Promise<{ mock?: string }>;
}) {
  const { run_id } = await params;
  const mock = isMock(await searchParams);
  // Shareable deep link to this dashboard replay page (a human page, not the JSON API).
  const replayLink = `${DASHBOARD_URL}/replay/${run_id}`;
  // Load the recorded trajectory so the page shows WHAT replay re-executes.
  const { data: detail } = await getRunDetail(run_id, mock);
  return <ReplayView runId={run_id} replayLink={replayLink} detail={detail} mock={mock} />;
}
