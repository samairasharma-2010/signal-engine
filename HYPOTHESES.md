# Pre-registered hypotheses

Committed BEFORE running the analysis on real data. The git commit date of this
file is the proof. Do not edit after the first real `python pipeline.py fetch`;
add an "Amendments" section with a date instead.

**Question:** Can freely available public-attention data, known before a company
reports, tell us whether its revenue growth is about to speed up or slow down?

**Data:** 10 companies (Nike, Adidas, Netflix, Apple, Microsoft, Amazon, Tesla,
McDonald's, Starbucks, Coca-Cola), fiscal quarters from 2016 onward.
Signals: Wikipedia page views, Google search interest.

**Success criterion (decided in advance):** a signal "works" if, pooled across
companies, its Benjamini-Hochberg adjusted p-value is below 0.05 AND its
out-of-sample R² (quarters from 2022 on) is above zero.

- **H1 (nowcast):** Signal acceleration in quarter t is positively related to
  revenue acceleration in quarter t.
- **H2 (lead):** The same relationship holds for quarter t+1, but weaker.
- **H3 (industry):** The relationship is stronger for consumer-facing companies
  than for business-facing ones (Microsoft, Amazon).
- **H4 (null):** At least one signal shows no reliable relationship.

Date committed: ____________
