import { getDrift, getEvaluatorQuality, isMock } from "@/lib/api";
import { ReliabilityView } from "@/components/sentinel/views/ReliabilityView";

export const dynamic = "force-dynamic";

/** Reliability over time: behavioural drift + evaluator-quality (UC1 §2.3 / §2.4). */
export default async function ReliabilityPage({
  searchParams,
}: {
  searchParams: Promise<{ mock?: string }>;
}) {
  const mock = isMock(await searchParams);
  const [drift, quality] = await Promise.all([
    getDrift(mock),
    getEvaluatorQuality(mock),
  ]);
  return (
    <ReliabilityView
      drift={drift.data}
      quality={quality.data}
      source={drift.source}
      sourceError={drift.error ?? quality.error}
    />
  );
}
