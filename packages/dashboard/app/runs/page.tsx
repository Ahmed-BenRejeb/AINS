import { getRuns, isMock } from "@/lib/api";
import { RunsView } from "@/components/sentinel/views/RunsView";

export const dynamic = "force-dynamic";

/** All recorded runs (`GET /runs`). */
export default async function RunsPage({
  searchParams,
}: {
  searchParams: Promise<{ mock?: string }>;
}) {
  const mock = isMock(await searchParams);
  const { data, source, error } = await getRuns(mock);
  return <RunsView runs={data} source={source} sourceError={error} mock={mock} />;
}
