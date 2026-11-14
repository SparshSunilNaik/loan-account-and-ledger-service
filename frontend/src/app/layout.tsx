import type { Metadata } from "next";
import "./globals.css";
import "./workbench.css";
import { Providers } from "@/components/providers";
import { THEME_BOOTSTRAP } from "@/lib/theme";
import { Shell } from "@/components/shell";
export const metadata: Metadata = {
  title: { default: "LedgerCore Studio", template: "%s · LedgerCore Studio" },
  description:
    "Local financial operations and testing dashboard. Development only; outside the original submission.",
};
export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_BOOTSTRAP }} />
      </head>
      <body>
        <Providers>
          <Shell>{children}</Shell>
        </Providers>
      </body>
    </html>
  );
}
