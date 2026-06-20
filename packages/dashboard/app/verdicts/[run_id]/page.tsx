import { getVerdict, isMock } from "@/lib/api";
import { VerdictView } from "@/components/sentinel/views/VerdictView";

export const dynamic = "force-dynamic";

/** Full verdict detail (`GET /verdicts/{run_id}`). */
export default async function VerdictPage({
  params,
  searchParams,
}: {
  params: Promise<{ run_id: string }>;
  searchParams: Promise<{ mock?: string }>;
}) {
  const { run_id } = await params;
  const mock = isMock(await searchParams);
  const { data, source, error } = await getVerdict(run_id, mock);
  return <VerdictView verdict={data} source={source} sourceError={error} mock={mock} />;
}
