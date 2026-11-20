import type { Metadata } from "next";
import Prose from "@/components/Prose";
import { BRAND, SUPPORT_EMAIL } from "@/lib/site";

export const metadata: Metadata = { title: "Copyright & DMCA", description: `Copyright policy and takedown requests for ${BRAND}.`, alternates: { canonical: "/legal/copyright" } };

export default function Copyright() {
  return (
    <Prose title="Copyright & DMCA Policy">
      <p>{BRAND} respects the rights of creators. Users must only clip content they own or have permission to use, and we respond to valid copyright notices.</p>
      <h2>Reporting infringement</h2>
      <p>If you believe content processed or stored by {BRAND} infringes your copyright, send a notice to <a href={`mailto:${SUPPORT_EMAIL}`}>{SUPPORT_EMAIL}</a> that includes:</p>
      <ul>
        <li>Your physical or electronic signature.</li>
        <li>A description of the copyrighted work.</li>
        <li>The specific material you believe infringes it, with enough detail for us to find it.</li>
        <li>Your name, address, phone number and email.</li>
        <li>A statement that you believe in good faith the use isn&apos;t authorized by the owner, its agent or the law.</li>
        <li>A statement, under penalty of perjury, that the information is accurate and you&apos;re the owner or authorized to act for the owner.</li>
      </ul>
      <p>Clips are usually posted by users on third-party platforms. To remove a posted clip, also report it directly to that platform.</p>
      <h2>Counter-notices</h2>
      <p>If your material was removed and you believe that was a mistake, you can send a counter-notice with your contact details, a description of the removed material, a statement under penalty of perjury that it was removed by mistake, and your consent to the jurisdiction of the relevant court.</p>
      <h2>Repeat infringers</h2>
      <p>We close the accounts of users who repeatedly infringe.</p>
      <h2>Designated agent</h2>
      <p>Name: [to be added]<br />Address: [to be added]<br />Email: <a href={`mailto:${SUPPORT_EMAIL}`}>{SUPPORT_EMAIL}</a></p>
    </Prose>
  );
}
