import { getOverview, isMock } from "@/lib/api";
import { HomeView } from "@/components/sentinel/views/HomeView";

export const dynamic = "force-dynamic";

/**
 * Home / overview. Server-fetches the run + verdict overview (with mock support)
 * and hands it to the animated client view.
 */
export default async function HomePage({
  searchParams,
}: {
  searchParams: Promise<{ mock?: string }>;
}) {
  const mock = isMock(await searchParams);
  const { data, source, error } = await getOverview(mock);
  return (
    <HomeView
      stats={data.stats}
      summaries={data.summaries}
      source={source}
      sourceError={error}
      mock={mock}
    />
  );
}
