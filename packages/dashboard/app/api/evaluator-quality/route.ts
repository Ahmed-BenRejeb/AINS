import { NextResponse } from "next/server";
import { getEvaluatorQuality } from "@/lib/api";

export const dynamic = "force-dynamic";

/**
 * Proxy `GET /evaluator-quality/demo` (server-to-server, no CORS). Runs the
 * evaluator over the built-in gold set and returns a `Loaded<EvaluatorQuality>`.
 * Button-triggered from the UI because it re-judges a few cases (spends neurons).
 */
export async function GET(request: Request) {
  const mock = new URL(request.url).searchParams.get("mock") === "true";
  const result = await getEvaluatorQuality(mock);
  return NextResponse.json(result);
}
