# Data issues log

Problems found in source data, and how each is fixed. Fixes are made by
transformation scripts that produce a new snapshot, never by editing files.

## 1. BrightView SIC code lost its leading zero (fixed in company_list_v2)

- **Found:** 2026-10-17.
- **Row:** BrightView Holdings, Inc. (IQ568706872), a commercial landscaping
  company.
- **Problem:** its SIC code is 0700 (Agricultural Services). The spreadsheet
  stored it as the number 700, dropping the leading zero, and the 2- and
  3-digit codes were then derived from that as 70 and 700. That put a
  landscaper in SIC 70 (Hotels and Lodging) with Airbnb, Marriott Vacations,
  and St. Joe.
- **Scope:** checked all 560 rows: BrightView is the only 3-digit SIC code,
  and every other row's 2/3-digit codes agree with its 4-digit code.
- **Fix:** `src/prepare_company_list.py` loads SIC codes as text, zero-pads
  them to 4 characters, and re-derives the 2- and 3-digit codes. In v2,
  BrightView is 0700 / 070 / 07. Cells changed are listed in
  data-local/snapshots/company_list_v2_sic_fixed_changes.csv.
- **Prevention:** all code loads the list through
  `src/project_data.normalize_sic_codes`, so a raw copy can't reintroduce the
  error. When exporting from the sheet, format SIC columns as text.

## 2. Smith Douglas Homes has no website (fixed in company_list_v3)

- **Found:** 2026-10-17, during the full scrape.
- **Row:** Smith Douglas Homes Corp. (IQ328847166). `target_ciq_website` is `0`.
- **Effect:** nothing can be collected; its profile is all "unknown".
- **Fix:** www.smithdouglas.com, supplied by the team (WEBSITE_FIXES in
  `src/prepare_company_list.py`). Re-scraped 2026-10-17: ok.

## 3. Investor-relations websites (partly fixed in company_list_v3)

- **Found:** 2026-10-17, during the full scrape.
- **Rows:** Avista (`investor.avistacorp.com`), Black Hills
  (`ir.blackhillscorp.com`), Herc Holdings (`ir.hercrentals.com`), Wingstop
  (`ir.wingstop.com`).
- **Problem:** Aziz's rule excludes investor-relations pages: a private
  company has none, and IR text describes the stock, not the business.
  Wingstop's IR pages were scraped as "ok"; the other three came back thin.
- **Fix:** `src/prepare_company_list.py` replaces IR hosts with the main
  domain (ir.wingstop.com → wingstop.com). Herc and Wingstop re-scraped: ok.
- **Still open:** for some companies the main domain itself redirects to the
  IR site, so there is no non-IR corporate page: Avista (avistacorp.com),
  Black Hills (blackhillscorp.com), and, found by scanning all pages,
  Simpson Manufacturing (simpsonmfg.com) and IAC (iac.com →
  ir.people-incorporated.com). The scraper now refuses IR hosts, including
  via redirects (status `investor_site`), so these four are all "unknown"
  until the team supplies an operating-business website for each.
