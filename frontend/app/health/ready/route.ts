import { NextResponse } from "next/server";

/** Readiness probe -- this service has no database/broker connection of
 * its own to warm up (implementation plan section 2/3), so readiness is
 * equivalent to liveness: the process serving requests is the only
 * precondition. */
export async function GET() {
  return NextResponse.json({ status: "ok" });
}
