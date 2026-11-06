import type { Metadata } from "next";
import Image from "next/image";

import { Faq } from "@/components/marketing/Faq";
import { JsonLd } from "@/components/marketing/JsonLd";
import { PRIVACY_PROMISE } from "@/components/marketing/promise";
import { RuledList, Section } from "@/components/marketing/Section";
import { MCP_TOOL_COUNT, pageMeta } from "@/components/marketing/site";
import { faqNodes } from "@/components/marketing/seo/Blocks";
import { ButtonLink } from "@/components/ui";
import { FEATURES } from "@/lib/seo/facts";
import { HOME_FAQ } from "@/lib/seo/faq";
import { faqPage, graph, organization, softwareApplication, sourceCode, webPage, website } from "@/lib/seo/schema";
import { APP_VERSION_LABEL } from "@/lib/version";

export const metadata: Metadata = pageMeta("/");

const FACTS = [
  { k: "US · UK · KSA", v: "USD, GBP and SAR rounds" },
  { k: "Funding Room", v: "versioned diligence documents" },
  { k: "Claude", v: "on your own Anthropic key" },
  { k: `${MCP_TOOL_COUNT} MCP tools`, v: "for your agents" },
];

const MARKETS: { name: string; points: string[] }[] = [
  {
    name: "United Kingdom",
    points: [
      "GBP rounds with SAFE, priced equity, notes or an advance subscription agreement (ASA)",
      "SEIS then EIS: tranches in your funding costs and on the round",
      "HMRC advance assurance, articles and DTAC on the checklist",
    ],
  },
  {
    name: "United States",
    points: [
      "USD rounds on a post-money SAFE, a convertible note or priced equity",
      "Valuation cap or pre-money, target and close date per round",
      "Incorporation, 409A and HIPAA position on the checklist",
    ],
  },
  {
    name: "Saudi Arabia",
    points: [
      "SAR rounds, with Sharia-compliant terms marked on the round",
      "Commercial Registration, MISA licence, ZATCA, PDPL and SFDA on the checklist",
      "Arabic and English: the language switch is ready in Settings",
    ],
  },
];

/** Wasila's public home page (v1.0.0.0). */
export default function HomePage() {
  return (
    <>
      <JsonLd data={graph(organization(), website(), softwareApplication(), sourceCode(), webPage("/"), faqPage(HOME_FAQ, "/"))} />

      <section aria-labelledby="hero-title" className="overflow-hidden bg-linear-to-b from-accent-soft via-canvas to-canvas">
        <div className="gutter mx-auto grid max-w-site items-center gap-x-40 gap-y-32 pt-48 pb-56 lg:grid-cols-12 lg:pt-80 lg:pb-80">
          <div className="min-w-0 lg:col-span-7">
            <p className="t-label mb-18">Wasila {APP_VERSION_LABEL} · Investor CRM and Funding Room</p>
            <h1 id="hero-title" className="t-display-xl max-w-[14ch]">
              Your raise, in one place.
            </h1>
            <p className="t-body-l mt-18 max-w-[52ch] text-muted">
              One searchable master list of investors, every round&apos;s pipeline, a Funding Room for diligence, email outreach with the right attachments, your deck and your funding costs. For founders raising in the US, the UK and Saudi Arabia.
            </p>
            <div className="mt-28 flex flex-wrap items-center gap-12">
              <ButtonLink href="/signin" variant="primary" size="lg">
                Open Wasila
              </ButtonLink>
              <ButtonLink href="/docs" variant="secondary" size="lg">
                Read the docs
              </ButtonLink>
            </div>
            <dl className="mt-36 grid max-w-[640px] grid-cols-2 gap-x-24 gap-y-14 sm:grid-cols-4">
              {FACTS.map((f) => (
                <div key={f.k}>
                  <dt className="font-display text-lg font-bold text-accent">{f.k}</dt>
                  <dd className="m-0 text-sm text-muted">{f.v}</dd>
                </div>
              ))}
            </dl>
          </div>
          <div className="flex justify-center lg:col-span-5">
            <Image
              src="/brand/wasila-logo.png"
              alt="Wasila: وسيلة"
              width={360}
              height={355}
              priority
              unoptimized
              className="h-auto w-[220px] rounded-[18%] shadow-dialog sm:w-[300px] lg:w-[360px]"
            />
          </div>
        </div>
      </section>

      <Section id="features" index="01" note="Features" title="Everything the raise needs" lede="Built on a proven investor pipeline, with the tools founders asked for added on.">
        <ul className="m-0 grid list-none gap-14 p-0 sm:grid-cols-2 xl:grid-cols-3">
          {FEATURES.map((f) => (
            <li key={f.name} className="rounded-md border border-line border-t-3 border-t-brand-sky bg-surface p-16">
              <h3 className="t-display-xs m-0">{f.name}</h3>
              <p className="m-0 mt-8 text-muted">{f.text}</p>
            </li>
          ))}
        </ul>
      </Section>

      <Section id="markets" index="02" note="Markets" title="US, UK and Saudi rounds" lede="Each round knows where it is raised: the currency, the instruments, the tax relief and the documents investors there expect.">
        <div className="grid gap-14 md:grid-cols-3">
          {MARKETS.map((m) => (
            <div key={m.name} className="rounded-md border border-line border-t-3 border-t-brand-gold bg-surface p-16">
              <h3 className="t-display-xs m-0">{m.name}</h3>
              <ul className="m-0 mt-10 flex list-disc flex-col gap-6 ps-18 text-muted">
                {m.points.map((p) => (
                  <li key={p}>{p}</li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </Section>

      <Section id="privacy" index="03" note="Privacy" title="Private by design">
        <RuledList
          items={PRIVACY_PROMISE.map((p) => ({
            lead: p.lead,
            body: p.body,
          }))}
        />
      </Section>

      <Section id="faq" index="04" note="FAQ" title="Questions founders ask">
        <Faq items={faqNodes(HOME_FAQ)} />
      </Section>
    </>
  );
}
