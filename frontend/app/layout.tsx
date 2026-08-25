import type { Metadata } from "next";
import "./globals.css";
import { Navbar } from "@/components/layout/Navbar";

export const metadata: Metadata = {
  title: { default: "Aperture Guard", template: "%s · Aperture Guard" },
  description: "Safe semantic image matching with deterministic mismatch protection.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50 focus:rounded-lg focus:bg-white focus:p-3 focus:text-black">Skip to content</a>
        <Navbar />
        <main id="main">{children}</main>
        <footer className="page-shell border-t border-white/10 py-8 text-sm text-slate-500">Aperture Guard · Evidence before recommendation.</footer>
      </body>
    </html>
  );
}
