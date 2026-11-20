import type { Metadata } from "next";
import Prose from "@/components/Prose";
import { BRAND, SUPPORT_EMAIL } from "@/lib/site";

export const metadata: Metadata = { title: "Refund Policy", description: `Refunds and cancellations for ${BRAND} subscriptions.`, alternates: { canonical: "/legal/refunds" } };

export default function Refunds() {
  return (
    <Prose title="Refund Policy">
      <p>We want you to be happy with {BRAND}. The free plan lets you try the full workflow before paying.</p>
      <h2>Refunds</h2>
      <ul>
        <li>If you&apos;re not satisfied, you can request a full refund within <b>14 days</b> of your first payment for a plan.</li>
        <li>After 14 days, payments aren&apos;t refunded, but you can cancel at any time to stop future charges.</li>
        <li>If something on our side prevented you from using the service, contact us and we&apos;ll make it right.</li>
      </ul>
      <h2>How to request one</h2>
      <p>Email <a href={`mailto:${SUPPORT_EMAIL}`}>{SUPPORT_EMAIL}</a> with the email address on your account, or reply to your Paddle receipt. Refunds are processed by our merchant of record, Paddle, back to your original payment method, usually within 5–10 business days.</p>
      <h2>Cancelling</h2>
      <p>Cancel anytime from <b>Account → Manage billing</b>. You keep your paid plan until the end of the period you&apos;ve paid for, and you won&apos;t be charged again.</p>
    </Prose>
  );
}
