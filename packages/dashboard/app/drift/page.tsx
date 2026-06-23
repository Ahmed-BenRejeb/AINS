import { getDrift, isMock } from "@/lib/api";
import { DriftView } from "@/components/sentinel/views/DriftView";

export const dynamic = "force-dynamic";

/** Behavioural drift across two windows of evaluated runs (UC1 §2.3). */
export default async function DriftPage({
  searchParams,
}: {
  searchParams: Promise<{ mock?: string }>;
}) {
  const mock = isMock(await searchParams);
  const { data, source, error } = await getDrift(mock);
  return <DriftView report={data} source={source} sourceError={error} mock={mock} />;
}
