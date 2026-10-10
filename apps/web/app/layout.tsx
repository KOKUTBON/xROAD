import type { Metadata } from "next";
import { STATIC_DEMO, publicAsset } from "@/lib/demo-mode";
import type { ReactNode } from "react";

import { InstitutionProvider } from "@/components/institution-provider";
import { LocaleProvider } from "@/components/locale-provider";
import { SessionProvider } from "@/components/session-provider";
import { ThemeProvider } from "@/components/theme-provider";
import { localeInitScript } from "@/lib/i18n";
import { themeInitScript } from "@/lib/theme";

import "maplibre-gl/dist/maplibre-gl.css";
import "./globals.css";
import "./signal-system.css";
import "./workbench-utilities.css";
import "./signal-landing.css";

export const metadata: Metadata = {
  ...(STATIC_DEMO ? { metadataBase: new URL("https://kokutbon.github.io") } : {}),
  manifest: publicAsset("/manifest.webmanifest"),
  title: "xROAD — Road Risk Intelligence",
  description:
    "See road risk before it becomes a crash: hotspot detection, exposure-aware risk models, and intervention planning for municipal road safety.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" data-theme="light" suppressHydrationWarning>
      <head>
        {/* Apply the persisted locale to <html lang> before hydration. */}
        <script dangerouslySetInnerHTML={{ __html: localeInitScript() }} />
        {/* Apply the persisted (or OS-preferred) appearance before first paint. */}
        <script dangerouslySetInnerHTML={{ __html: themeInitScript() }} />
        <meta name="theme-color" content="#0e1013" />
      </head>
      <body>
        <ThemeProvider>
          <InstitutionProvider>
            <LocaleProvider>
              <SessionProvider>{STATIC_DEMO ? <div className="demo-banner" role="note">Public demo · synthetic sample data · simulated login · backend actions unavailable</div> : null}{children}</SessionProvider>
            </LocaleProvider>
          </InstitutionProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
