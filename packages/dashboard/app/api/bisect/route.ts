import { NextResponse } from "next/server";
import { postBisect } from "@/lib/api";

export const dynamic = "force-dynamic";

/**
 * Proxy `POST /bisect` to the flight recorder with mock support.
 * Body: `{ good_run_id: string, bad_run_id: string, mock?: boolean }`.
 * Returns a `Loaded<BisectResult>`.
 */
export async function POST(request: Request) {
  let body: { good_run_id?: string; bad_run_id?: string; mock?: boolean };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "invalid JSON body" }, { status: 400 });
  }
  if (!body.good_run_id || !body.bad_run_id) {
    return NextResponse.json(
      { error: "good_run_id and bad_run_id are required" },
      { status: 400 },
    );
  }
  const result = await postBisect(body.good_run_id, body.bad_run_id, Boolean(body.mock));
  return NextResponse.json(result);
}
