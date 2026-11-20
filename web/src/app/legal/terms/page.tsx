import type { Metadata } from "next";
import Link from "next/link";
import Prose from "@/components/Prose";
import { BRAND, SUPPORT_EMAIL } from "@/lib/site";

export const metadata: Metadata = { title: "Terms of Service", description: `Terms of Service for ${BRAND}.`, alternates: { canonical: "/legal/terms" } };

export default function Terms() {
  return (
    <Prose title="Terms of Service">
      <h2>1. The service</h2>
      <p>{BRAND} (&quot;we&quot;, &quot;us&quot;) lets you scan videos you link to, review moments from them, and export short clips. By creating an account or using the service, you agree to these Terms.</p>
      <h2>2. Your account</h2>
      <p>You must be at least 13 years old (or the minimum age in your country) to use {BRAND}. Keep your login details secure; you&apos;re responsible for activity on your account. Tell us right away at {SUPPORT_EMAIL} if you think your account has been compromised.</p>
      <h2>3. Content you clip</h2>
      <ul>
        <li>Only use {BRAND} on content you own or have permission to use, for example your own streams or streams whose creators run a clipping program you&apos;ve joined.</li>
        <li>You&apos;re responsible for the clips you make and where you post them, including following each platform&apos;s rules and each clipping campaign&apos;s rules.</li>
        <li>Don&apos;t use {BRAND} to infringe copyright or trademarks, impersonate anyone, or make misleading, hateful or illegal content.</li>
        <li>You keep whatever rights you have in the clips you make. You give us permission to process, store and deliver your content only as needed to run the service for you.</li>
      </ul>
      <h2>4. Acceptable use</h2>
      <p>Don&apos;t misuse the service. That includes trying to get around plan limits, overloading or attacking our systems, scraping or reselling the service, or sharing your account to dodge limits. We may suspend accounts that break these rules.</p>
      <h2>5. Plans, billing and cancellation</h2>
      <ul>
        <li>Paid plans are billed monthly in advance. Our order process is conducted by our online reseller Paddle.com, which is the merchant of record for all orders and handles payment, invoicing, sales tax and billing support. Paddle&apos;s buyer terms also apply to your purchase. Prices are on the <Link href="/pricing">pricing page</Link>.</li>
        <li>Monthly limits (hours scanned, exports) reset each calendar month and don&apos;t roll over.</li>
        <li>You can cancel at any time from your account page; you keep paid features until the end of the current billing period. Refunds are covered by our <Link href="/legal/refunds">Refund Policy</Link>.</li>
        <li>We may change prices with advance notice. Changes apply from your next billing period.</li>
      </ul>
      <h2>6. Storage and deletion</h2>
      <p>Projects, previews and clips are stored temporarily and deleted automatically after a limited time. Download anything you want to keep. You can delete projects or your whole account at any time.</p>
      <h2>7. Third-party services</h2>
      <p>{BRAND} works with videos hosted on third-party platforms such as YouTube and Twitch. We aren&apos;t affiliated with or endorsed by them, or by any game publisher. Their availability and terms are outside our control, and some videos may not work.</p>
      <h2>8. Disclaimers</h2>
      <p>The service is provided &quot;as is&quot;. We work hard to keep it fast and reliable, but we don&apos;t promise it will always be available, error-free, or that it will find every moment. We don&apos;t guarantee any number of views or earnings from clips you make.</p>
      <h2>9. Limitation of liability</h2>
      <p>To the extent the law allows, we aren&apos;t liable for indirect, incidental or consequential damages, or lost profits. Our total liability for any claim is limited to what you paid us in the 3 months before the claim.</p>
      <h2>10. Termination</h2>
      <p>You can stop using {BRAND} and delete your account at any time. We may suspend or end access if you break these Terms or if we must by law.</p>
      <h2>11. Changes</h2>
      <p>We may update these Terms. If the changes are significant, we&apos;ll let you know by email or in the app before they take effect.</p>
      <h2>12. Contact</h2>
      <p>Questions? Email <a href={`mailto:${SUPPORT_EMAIL}`}>{SUPPORT_EMAIL}</a>.</p>
    </Prose>
  );
}
