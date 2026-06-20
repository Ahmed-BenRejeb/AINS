import { NextResponse } from "next/server";
import { postReplay } from "@/lib/api";

export const dynamic = "force-dynamic";

/**
 * Proxy `POST /replay` to the flight recorder (server-to-server, no CORS) with
 * mock support. Body: `{ run_id: string, mock?: boolean }`. Returns a `Loaded<ReplayResult>`.
 */
export async function POST(request: Request) {
  let body: { run_id?: string; mock?: boolean };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "invalid JSON body" }, { status: 400 });
  }
  if (!body.run_id) {
    return NextResponse.json({ error: "run_id is required" }, { status: 400 });
  }
  const result = await postReplay(body.run_id, Boolean(body.mock));
  return NextResponse.json(result);
}
