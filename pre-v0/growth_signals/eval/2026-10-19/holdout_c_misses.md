# Held-out C (10 fresh companies, round-3 rules frozen): misses for the NEXT round

Score: precision 18/31 = 58% (19/31 = 61% after adjudicating TGS P12 "TGS Acquires Apparition
Geoservices", a true event on a listing page beyond the blocks read for labeling); recall 18/42 = 43%.
Previous rounds on their own fresh holdouts: ~60% precision, 32-39% recall. Round-3 fixes reached
100%/88-95% on the in-sample sets but generalized only slightly (recall +4-11 points, precision flat).

## False negatives (patterns, not sentences)
- Agreements without a signing verb: "today announced an agreement with PetroGuin for the rights".
- Divestiture objects: brands ("sold the B&M ... brands"), interests ("completed the sale of our
  interest in Mountain Valley Pipeline", "sold a minority interest in"), a business sold by name in a
  title ("TGS Sells North American Well Data Products Business").
- Acquisition forms: "Closed MARS Parts acquisition", "announced the strategic acquisition of",
  subsidiary as acquirer ("Brundage-Bone ... has completed the acquisition of").
- Market entry via acquisition: "to Enter U.K. Temporary Power Market", "Expands International
  Presence".
- Product launches without product nouns: "latest addition to its dealer platform: VINMax",
  "announced enhanced price transparency features", seismic "multi-client survey"/"project" products.
- Contracts: "Strategic Alliance with NYU Langone" (round-3 made "alliance" case-sensitive to stop
  "Media Alliance"; title case now misses), "anchored by firm commitments ... from shippers".
- Credit: "Increased capacity under the Company's revolving credit facility", "Closes $475 Million
  Private Offering of Senior Notes" used to redeem 2027 notes (refinancing by notes).

## False positives
- Quotes about strategy: "opened new end markets", "opportunities to expand market reach",
  "opening new locations" in advice prose (USPH blog), "building ... communities they serve".
- Dividend press release "positive outlook for fiscal year 2027" read as guidance raised.
- "Announces Quarterly Cash Dividend Program" read as a product launch (program).
- "CarGurus awards our top deal ratings" read as a contract award.
- "terminated ... asset purchase agreement" (a cancelled divestiture) read as customer loss.
- "integration expenses and ... previously announced planned exit" read as divestiture.
- Marketing initiative with a partner ("introducing The Family Fit Factor") read as a product launch.

## Collection defects seen
- TGS monthly archive listing pages (/press-releases/archive/2026/08) collected as articles; their
  headlines get the listing's date. CLMB RSS feed collected as an article.
- 15 of 32 sampled companies had 7+ dated own-site articles.

## Takeaway
Hand-written regex rules keep chasing phrasing: each round fixes what it sees and the fresh-data
score moves a few points. Options for the next round: (1) keep rules for high-precision types
(guidance, acquisition, credit) and add a reviewed LLM classifier for the rest, with these four label
sets as its test set; (2) or keep rules but measure only on fresh holdouts and accept ~60%/40-50%.
