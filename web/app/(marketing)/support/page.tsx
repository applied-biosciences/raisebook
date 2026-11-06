import type { Metadata } from "next";

import { JsonLd } from "@/components/marketing/JsonLd";
import { A, DocHeader, H2, P, Ul, slug } from "@/components/marketing/docs/Prose";
import { AsideFacts, AsideToc, PageShell } from "@/components/marketing/PageShell";
import { REPO_URL, pageMeta } from "@/components/marketing/site";
import { ButtonLink, TextLink } from "@/components/ui";
import { pageGraph } from "@/lib/seo/schema";
import { APP_VERSION_LABEL } from "@/lib/version";

export const metadata: Metadata = pageMeta("/support");

const SECTIONS = ["Report a problem", "What to include", "Security", "Your data"];

export default function Support() {
  return (
    <>
      <JsonLd data={pageGraph("/support")} />
      <PageShell
        aside={
          <>
            <AsideFacts
              items={[
                ["Operator", "Applied Biosciences"],
                ["Contact", "hello@wasila.app"],
                ["Version", APP_VERSION_LABEL],
              ]}
            />
            <AsideToc items={SECTIONS.map((s) => ({ id: slug(s), label: s }))} />
          </>
        }
      >
        <DocHeader
          eyebrow="Support"
          title="Get help with Wasila."
          lede={<p>Something broken, confusing or missing? Tell us and we will fix it for your team.</p>}
        />

        <div className="mb-32 flex flex-wrap items-center gap-x-18 gap-y-12">
          <ButtonLink href="mailto:hello@wasila.app" size="lg">
            Email support
          </ButtonLink>
          <TextLink href={REPO_URL} external>
            Open an issue
          </TextLink>
        </div>

        <H2>Report a problem</H2>
        <P>
          Email <A href="mailto:hello@wasila.app">hello@wasila.app</A> or open an issue in the{" "}
          <A href={REPO_URL}>repository</A>. Start with the <A href="/docs">docs</A> for how-tos.
        </P>

        <H2>What to include</H2>
        <Ul>
          <li>The page you were on and what you pressed.</li>
          <li>What you expected and what happened instead.</li>
          <li>The version shown at the bottom of every page ({APP_VERSION_LABEL}).</li>
          <li>Never send investor data, API keys or passwords in a report.</li>
        </Ul>

        <H2>Security</H2>
        <P>
          Report security issues privately: see <A href={`${REPO_URL}/blob/main/SECURITY.md`}>SECURITY.md</A>.
        </P>

        <H2>Your data</H2>
        <P>
          You can export or delete your data at any time: <A href="/docs/export">Export and delete</A>. Privacy questions
          are answered on the <A href="/privacy">privacy page</A>.
        </P>
      </PageShell>
    </>
  );
}
