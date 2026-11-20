import type { Metadata, Viewport } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import Navbar from "@/components/Navbar";
import Footer from "@/components/Footer";
import { createClient } from "@/utils/supabase/server";
import { BRAND, SITE_URL } from "@/lib/site";

const inter = Inter({ subsets: ["latin"], weight: ["400", "500", "600", "700", "800", "900"], display: "swap" });

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: { default: `${BRAND}: turn long streams into hundreds of clips`, template: `%s · ${BRAND}` },
  description: `${BRAND} scans entire YouTube and Twitch streams in minutes and lines up every moment with action. Review fast, keep the best, export 9:16 clips with captions.`,
  applicationName: BRAND,
  openGraph: { type: "website", siteName: BRAND, images: [{ url: "/og.png", width: 1200, height: 630 }] },
  twitter: { card: "summary_large_image", images: ["/og.png"] },
  alternates: { canonical: "/" },
};

export const viewport: Viewport = { themeColor: "#0b0a10" };

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const supabase = await createClient();
  const { data: { user } } = await supabase.auth.getUser();
  const navUser = user ? { email: user.email || "", name: (user.user_metadata?.name as string) || "" } : null;
  return (
    <html lang="en" className={inter.className}>
      <body>
        <a className="skip" href="#main">Skip to content</a>
        <Navbar user={navUser} />
        <main id="main">{children}</main>
        <Footer signedIn={!!user} />
      </body>
    </html>
  );
}
