# Held-out A (10 new companies): misses for the NEXT round (rules frozen this round)

Score (article x event type, blind labels): precision 12/20 = 60% (63% if BMRN P11, a retrospective
interview mention of a past acquisition, is treated as borderline); recall 12/31 = 39%.

## Structural bug (highest priority)
- Every `[^.!?]{0,N}` window stops at a decimal point: "has been awarded a $2.2 million contract",
  "Awarded $1.7 Million Contract" never match. Affects all event types. Fix: treat a period between
  digits (and in abbreviations already protected by sentences()) as non-terminal inside windows.

## False negatives
- SMID P4/P8 new_contract: decimal bug (above). P7: "Secures $10 Million Contract" (present-tense
  "secures"). P10: "has been awarded three ... projects" (object "projects").
- CDNL P5 acquisition: "announced today the closing of its acquisition of Allied" (noun form
  "closing of its acquisition"). P12 market_expansion: "expanding our footprint into Georgia",
  "first geographic expansion beyond North Carolina". P14 credit_positive: "second amendment to its
  senior secured credit agreement", "raises the revolving credit facility".
- RAMP P9: "LiveRamp Partners with Adobe", "announced a new integration". P7: "first measurement
  partner in LiveRamp" (company as partner, passive). P10: "opens its agent network ... with new LAB
  program" (title only). P12: "expanded its Cross-Media Intelligence solution", "Adds Meta to ...".
- LEE P4: "announced today the launch of an expansive suite of AI-powered solutions" (launch-of rule
  needs a capitalized name or "new" right after "of"). P6: "TownNews and Tekan announce an exclusive
  partnership" (base-form "announce"; actor is a majority-owned subsidiary, not in company tokens);
  "a major expansion into the Canadian market" (noun form). P7: title-only product article.
- KNTK P13 market_expansion: "reached final investment decision on Kings Landing II ... processing
  plant" (FID not covered). P16 new_contract: "Amended gas gathering and processing agreements with
  the two largest customers ... that extend the terms"; divestiture: "the sale of the Company's equity
  interest in EPIC Crude" (noun form).

## False positives
- CDNL P11 new_contract: "entered into an agreement and plan of merger" (add "plan of merger" to
  contract exclusions).
- CDNL P14 market_expansion: "Completes Syndication of Expanded Credit Facility" ("facility" as a site
  object; exclude credit/loan facility).
- CDNL P5 market_expansion: "The acquisition expands ... capabilities in the Atlanta market"
  (capabilities in an existing market).
- BMRN P8 market_expansion: employee profile, "solutions that expand access across the countries".
- BMRN P11 acquisition: interview mentions a past acquisition (retrospective; borderline).
- LEE P3 hiring (careers page): "We strive to hire talented and dedicated people" ("people" added to
  hiring objects is too broad after "to hire").
- INOD P16 funding_round: "The company raised over a billion dollars in seed funding" where "the
  company" is another firm (AMI Labs); self-reference words are trusted blindly.
- FA P5 hiring: industry statistic "Total staffing employment ... adding approximately 12,000 jobs".

## Collection observations from the same sample
- 13 of 32 sampled companies had 7+ dated own-site articles; 19 had few or none (homepage failures,
  no news link found, JS listings).
- Own-site "news" is often non-event content: STRL (all conference/earnings-date notices), MRTN and
  BMRN (blogs, employee stories), FA (awards, regulatory digests), INOD (research blog).
- INOD P10 is a cnet.com article collected as a company article (off-site page).
