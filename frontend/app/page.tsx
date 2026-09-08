import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { REFRESH_TOKEN_COOKIE } from "@/lib/server/backend-config";

export default async function RootPage() {
  const cookieStore = await cookies();
  const hasSession = cookieStore.has(REFRESH_TOKEN_COOKIE);
  redirect(hasSession ? "/dashboard" : "/login");
}
