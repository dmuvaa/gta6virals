"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { BrandMark } from "./Navbar";
import { BRAND, COMPANY, SUPPORT_EMAIL, TAGLINE } from "@/lib/site";

export default function Footer({ signedIn }: { signedIn: boolean }) {
  const path = usePathname();
  if (path.startsWith("/app") || path === "/login" || path === "/signup" || path.startsWith("/auth") || path.endsWith("-password")) return null;
  return (
    <footer className="footer">
      <div className="container footer-grid">
        <div className="footer-brand">
          <Link className="brand" href="/"><BrandMark /><span>{BRAND}</span></Link>
          <p>{TAGLINE}</p>
        </div>
        <div>
          <h4>Product</h4>
          <Link href="/#features">Features</Link><Link href="/#how">How it works</Link><Link href="/pricing">Pricing</Link><Link href="/faq">FAQ</Link>
        </div>
        <div>
          <h4>Account</h4>
          {signedIn ? <><Link href="/app">Dashboard</Link><Link href="/app/account">Account &amp; billing</Link></>
                    : <><Link href="/signup">Sign up</Link><Link href="/login">Log in</Link></>}
          <a href={`mailto:${SUPPORT_EMAIL}`}>Contact support</a>
        </div>
        <div>
          <h4>Legal</h4>
          <Link href="/legal/terms">Terms of Service</Link><Link href="/legal/privacy">Privacy Policy</Link>
          <Link href="/legal/refunds">Refund Policy</Link><Link href="/legal/copyright">Copyright &amp; DMCA</Link>
        </div>
      </div>
      <div className="container footer-bottom">
        <span>© {new Date().getFullYear()} {COMPANY}. All rights reserved.</span>
        <span>Not affiliated with or endorsed by Rockstar Games, Take-Two Interactive, YouTube or Twitch. Game and channel names belong to their owners.</span>
      </div>
    </footer>
  );
}
