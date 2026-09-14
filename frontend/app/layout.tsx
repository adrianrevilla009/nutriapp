import type { ReactNode } from "react";
import { Inter, Fraunces } from "next/font/google";
import { NextIntlClientProvider } from "next-intl";
import { getMessages } from "next-intl/server";
import { QueryProvider } from "@/components/providers/QueryProvider";
import { AppNav } from "@/components/features/AppNav";
import "./globals.css";

// Self-hosted at build time by next/font (no runtime request to Google
// Fonts, no layout-shift/CLS penalty) -- purely additive, styling-only
// change: a `className` on <html>, no markup/content/behavior change.
// Two families for the "warm editorial" pass: Fraunces (a warm, high-
// contrast display serif with optical sizing) for headings, Inter for
// body/UI text -- a deliberate, original pairing, not a copy of any
// particular site's font choices.
const inter = Inter({ subsets: ["latin"], variable: "--font-inter", display: "swap" });
const fraunces = Fraunces({
  subsets: ["latin"],
  variable: "--font-fraunces",
  display: "swap",
  axes: ["opsz", "SOFT", "WONK"],
});

export const metadata = {
  title: "NutriApp",
  description: "Log what you eat and see your macro/micro nutrient totals.",
};

export default async function RootLayout({ children }: { children: ReactNode }) {
  const messages = await getMessages();
  return (
    <html lang="en" className={`${inter.variable} ${fraunces.variable}`}>
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
