import { FLIGHT_RECORDER_URL, isMock } from "@/lib/api";
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
  const replayLink = `${FLIGHT_RECORDER_URL}/replay/${run_id}`;
  return <ReplayView runId={run_id} replayLink={replayLink} mock={mock} />;
}
