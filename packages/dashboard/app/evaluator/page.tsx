import { isMock } from "@/lib/api";
import { EvaluatorView } from "@/components/sentinel/views/EvaluatorView";

export const dynamic = "force-dynamic";

/** Evaluation-of-the-evaluator (UC1 §2.4): judge-vs-human Cohen's kappa. */
export default async function EvaluatorPage({
  searchParams,
}: {
  searchParams: Promise<{ mock?: string }>;
}) {
  const mock = isMock(await searchParams);
  return <EvaluatorView mock={mock} />;
}
