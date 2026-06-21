import { getOverview, isMock } from "@/lib/api";
import { HomeLanding } from "@/components/sentinel/views/HomeLanding";

export const dynamic = "force-dynamic";

/**
 * Home / landing. Server-fetches the run + verdict overview (with mock support)
 * and hands it to the animated landing showpiece.
 */
export default async function HomePage({
  searchParams,
}: {
  searchParams: Promise<{ mock?: string }>;
}) {
  const mock = isMock(await searchParams);
  const { data, source, error } = await getOverview(mock);
  return (
    <HomeLanding
      stats={data.stats}
      summaries={data.summaries}
      source={source}
      sourceError={error}
      mock={mock}
    />
  );
}
