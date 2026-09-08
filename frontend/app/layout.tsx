import type { ReactNode } from "react";
import { NextIntlClientProvider } from "next-intl";
import { getMessages } from "next-intl/server";
import { QueryProvider } from "@/components/providers/QueryProvider";
import { AppNav } from "@/components/features/AppNav";
import "./globals.css";

export const metadata = {
  title: "NutriApp",
  description: "Log what you eat and see your macro/micro nutrient totals.",
};

export default async function RootLayout({ children }: { children: ReactNode }) {
  const messages = await getMessages();
  return (
    <html lang="en">
      <body>
        <NextIntlClientProvider messages={messages}>
          <QueryProvider>
            <AppNav />
            <main>{children}</main>
          </QueryProvider>
        </NextIntlClientProvider>
      </body>
    </html>
  );
}
