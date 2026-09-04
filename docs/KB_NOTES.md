# Knowledge Base Notes

This document describes the synthetic knowledge base used by the Telecom Operations Copilot. It exists for two reasons: to be honest about the data the agent is grounded on, and to help anyone reviewing the project understand what the agent does and does not know.

## Contents

The KB is a flat collection of 17 markdown documents, organized in four sub-folders:

```
kb/
├── about/             (1 document)
├── plans/             (6 documents, ~3.2k words)
├── policies/          (5 documents, ~3.5k words)
└── troubleshooting/   (5 documents, ~5.3k words)
```

Total: about 12,000 words across 17 documents.

## What each folder covers

### `kb/plans/` (6 documents)

Plan offerings for the fictional telecom company **TelSano**:

| File | Plan | Type | Price |
|---|---|---|---|
| 01-essential.md | Essential | Mobile | $25/mo |
| 02-connect.md | Connect | Mobile | $45/mo |
| 03-unlimited.md | Unlimited | Mobile | $65/mo |
| 04-internet-100.md | Internet 100 | Home internet | $50/mo |
| 05-fiber-1000.md | Fiber 1000 | Home internet | $80/mo |
| 06-bundles-and-discounts.md | Bundles + autopay, senior, military, family | Cross-cutting | varies |

### `kb/policies/` (5 documents)

Operational policies that affect billing and account behavior:

- `01-billing-cycle.md` - bill issue dates, 21-day due date, prorated charges
- `02-late-fees.md` - 5-day grace period, $10 late fee, suspension after 14 days, $25 reconnect fee
- `03-autopay.md` - autopay enrollment, $5 per mobile line discount, failed payment handling
- `04-cancellation.md` - no early termination fees, 14-day equipment return, number portability
- `05-refunds-and-credits.md` - service outage credits, billing error refunds, goodwill credits

### `kb/troubleshooting/` (5 documents)

Diagnostic guides written for the agent to follow step by step:

- `01-slow-internet.md` - wired vs Wi-Fi diagnostics, power cycle, outage check, congestion patterns
- `02-no-internet-connection.md` - equipment lights, cables, account check, when to escalate
- `03-mobile-no-signal.md` - airplane mode, restart, SIM check, coverage map
- `04-mobile-data-not-working.md` - plan limit check, APN settings, account suspension
- `05-router-and-modem-help.md` - light meanings, restart vs factory reset, common equipment issues

## Document structure

Every KB document follows the same shape:

- **YAML front-matter** with metadata (`plan_id`, `doc_type`, `topic`, `applies_to`)
- **H1 heading** with the document title
- **One-line lead** describing what the document is about
- **H2 sections** that the agent can quote or cite

The consistent shape helps with:
- Chunking (sections become natural chunks for the vector store)
- Citation (the agent can cite "section X of file Y")
- Filtering (front-matter metadata can be used to narrow retrieval)

## Generation method

The 17 documents were generated through an LLM-assisted process:

1. Hand-design of the company's plan structure (5 plans + 1 bundle doc), with prices and feature sets chosen to mirror real US telecom market segmentation (entry / mid-tier / unlimited / standard home internet / fiber)
2. LLM generation (Claude Opus 4.7) of each document from a structured prompt: doc_type, topic, target sections, cross-references to other docs in the KB
3. **Manual review** of every document for internal consistency (prices match across docs, discount rules in `06-bundles-and-discounts.md` are referenced correctly in policy docs, troubleshooting steps reference real tool names defined in the architecture)
4. Stylistic cleanup: removed em-dashes throughout (project style guideline), kept English at a B2 level (the project owner is not a native English speaker)

## Internal consistency rules

The KB was authored to honor a few invariants. These matter because the agent will be evaluated on whether it respects them:

- Prices in plan docs match prices used in `kb/plans/06-bundles-and-discounts.md` example math
- Plan IDs used in `applies_to:` front-matter match the file names (`essential`, `connect`, `unlimited`, `internet_100`, `fiber_1000`)
- The 21-day due date is consistent across `01-billing-cycle.md`, `02-late-fees.md`, and `03-autopay.md`
- The 5-day grace period is mentioned in both `02-late-fees.md` and `03-autopay.md`
- Discount stacking rules in `06-bundles-and-discounts.md` are honored in the mock billing data (`mock-data/billing.json`)

## Limitations (be honest about what the KB does NOT cover)

The KB is intentionally narrow. It does NOT cover:

- **International plans and roaming pricing.** Connect and Unlimited mention Canada and Mexico, but specific add-on prices for other countries are not in the KB.
- **Business or enterprise plans.** Only residential plans exist.
- **Detailed device pricing or financing.** Mobile device payment plans are mentioned but not priced.
- **Complex billing disputes.** Edge cases like double-billing across address changes, partial-refund scenarios with three discount types, or pro-rated cancellation during a promotional period are not specifically addressed.
- **Detailed network technology specs.** Tower coverage, frequency bands, and similar engineering details are absent.
- **Regional pricing variation.** TelSano is treated as flat-priced across all US states. Real telecom pricing varies by zip code in ways this KB does not model.
- **Legal and regulatory text.** No FCC-style disclosures, ADA accommodations details, or state-specific consumer protection language.

The agent should refuse or escalate when asked about these topics, since making up answers would hurt grounding.

## Plausibility

The KB is fictional but designed to be plausible:

- Plan prices fall within real US carrier ranges as of 2025-2026
- Policy timelines (21-day billing, 14-day suspension, 30-day reactivation window) reflect common industry norms
- Troubleshooting steps mirror real consumer-router diagnostic flows
- Discount programs (autopay, family, senior, military) are common in the US telecom market

It would not pass a legal review by a real telecom and is unsuitable as a real customer-facing knowledge base. Its purpose is to be a realistic enough sandbox for evaluating the agent's classification, retrieval, tool use, and citation behavior.

## Update process

If a document is changed:

1. Update the document on the Dev branch
2. Update this notes file if structure or coverage changes
3. Check internal consistency: prices, plan IDs, timelines
4. Re-index the vector store so retrieval reflects the change
5. Re-run the evaluation suite (locked queries) to confirm no regressions

Notebooks `01-smoke-test.ipynb` and `02-kb-upload-and-retrieval-test.ipynb`, the
notebook used for step 4, were generated by build scripts that were removed once
they no longer reproduced them; both scripts are in the tree at commit 9236e49.
