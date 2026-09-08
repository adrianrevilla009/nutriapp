import { NextResponse } from "next/server";

/** Liveness probe (docs/containerization-and-orchestration.md section
 * 3.2) -- process is up. Never checks a downstream dependency: liveness
 * failing must mean "restart this pod," not "a backend is slow." */
export async function GET() {
  return NextResponse.json({ status: "ok" });
}
