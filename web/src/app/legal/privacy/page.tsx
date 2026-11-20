import type { Metadata } from "next";
import Link from "next/link";
import Prose from "@/components/Prose";
import { BRAND, SUPPORT_EMAIL } from "@/lib/site";

export const metadata: Metadata = { title: "Privacy Policy", description: `How ${BRAND} handles your data.`, alternates: { canonical: "/legal/privacy" } };

export default function Privacy() {
  return (
    <Prose title="Privacy Policy">
      <h2>What we collect</h2>
      <ul>
        <li><b>Account details:</b> your email, name (optional) and login information. Passwords are handled by our authentication provider, Supabase, and are stored only in hashed form. If you sign in with Google or Twitch, we receive your email and basic profile from them.</li>
        <li><b>Projects:</b> the video links you submit, and the previews and clips made from them (stored temporarily).</li>
        <li><b>Usage:</b> hours scanned and clips exported each month, to apply plan limits.</li>
        <li><b>Billing:</b> if you subscribe, Paddle (our merchant of record) handles your payment details and billing address. We only receive a customer ID and your subscription status, never your card number.</li>
        <li><b>Technical data:</b> basic server logs (IP address, browser, pages requested) for security and troubleshooting.</li>
      </ul>
      <h2>How we use it</h2>
      <p>To run the service, apply plan limits, manage subscriptions, keep accounts secure and answer support requests. We don&apos;t sell your personal data or use it for advertising.</p>
      <h2>Cookies</h2>
      <p>We use essential cookies to keep you logged in. We don&apos;t use advertising or tracking cookies.</p>
      <h2>Who we share it with</h2>
      <ul>
        <li><b>Supabase</b>, which hosts our database and logins.</li>
        <li><b>Cloudflare</b>, which stores previews and clips.</li>
        <li><b>Our hosting provider</b>, which runs our servers.</li>
        <li><b>Paddle</b>, which sells subscriptions on our behalf and processes payments.</li>
        <li><b>Video platforms</b> (such as YouTube and Twitch), which receive requests from our servers when we fetch videos you link to.</li>
        <li><b>Authorities</b>, when the law requires it.</li>
      </ul>
      <h2>How long we keep it</h2>
      <p>Projects, previews and clips are deleted automatically after a short period, usually 48 hours. Account and billing records are kept while your account is open and as long as the law requires afterwards.</p>
      <h2>Your choices</h2>
      <p>You can delete any project, or your whole account and all its projects, from your <Link href="/app/account">account page</Link>. To get a copy of your data or ask a question, email <a href={`mailto:${SUPPORT_EMAIL}`}>{SUPPORT_EMAIL}</a>.</p>
      <h2>Changes</h2>
      <p>If we make significant changes, we&apos;ll update this page and tell you by email or in the app.</p>
    </Prose>
  );
}
