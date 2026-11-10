"""Append the executed integration study to the existing v1 results notebook."""

from __future__ import annotations

from pathlib import Path

import nbformat as nbf


ROOT = Path(__file__).resolve().parents[2]
NOTEBOOK = ROOT / "v1/notebooks/comps_and_valuation.ipynb"
TAG = "integrated-v1-2026-11-09"


def md(source: str):
    cell = nbf.v4.new_markdown_cell(source.strip())
    cell.metadata["tags"] = [TAG]
    return cell


def code(source: str):
    cell = nbf.v4.new_code_cell(source.strip())
    cell.metadata["tags"] = [TAG]
    return cell


def extension() -> list:
    return [
        md("""
## 13. Integrated v1 inputs and source alignment

This continuation runs the shared v1 components in order: source alignment, current business scope, facet construction, candidate retrieval, peer assessment, financial factors, valuation, growth signals, and error analysis. The **533-company public-as-private sample** uses the fixed 373/160 SIC2 split. A larger public catalog is a separate retrieval experiment. Financial multiples enter only after peers are chosen. Scores describe this development sample, not actual private-company accuracy.

All new language-model decisions use **GPT-6.1 Sol through the locally authenticated Codex CLI**. Call concurrency is recorded per run. Text embeddings use the local `all-mpnet-base-v2` model on the available GPU; retrieval, fitting, valuation and metrics are deterministic Python computations. Input and model fingerprints govern reuse; every reused embedding is compared numerically with the installed model.

Inputs and scripts are pinned in `outputs-local/v1/integration/`; rerun the corresponding `v1/scripts/integration_*.py` modules to rebuild each table. The existing v1 sections above retain the team's original four selection routes and holdout results.
"""),
        code("""
from pathlib import Path
import json
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from IPython.display import display

ROOT = next(p for p in (Path.cwd(), *Path.cwd().parents)
            if (p / 'v1/scripts').exists() and (p / 'outputs-local/v1').exists())
V1 = ROOT / 'outputs-local/v1'
I = V1 / 'integration'
manifest = json.loads((I / 'sources/manifest.json').read_text(encoding='utf-8'))
display(pd.DataFrame([{'input': x['path'], 'sha256': x['sha256'][:12]}
                      for x in manifest['inputs']]))
"""),
        md("""


`IQ_COMPANY_ID` is the one-company key. The fixed Capital IQ snapshot contains 560 firms; the v1 eligibility rule retains 533. Barbara's published catalog maps each of those 533 IDs to one economic-group key, with 71 catalog mappings held for identity review. Her profile shards and 5,600 saved matches are versioned separately. A private target may supply its website, business description and, when available, revenue, EBITDA or debt; public-only listing fields and target multiples are excluded from retrieval. Sources: [data dictionary](../../docs/data_dictionary.md), [Barbara's research site](https://barbara069.github.io/private-company-comparables-research/).

Yifan's Orbis facet list distinguishes direct payers from users and adds diversification and growth fields. The crosswalk below keeps partial definitions separate. The shared WRDS ratio workbook covers 504 tickers; its firm-level ratios are public-peer or research controls, not private-target inputs. Exact ticker and a company-name similarity check are required before comparing values; WRDS and Capital IQ multiples are not assumed to share a measurement date or denominator. Sources: [Yifan's Orbis field audit](https://docs.google.com/spreadsheets/d/19JNq9CXaEjUzQlALIy6d1Edt3gGH_NKP/edit), [WRDS firm ratios](https://drive.google.com/file/d/14NvyjcLDPbrm4fGh03xJpMrAJ9Q-VeqB/view), [WRDS product description](https://wrds-www.wharton.upenn.edu/pages/grid-items/financial-ratios-firm-level/).
"""),
        code("""
source = manifest['barbara_catalog']
display(pd.DataFrame([{'source': 'v1 eligible companies', 'count': 533},
                      {'source': 'Barbara economic groups', 'count': source['catalog_groups']},
                      {'source': 'groups passing identity filter', 'count': source['eligible_groups']},
                      {'source': 'baseline IDs mapped once', 'count': source['baseline_ids_mapped']},
                      {'source': 'published match rows', 'count': len(pd.read_csv(I / 'barbara_matches/published_rankings.csv'))}]))
fields = json.loads((I / 'fields/summary.json').read_text(encoding='utf-8'))
display(pd.DataFrame([{'ticker matches passing name check': fields['ticker_name_agreement'],
                       'dated 2025 WRDS multiples': fields['matched_2025_nonmissing_evm'],
                       'FF49 groups': fields['wrds_2025_ff49_groups'],
                       'cross-source median absolute multiple difference':
                           fields['wrds_evm_vs_capiq_multiple_median_absolute_difference']}]))
crosswalk = pd.read_csv(I / 'fields/yifan_facet_crosswalk.csv')
display(crosswalk[['orbis_facet', 'v1_field', 'relation', 'definition_note']])
"""),
        md("""
## 14. Current business scope

Yiming's dated exit check changes only a facet whose **old text exactly matches** the saved Sonnet fill and whose completed exit has acceptable evidence. It applies 116 values across 42 firms; 44 review rows stay visible. The company retains one ID and all current businesses. The source-audited ten-company benchmark tests activity status and economic grouping. A separate blind GPT-6.1 Sol scope check uses the same activity names and only cited saved website lines, with the reference labels withheld. Only two of the ten cases had a benchmark reference page among those saved lines, so this check also measures evidence availability. The 293-pair score and 160-target multiple test measure downstream effects. The team's separate 40-company sensitivity test excludes source-confirmed mixed-business *peers* from the saved earlier holdout routes; it is a diagnostic, not the current GPT route. Sources: [Yiming's check](https://drive.google.com/file/d/1-yKpdRVMDSjGCnLUQh0fuqvqJeT-Kmw4/view), [business-scope rule](../GOLDEN_SET_ROUND2.md), [implementation](../scripts/integration_sources.py), [saved sensitivity code](../scripts/source_scope_sensitivity.py).
"""),
        code("""
scope = pd.read_csv(I / 'scope_eval/peer_metrics.csv')
value = pd.read_csv(I / 'scope_eval/valuation_summary.csv')
audit = json.loads((V1 / 'business_structure_refinement/source_benchmark/summary.json').read_text(encoding='utf-8'))
display(pd.DataFrame([{'check': 'current activity labels', 'saved': audit['activity_correct_saved'],
                       'source-corrected': audit['activity_correct_refined'], 'total': audit['activity_labels']},
                      {'check': 'exact business groups', 'saved': audit['group_exact_saved'],
                       'source-corrected': audit['group_exact_refined'], 'total': audit['group_reference_cases']}]))
display(scope[['method', 'labeled pairs', 'pairwise accuracy', 'reviewed_good_selected',
               'reviewed_bad_selected']].rename(columns={'pairwise accuracy': 'pairwise_accuracy'}))
display(value[['comp rule', 'targets', 'median abs % error']])
gpt_scope = json.loads((I / 'gpt_scope_eval/summary.json').read_text(encoding='utf-8'))
display(pd.DataFrame([gpt_scope]))
display(pd.read_csv(I / 'gpt_scope_eval/evidence_overlap.csv'))
display(pd.read_csv(I / 'gpt_scope_eval/group_partitions.csv'))
display(pd.read_csv(V1 / 'holdout_completion/evaluation/source_scope_sensitivity/sensitivity.csv')[
    ['route', 'source-audited mixed peers', 'affected targets',
     'original coverage', 'filtered coverage', 'affected median paired change']])
"""),
        md("""
The 116 dated Sonnet edits cannot be copied verbatim into independently generated GPT text. We compare each fresh GPT field with the activity removed by Yiming's edit, then check flagged fields against the named completed divestiture. Primary company releases show that National Healthcare Properties retained outpatient medical assets after a partial sale and Ensign still operated senior living after the Pennant separation. Ensign's home-health and hospice operations were transferred to Pennant; Timken's belts business and Skillsoft's Global Knowledge business were sold. Skillsoft continues to offer training access through a reseller partnership. The integrated default makes ten field-level corrections across HLTC, ENSG and SKIL; TKR was already current in the Sonnet input. B3 retrieval, four selection routes, factors and valuation are rerun below. GPT general and other historical conditions retain their frozen fields, including flagged stale descriptions; they are comparison inputs, not current-scope defaults. This is a targeted four-company source review, not a factual audit of all 533 firms. Sources: [alignment audit](../scripts/integration_gpt_scope_alignment.py), [NHP announcement](https://investors.nhpreit.com/Investors/investor-news/news-details/2026/National-Healthcare-Properties-Announces-Definitive-Agreement-to-Sell-40-Additional-Outpatient-Medical-Facilities-for-531-Million-Signs-LOI-for-Remaining-Four-OMFs-and-Provides-SHOP-Acquisition-Pipeline-Update/default.aspx), [Ensign current operations](https://investor.ensigngroup.net/news/news-details/2026/The-Ensign-Group-Adds-New-Operations-in-Colorado/default.aspx), [Pennant separation](https://investor.ensigngroup.net/news/news-details/2019/The-Ensign-Group-Inc.-Announces-Record-and-Distribution-Dates-for-Pennant-Spin-Off-08-28-2019/default.aspx), [Timken release](https://news.timken.com/2026-09-28-Timken-Completes-Sale-of-Belts-Business-to-Gates), [Skillsoft sale](https://investor.skillsoft.com/news-events/press-releases/detail/457/skillsoft-completes-sale-of-global-knowledge-business-advancing-focus-on-ai-native-skills-management-platform), [reseller agreement](https://investor.skillsoft.com/sec-filings/all-sec-filings/content/0001437749-26-017991/ex_965969.htm).
"""),
        code("""
scope_alignment = pd.read_csv(I / 'gpt_scope_alignment/alignment.csv')
display(scope_alignment.groupby('status').size().rename('fields').to_frame())
scope_specificity = pd.read_csv(I / 'gpt_scope_alignment/specificity.csv')
display(scope_specificity.groupby(['general', 'cited'], dropna=False).size().rename('fields').to_frame())
display(scope_specificity[scope_specificity['general'].eq('specific_outdated')][
    ['ticker', 'facet', 'general', 'cited', 'reason_y']])
display(pd.read_csv(I / 'gpt_scope_alignment/source_exceptions.csv')[
    ['ticker', 'activity', 'decision', 'source_date', 'url']])
display(pd.read_csv(I / 'gpt_scope_alignment/sensitivity/comparison.csv')[
    ['variant', 'good_selected', 'good_total', 'bad_selected',
     'valuation_targets', 'median_ape']])
display(pd.read_csv(I / 'gpt_scope_alignment/sensitivity/paired.csv')[
    ['old', 'new', 'targets', 'changed_peer_lists', 'median_paired_gain']])
default_scope = json.loads((I / 'source_reviewed_default/run.json').read_text(encoding='utf-8'))
display(pd.DataFrame([default_scope]))
display(pd.read_csv(I / 'source_reviewed_default/changes.csv')[
    ['ticker', 'facet', 'before', 'after', 'primary_source']])
display(pd.DataFrame([json.loads((I / 'source_reviewed_default/scope_comparison.json')
                            .read_text(encoding='utf-8'))]))
"""),
        md("""
## 15. Facet construction and model comparison

The original whole-company facets are the common base. Fiona adds sector and sub-sector descriptions; Barbara adds SIC2-specific fields. Missing or inapplicable fields do not receive a match score. The saved Haiku/Sonnet fills and 48 B3 configurations are compared on Barbara's 293 graded pairs and the same 160 development valuation targets. Pair ranking, good-peer retention and multiple error can disagree; no variant is chosen from the 160 targets as a final test. GPT-6.1 Sol fills use the same general, sector and SIC2 schemas in separate local runs; fill count alone is not factual accuracy. Sources: [facet definitions](../scripts/facets.py), [Fiona's sector model](../scripts/sector_facets.py), [Barbara's SIC2 dictionary](../scripts/reference/sic2_industry_facet_dictionary.md), [B3 ablation](../scripts/b3_facet_add_drop.py).
"""),
        code("""
facet_runs = [('Haiku general', 'facets/tables/facets.csv'),
              ('Sonnet general', 'facets_sonnet/tables/facets.csv'),
              ('Sonnet current-scope general', 'integration/sources/facets_sonnet_corrected.csv'),
              ('Sonnet source-reviewed default', 'integration/source_reviewed_default/facets.csv'),
              ('Fiona sector', 'sector_facets_sonnet/tables/sector_facets.csv'),
              ('Barbara SIC2', 'industry_facets_sonnet/tables/industry_facets_long.csv'),
              ('GPT-6.1 Sol general', 'facets_codex_gpt61sol/tables/facets.csv'),
              ('GPT-6.1 Sol sector', 'sector_facets_codex_gpt61sol/tables/sector_facets.csv'),
              ('GPT-6.1 Sol SIC2', 'industry_facets_codex_gpt61sol/tables/industry_facets_long.csv')]
display(pd.DataFrame([{'facet_source': name, 'company_count': pd.read_csv(V1 / path)['IQ_COMPANY_ID'].nunique()
                       if (V1 / path).exists() else 0} for name, path in facet_runs]))
display(pd.DataFrame([json.loads((I / 'embedding_audit.json').read_text(encoding='utf-8'))]))
variants = pd.read_csv(V1 / 'facet_add_drop/current/metrics.csv')
display(variants[variants['label_source'] == 'human_majority'][
    ['variant', 'labeled_pairs', 'pairwise_accuracy', 'good_recall']].head(12))
reviewed_variants = pd.read_csv(I / 'facet_293/metrics.csv')
display(reviewed_variants.sort_values('pairwise_accuracy', ascending=False)[
    ['variant', 'labeled_pairs', 'pairwise_accuracy', 'good_recall',
     'labeled_bad_selected']].head(12))
facet_values = pd.read_csv(I / 'facet_valuation/summary.csv')
facet_values = facet_values[facet_values['rule'] == 'top 10 weighted mean']
facet_compare = reviewed_variants.merge(facet_values[['variant', 'median abs % error']],
                                        on='variant', validate='one_to_one')
display(facet_compare[facet_compare['variant'].isin([
    'B3 Haiku', 'B3 Sonnet', 'B3 Corrected', 'Sonnet + Fiona categories',
    'Sonnet + Barbara SIC2 facets', 'Corrected + all additions'])][
    ['variant', 'pairwise_accuracy', 'good_recall', 'labeled_bad_selected',
     'median abs % error']])
fig, ax = plt.subplots(figsize=(6.5, 4))
ax.scatter(facet_compare['pairwise_accuracy'], facet_compare['median abs % error'],
           c=facet_compare['good_recall'], cmap='viridis', vmin=.7, vmax=1, s=36)
for name in ('B3 Sonnet', 'B3 Corrected', 'Sonnet + Fiona categories',
             'Sonnet + Barbara SIC2 facets'):
    row = facet_compare.set_index('variant').loc[name]
    ax.annotate(name, (row['pairwise_accuracy'], row['median abs % error']),
                xytext=(4, 4), textcoords='offset points', fontsize=7)
ax.set(xlabel='Pairwise accuracy, Barbara 293',
       ylabel='Median absolute multiple error (%), 160 targets')
plt.tight_layout(); plt.show()
"""),
        md("""
Matthew and Richard's saved selector test holds B3 candidates, general facets and prompt fixed while changing Haiku to Sonnet. The screen agrees on 92% of 2,396 pairs; direct selections differ more. The reviewer comparison below covers only the two labeled round-1 targets, so it is a model-choice diagnostic rather than a holdout valuation result. Source: [model-selection evaluation](../scripts/model_selection_eval.py).
"""),
        code("""
model_dir = V1 / 'model_selection/2026-11-05T015952Z'
display(pd.read_csv(model_dir / 'model_agreement.csv'))
model_gold = pd.read_csv(model_dir / 'golden_majority.csv')
display(model_gold[model_gold['method'].str.startswith('direct ')][
    ['method', 'target', 'listed', 'good listed', 'good total', 'non-comps listed']])
"""),
        md("""
The 40-company historical review cohort supplies a fixed set of firms for fresh checks of both GPT general versions. For each facet, Yifan and Richard's tier-R BM25 step retrieves up to eight relevant company-site lines. GPT-6.1 Sol applies the team's five-way evidence rubric; uncited judgments are discarded by the existing verifier. These judgments identify claims to inspect, but they are not human accuracy labels for the new GPT values. Sources: [tier-R retrieval](../scripts/verification/retrieve.py), [evidence verifier](../scripts/verification/verify_with_evidence.py).
"""),
        code("""
claim_run = json.loads((I / 'claim_check/run.json').read_text(encoding='utf-8'))
claim_checks = pd.read_csv(I / 'claim_check/verdicts.csv')
claim_cited = pd.read_csv(I / 'claim_check_cited/verdicts.csv')
display(pd.DataFrame([claim_run, json.loads((I / 'claim_check_cited/run.json').read_text(encoding='utf-8'))]))
display(pd.concat([claim_checks.assign(source='memory-first'),
                   claim_cited.assign(source='cited-only')])
        .groupby(['source', 'verdict']).size().unstack(fill_value=0))
claim_focus = pd.concat([claim_checks.assign(source='memory-first'),
                         claim_cited.assign(source='cited-only')])
display(claim_focus[claim_focus['verdict'].isin(['partly', 'contradicted', 'not_found', 'missed'])][
    ['source', 'ticker', 'facet', 'verdict', 'cite', 'reason']].head(20))
"""),
        md("""
### Source-cited and Orbis-aligned alternatives

The first GPT general pass uses model knowledge, following the team's original fill protocol. A separate pass keeps only facets citing company-site lines. Thirteen firms have no usable saved lines; the source pass checks official-site search results for them and leaves unsupported fields unknown. The refreshed results were retrieved after the 2026-10-25 financial snapshot, so this comparison is not a point-in-time backtest. Yifan's eleven qualitative Orbis fields are extracted independently under her definitions; direct payers are not inferred from the broader customer-segment field. The source-only and Orbis alternatives are measured with the same peer and valuation labels. These are evidence-coverage and development tests, not verified private-company records. Sources: [Yifan's field audit](https://docs.google.com/spreadsheets/d/19JNq9CXaEjUzQlALIy6d1Edt3gGH_NKP/edit), [Attribute or Abstain](https://aclanthology.org/2024.emnlp-main.463/).
"""),
        code("""
yifan_run = json.loads((I / 'yifan_facets/run.json').read_text(encoding='utf-8'))
display(pd.DataFrame([
    {'facet_source': 'GPT memory-first', 'companies_with_values':
     pd.read_csv(V1 / 'facets_codex_gpt61sol/tables/facets.csv')['llm_status'].eq('ok').sum(),
     'site_evidence_required': False},
    {'facet_source': 'GPT source-cited', 'companies_with_values': int(pd.read_csv(
     I / 'source_facet_eval/coverage.csv').set_index('variant').loc[
     'GPT cited-only', 'companies_with_any_facet']),
     'site_evidence_required': True},
    {'facet_source': 'Yifan Orbis-aligned', 'companies_with_values': yifan_run['status_counts'].get('ok', 0),
     'site_evidence_required': True}]))
quality = json.loads((I / 'facet_quality/summary.json').read_text(encoding='utf-8'))
display(pd.DataFrame([{'facet_source': name, **totals} for name, totals in quality.items()]))
display(pd.read_csv(I / 'web_evidence/coverage.csv'))
source_peer = pd.read_csv(I / 'source_facet_eval/reviewed_metrics.csv')
source_value = pd.read_csv(I / 'source_facet_eval/valuation_summary.csv')
display(source_peer[['variant', 'labeled_pairs', 'pairwise_accuracy', 'good_recall']])
display(source_value[['comp rule', 'targets', 'median abs % error']])
display(pd.read_csv(I / 'source_facet_eval/paired_comparison.csv'))
display(pd.read_csv(I / 'source_facet_eval/coverage.csv'))
yifan_peer = pd.read_csv(I / 'yifan_eval/reviewed_metrics.csv')
yifan_value = pd.read_csv(I / 'yifan_eval/valuation_summary.csv')
display(yifan_peer[['variant', 'pairwise_accuracy', 'good_recall',
                    'labeled_bad_selected']])
display(yifan_value[['comp rule', 'targets', 'median abs % error']])
display(pd.read_csv(I / 'yifan_eval/coverage.csv'))
"""),
        md("""
## 16. Candidate construction

B0–B3, M2, TF-IDF, SIC pool restrictions, whole-profile MPNet/TF-IDF/LSA/rank fusion, Ward's tree and UMAP/HDBSCAN groups are rerun separately on corrected Sonnet and GPT whole-company fields. All rank the same 373 eligible training peers and use the same 293 reviewer pairs and 160 development valuation targets. The unsupervised tree and density partitions see all 533 business descriptions but no labels or multiples. B3 blends facet-level embedding and TF-IDF similarity; its standard list retains mutual top-ten peers with a three-peer top-up. The tree and density rules gate whole-profile cosine ranks; cluster outliers use the team's mutual-neighbor fallback. Strict SIC restrictions may return no peer. The earlier activity/transport caches used a different candidate pool; they are not imported into this comparison. A **separate candidate-universe experiment** searches Barbara's 38,788 eligible groups with website excerpts using TF-IDF or MPNet; Barbara's own published top-ten lists use 30,416 descriptions and are a different pool. Published text-based industry and M&A peer-selection studies motivate testing business text beside industry codes, but do not establish private-company performance here. Sources: [B3 and M2 code](../scripts/facet_weighting.py), [team tree and cluster selectors](../../pre-v0/matching/peer_selectors.py), [retrieval comparison](../scripts/integration_candidate_methods.py), [Sentence-BERT](https://aclanthology.org/D19-1410/), [LSA](https://asistdl.onlinelibrary.wiley.com/doi/10.1002/%28SICI%291097-4571%28199009%2941%3A6%3C391%3A%3AAID-ASI1%3E3.0.CO%3B2-9), [RRF](https://cormack.uwaterloo.ca/cormacksigir09-rrf.pdf), [Ward](https://iv.cns.iu.edu/sw/data/ward.pdf), [UMAP](https://arxiv.org/abs/1802.03426), [HDBSCAN](https://doi.org/10.1007/978-3-642-37456-2_14), [Hoberg and Phillips](https://www.journals.uchicago.edu/doi/full/10.1086/688176), [M&A peer selection](https://www.sciencedirect.com/science/article/pii/S0304405X21003834), [Barbara's published results](https://barbara069.github.io/private-company-comparables-research/).
The same 20 fixed-pool retrieval methods are also evaluated with the source-cited GPT facets under the same twelve-field schema.
The twenty-method runner reads the twelve common fields. It is rerun on the source-reviewed default; Fiona's and Barbara's additions enter B3 through separate similarity matrices. Their twelve GPT facet conditions are not attributed to the other nineteen original methods. The common-field methods retain the same 373-peer pool and saved evaluator.
"""),
        code("""
base_candidates = pd.read_csv(I / 'candidate_methods/reviewed_metrics.csv')
base_valuation = pd.read_csv(I / 'candidate_methods/valuation_summary.csv')
display(base_candidates.merge(base_valuation[['comp rule', 'targets', 'median abs % error']],
                              left_on='method', right_on='comp rule', validate='one_to_one',
                              suffixes=('_reviewed', ''))[
    ['method', 'targets', 'pairwise accuracy', 'good_recall',
     'bad_selected', 'median abs % error']])
default_retrieval = pd.read_csv(I / 'source_reviewed_default/retrieval/reviewed_metrics.csv')
default_retrieval_value = pd.read_csv(I / 'source_reviewed_default/retrieval/valuation_summary.csv')
display(default_retrieval.merge(default_retrieval_value[
    ['comp rule', 'targets', 'median abs % error']], left_on='method',
    right_on='comp rule', validate='one_to_one')[
    ['method', 'targets', 'pairwise accuracy', 'good_recall',
     'bad_selected', 'median abs % error']])
gpt_retrieval = pd.read_csv(I / 'candidate_methods_gpt/reviewed_metrics.csv')
gpt_retrieval_value = pd.read_csv(I / 'candidate_methods_gpt/valuation_summary.csv')
display(gpt_retrieval.merge(gpt_retrieval_value[['comp rule', 'targets', 'median abs % error']],
                            left_on='method', right_on='comp rule', validate='one_to_one',
                            suffixes=('_reviewed', ''))[
    ['method', 'targets', 'pairwise accuracy', 'good_recall',
     'bad_selected', 'median abs % error']])
cited_retrieval = pd.read_csv(I / 'candidate_methods_cited/reviewed_metrics.csv')
cited_retrieval_value = pd.read_csv(I / 'candidate_methods_cited/valuation_summary.csv')
display(cited_retrieval.merge(cited_retrieval_value[['comp rule', 'targets', 'median abs % error']],
                              left_on='method', right_on='comp rule', validate='one_to_one',
                              suffixes=('_reviewed', ''))[
    ['method', 'targets', 'pairwise accuracy', 'good_recall',
     'bad_selected', 'median abs % error']])
paired_retrieval = pd.read_csv(I / 'retrieval_paired/comparison.csv')
display(paired_retrieval[['method', 'common_targets', 'gpt_gain_percentage_points',
                          'gain_ci_low', 'gain_ci_high']])
expanded = [json.loads((I / f'expanded_pool/{name}/summary.json').read_text(encoding='utf-8'))
            for name in ('tfidf', 'mpnet')]
published = json.loads((I / 'barbara_matches/manifest.json').read_text(encoding='utf-8'))['summary']
candidate_results = pd.DataFrame([
    {'route': x['method'], 'pool': x['pool_groups'], 'reviewed_pairs_with_eligible_groups': x['reviewed_pairs_mapped'],
     'reviewed_good_in_top10': x['reviewed_good_top10'], 'reviewed_good_total': x['reviewed_good_total']}
    for x in expanded] + [
    {'route': 'Barbara published top ten', 'pool': published['published_universe_descriptions'][0],
     'reviewed_pairs_with_eligible_groups': published['reviewed_pairs_mapped'],
     'reviewed_good_in_top10': published['good_top10'], 'reviewed_good_total': published['good_total']}])
display(candidate_results)
fig, ax = plt.subplots(figsize=(7, 3))
ax.barh(candidate_results['route'], candidate_results['reviewed_good_in_top10'] /
        candidate_results['reviewed_good_total'], color='#386b81')
ax.set(xlabel='Reviewed good peers retrieved in top ten / eligible reviewed good peers', xlim=(0, .2))
plt.tight_layout(); plt.show()
"""),
        md("""
The ranking diagnostics below use only Barbara's graded peers. Precision@3 and nDCG@3 reorder the graded subset within each target; a target needs at least three graded candidates. Their denominators exclude unlabeled peers, so these values cannot be interpreted as full-pool precision. The table also reports how many graded pairs fall in each method's actual top ten. Source: [ranking calculation](../scripts/integration_reviewed_ranks.py).
"""),
        code("""
reviewed_ranks = pd.read_csv(I / 'reviewed_rank_metrics.csv')
display(reviewed_ranks[reviewed_ranks['method'].eq('B3 embedding plus TF-IDF')][
    ['facet_source', 'reviewed_pairs_ranked', 'targets_with_three_reviewed_peers',
     'labeled_precision_at_3', 'labeled_ndcg_at_3', 'reviewed_pairs_in_actual_top_10']])
compatibility = pd.read_csv(I / 'retrieval_compatibility.csv')
display(compatibility.groupby('specialized_facet_conditions').agg(
    methods=('method', 'count'), common_field_sources=('common_field_source_runs', 'first')))
"""),
        md("""
The fixed z cutoffs above are unsupervised. A separate supervised rule chooses one B3 z cutoff from 2.0–5.0 using Barbara's 293 training-pair labels. Each of the 45 reviewer targets is held out while its cutoff is chosen on the other 44; balanced accuracy treats good and bad pairs equally, with ties favoring recall. The final cutoff is refit on all 45 targets, then applied to the 160 development targets without forcing a peer count. Coverage and error are compared with fixed B3 on the same targets. This sparse reviewed set may not represent all candidate pairs. Source: [cross-validation](https://academic.oup.com/jrsssb/article/36/2/111/7027414), [threshold implementation](../scripts/integration_thresholds.py).
"""),
        code("""
cutoff = json.loads((I / 'thresholds/run.json').read_text(encoding='utf-8'))
display(pd.DataFrame([{'threshold': cutoff['final_threshold'],
                       'crossfit_balanced_accuracy': cutoff['crossfit_balanced_accuracy'],
                       'crossfit_good_recall': cutoff['crossfit_good_recall'],
                       'crossfit_bad_kept': cutoff['crossfit_bad_kept'],
                       'holdout_targets_with_peers': cutoff['holdout_targets_with_peers']}]))
display(pd.read_csv(I / 'thresholds/valuation_summary.csv')[
    ['comp rule', 'targets', 'median abs % error']])
display(pd.read_csv(I / 'thresholds/paired_comparison.csv'))
"""),
        md("""
The paired retrieval table compares the two facet sources on targets estimated by both. Its bootstrap intervals describe development uncertainty; the general-facet protocols also differ, so the contrast is not an isolated language-model effect. The GPT facet comparison below changes the information supplied to B3 while holding the 373-firm pool, mutual-top-ten rule, reviewer pairs and 160 valuation targets fixed. General, each addition, all additions, and each one-addition removal are reported separately. The best development row is not treated as a final model choice.
"""),
        code("""
gpt_peer = pd.read_csv(I / 'gpt_candidates/reviewed_metrics.csv')
gpt_value = pd.read_csv(I / 'gpt_candidates/valuation_summary.csv')
gpt_compare = gpt_peer.merge(gpt_value[['comp rule', 'targets', 'median abs % error']],
                             left_on='variant', right_on='comp rule', validate='one_to_one',
                             suffixes=('_reviewed', ''))
display(gpt_compare[['variant', 'labeled_pairs', 'pairwise_accuracy', 'good_recall',
                     'labeled_bad_selected', 'targets', 'median abs % error']])
display(pd.read_csv(I / 'gpt_candidates/paired_vs_general.csv')[[
    'variant', 'common_targets', 'gain_vs_general_percentage_points',
    'gain_ci_low', 'gain_ci_high', 'targets_better', 'targets_worse']])
gpt_uncertainty = pd.read_csv(I / 'gpt_candidates/valuation_intervals.csv')
display(gpt_uncertainty[gpt_uncertainty['comp rule'].isin(
    ['GPT general', 'GPT + all additions'])][
    ['comp rule', 'targets', 'median abs % error', 'error 2.5%', 'error 97.5%',
     'gain on baseline', 'gain 2.5%', 'gain 97.5%']])
fig, ax = plt.subplots(figsize=(7, 3.7))
ax.barh(gpt_compare['variant'], gpt_compare['median abs % error'], color='#477c8b')
ax.invert_yaxis(); ax.set(xlabel='Median absolute multiple error (%), same 160 targets')
plt.tight_layout(); plt.show()
"""),
        md("""
### Peer quality on the historical golden set

The 20 fixed-pool retrieval rules are compared on corrected Sonnet, source-reviewed Sonnet, GPT general, and source-cited GPT facets; 12 GPT facet variants add separate B3 conditions. The primary reviewer set has 32 majority-labeled pairs across PCTY and WEN. The 11 unanimous pairs and each reviewer's 36 scores are separate checks; Barbara's 293 scores form a single-reviewer cohort. A reviewed pair absent from the top ten receives rank 11. Good-peer recall counts only labeled grade-1/2 pairs selected; unreviewed pairs are never negatives. The source-reviewed control uses the same fixed company snapshot and split. The two-target majority set is too small to establish a superior method. Sources: [reviewer rubric](../GOLDEN_SET_ROUND2.md), [saved-run replay](../scripts/integration_reviewed_ranks.py), [source-reviewed replay](../scripts/integration_default_golden_eval.py).
"""),
        code("""
golden = pd.read_csv(I / 'golden_method_metrics.csv')
majority = golden[golden['label_source'].eq('human_majority')].copy()
display(majority.sort_values(['good_selected', 'bad_selected', 'pairwise_top10_accuracy'],
                             ascending=[False, True, False])[
    ['facet_source', 'method', 'good_selected', 'good_total', 'bad_selected',
     'bad_total', 'pairwise_top10_accuracy']])
display(golden[golden['method'].isin(['B3 embedding plus TF-IDF', 'GPT general',
                                       'GPT + Fiona categories', 'GPT + all additions'])
               & golden['label_source'].isin(['human_majority', 'human_unanimous'])][
    ['facet_source', 'method', 'label_source', 'good_selected', 'good_total',
     'bad_selected', 'pairwise_top10_accuracy']])
default_gold = pd.read_csv(I / 'source_reviewed_default/golden/metrics.csv')
display(default_gold[default_gold['label_source'].eq('human_majority')][
    ['method', 'good_selected', 'good_total', 'bad_selected',
     'pairwise_top10_accuracy']].sort_values(['good_selected', 'bad_selected'],
                                             ascending=[False, True]))
fig, ax = plt.subplots(figsize=(6.5, 4))
for source, part in majority.groupby('facet_source'):
    ax.scatter(part['bad_selected'], part['good_selected'], label=source, alpha=.75)
ax.set(xlabel='Labeled non-peers selected (of 21)',
       ylabel='Labeled peers selected (of 11)', xlim=(-.5, 21.5), ylim=(-.5, 11.5))
ax.legend(fontsize=8)
plt.tight_layout(); plt.show()
"""),
        md("""
The four selection routes also run on the two historical majority-labeled training targets with fresh GPT general fields. Each target's direct-LLM pool excludes that target. The binary screen evaluates the union of B3 shortlists once per target, then applies its decisions to each facet condition; this shared prompt isolates changes in candidate construction. Direct LLM and LLM→B3 have identical membership, so their peer recall and false selections coincide; B3 only changes the reverse route's order and valuation weights. The reviewer labels are withheld from all prompts. These 32 labeled pairs are a diagnostic, not an independent test. Source: [four-route reviewer comparison](../scripts/integration_golden_routes.py).
"""),
        code("""
golden_routes = pd.read_csv(I / 'golden_routes/metrics.csv')
golden_majority = golden_routes[golden_routes['label_source'].eq('human_majority')]
display(golden_majority.pivot(index='facet_source', columns='method',
                              values='good_selected'))
display(golden_majority.pivot(index='facet_source', columns='method',
                              values='bad_selected'))
display(pd.read_csv(I / 'golden_routes/judge.csv')[
    ['target', 'comp', 'score', 'reason']])
"""),
        md("""
## 17. Peer selection and grading

The baseline notebook above retains cosine, direct LLM, cosine→LLM and LLM→cosine as distinct selection routes. The source-citing judge applies the team's unchanged company-level **0–2 rubric**: 2 = products and customers fit across material current businesses; 1 = meaningful overlap with material unmatched scope; 0 = no meaningful company-level overlap. Barbara's 293 rows are one reviewer, not consensus labels. Her 292 scored overlaps with the saved agent form a diagnostic confusion table; the original 36-pair majority set remains separate. Sources: [rubric](../GOLDEN_SET_ROUND2.md), [judge implementation](../scripts/agent_loop.py), [review data](https://docs.google.com/spreadsheets/d/1LPWjEdTV7-T5BY5eCTqop3JITM6UTSGt/edit).
"""),
        code("""
review = json.loads((I / 'review/summary.json').read_text(encoding='utf-8'))
confusion = pd.read_csv(I / 'review/confusion.csv', index_col=0)
display(pd.DataFrame([review]))
display(confusion)
display(pd.read_csv(V1 / 'agent_loop/gold_05b_web/eval/agreement_human.csv')[
    ['grader', 'pairs', 'exact', 'exact %', 'peer vs not-peer %']])
fig, ax = plt.subplots(figsize=(4, 3))
ax.imshow(confusion, cmap='Blues')
for row in range(3):
    for col in range(3):
        ax.text(col, row, str(confusion.iloc[row, col]), ha='center', va='center')
ax.set(xticks=range(3), yticks=range(3), xlabel='Agent score', ylabel='Barbara score',
       title='0–2 reviewer/agent overlap')
plt.tight_layout(); plt.show()
"""),
        md("""
The GPT-6.1 Sol source-citing judge is run **without reviewer scores in its prompts** on all 293 Barbara pairs. Its two existing policies, keeping grades 1–2 or only grade 2, are tested on the **same 293 reviewed pairs and 45 training targets**. A single reviewer is a diagnostic reference, not a consensus gold standard. The four selection routes then run on the fixed 160 public-as-private targets. All six valuation rows per condition use the same public-peer multiples after peer selection. The source-reviewed default reruns B3 retrieval, direct selection and binary screening using the revised Sonnet fields. The historical `control_sonnet` route uses a GPT-built B3 shortlist with Sonnet text in its LLM prompts, so its difference from the new default is **not** a pure scope effect; the matched B3 scope comparison appears in Section 14. The facet ablations vary only the B3 shortlist while their GPT general prompt and direct selections remain fixed. Sources: [ReAct](https://arxiv.org/abs/2210.03629), [LLM-as-a-judge evaluation](https://arxiv.org/abs/2306.05685), [judge selection](../scripts/integration_judge_selection.py), [holdout routes](../scripts/holdout_batched_routes.py), [valuation code](../scripts/integration_holdout_eval.py).
"""),
        code("""
judge_eval = json.loads((I / 'judge_gpt61sol/eval_293/summary.json').read_text(encoding='utf-8'))
display(pd.DataFrame([judge_eval]))
display(pd.read_csv(I / 'judge_gpt61sol/eval_293/confusion.csv', index_col=0))
display(pd.read_csv(I / 'judge_gpt61sol/eval_293/selection_metrics.csv'))
display(pd.read_csv(I / 'judge_gpt61sol/eval_293/selection_valuation.csv'))
display(pd.read_csv(I / 'judge_gpt61sol/eval_293/selection_paired.csv'))
route_dirs = {'Sonnet content, GPT model': 'control_sonnet',
              'Source-reviewed Sonnet default': 'source_reviewed_default',
              'GPT general': 'gpt_general',
              'GPT all additions, full context': 'gpt_all',
              'GPT + FF49': 'gpt_plus_ff49',
              'GPT + SIC4': 'gpt_plus_sic4',
              'GPT + Fiona sub-sector': 'gpt_plus_fiona_sub-sector',
              'GPT + Fiona categories': 'gpt_plus_fiona_categories',
              'GPT + Barbara SIC2 facets': 'gpt_plus_barbara_sic2_facets',
              'GPT + all additions, retrieval only': 'gpt_all_retrieval',
              'GPT all except FF49': 'gpt_all_except_ff49',
              'GPT all except SIC4': 'gpt_all_except_sic4',
              'GPT all except Fiona sub-sector': 'gpt_all_except_fiona_sub-sector',
              'GPT all except Fiona categories': 'gpt_all_except_fiona_categories',
              'GPT all except Barbara SIC2 facets': 'gpt_all_except_barbara_sic2_facets',
              'GPT general, source exception': 'gpt_scope_exception'}
route_results = []
for label, folder in route_dirs.items():
    table = pd.read_csv(I / 'holdout_routes' / folder / 'evaluation/summary.csv')
    route_results.append(table.assign(facet_condition=label))
route_results = pd.concat(route_results, ignore_index=True)
display(route_results.pivot(index='facet_condition', columns='comp rule',
                            values='median abs % error').round(2))
display(route_results.pivot(index='facet_condition', columns='comp rule',
                            values='targets'))
paired = pd.concat([
    pd.read_csv(I / 'holdout_routes' / folder / 'evaluation/paired_common.csv')
      .assign(facet_condition=label)
    for label, folder in route_dirs.items()], ignore_index=True)
display(paired[paired['method'].isin(['B3 then LLM', 'LLM then B3'])][
    ['facet_condition', 'method', 'common_targets',
     'median_paired_gain_vs_b3', 'gain_ci_low', 'gain_ci_high']])
condition_comparison = pd.read_csv(I / 'holdout_routes/condition_comparison.csv')
display(condition_comparison[condition_comparison['method'].isin([
    'B3 selected', 'B3 then LLM', 'LLM then B3'])][[
    'old_condition', 'new_condition', 'method', 'common_targets',
    'median_gain_percentage_points', 'gain_ci_low', 'gain_ci_high']])
fig, ax = plt.subplots(figsize=(8, 4))
pivot = route_results[route_results['facet_condition'].isin([
    'Sonnet content, GPT model', 'Source-reviewed Sonnet default', 'GPT general',
    'GPT all additions, full context', 'GPT + all additions, retrieval only'])].pivot(
    index='comp rule', columns='facet_condition',
                            values='median abs % error')
pivot.plot.barh(ax=ax); ax.set(xlabel='Median absolute multiple error (%)')
plt.tight_layout(); plt.show()
"""),
        md("""
## 18. Private-supplied factors and valuation

Revenue, EBITDA margin and debt/revenue are **optional target inputs** after business matching; the eight subsets include business-only. Within each B3 top-ten shortlist, each subset reranks peers by empirical percentile distance, then selects 3, 5 or 10 and applies six positive-multiple aggregators. The saved corrected-Sonnet factor study is reproduced exactly; all 144 settings are also run on the source-reviewed default and each of 12 GPT facet shortlists. Peer count is tested rather than fixed: a published multiples study found ten closely selected peers competitive with a whole-industry set in its sample, with a smaller loss at five. The second estimator family fits FF49 pooled OLS, ridge and elastic-net regressions on 373 training firms, with and without qualitative facet categories; hyperparameters use training folds only. Its category and status inputs are exactly unchanged by the scope corrections, so the saved fit remains applicable. All rows below use the same 160 public-as-private development targets. Overall median error and paired wins can rank the factor sets differently, so both are reported. Period, currency, lease and EBITDA definitions require case-level confirmation before a dollar valuation. Sources: [SARD study](https://research.cbs.dk/da/publications/stick-to-the-fundamentals-and-discover-your-peers/), [peer-count study](https://doi.org/10.1111/eufm.12405), [Baker and Ruback](https://www.hbs.edu/ris/Publication%20Files/EstimatingIndustry_b4e64d71-c8fd-4a5e-b31a-623d3a7d02bc.pdf), [Barbara's method memo](https://drive.google.com/file/d/1B32xAUsOAmDMW1U0IoGLYeonRm4Czkbu/view), [factor code](../scripts/integration_factors.py), [cross-condition comparison](../scripts/integration_factor_cross.py).
"""),
        code("""
factor = pd.read_csv(I / 'factors/method_results.csv')
focus = factor[(factor['peer_budget'] == 5) & (factor['aggregation'] == 'median')]
display(focus[['factor_set', 'coverage', 'median_ape', 'mean_paired_delta',
               'targets_better', 'targets_worse', 'targets_equal']]
        .sort_values('median_ape'))
default_factor = pd.read_csv(I / 'source_reviewed_default/factors/method_results.csv')
display(default_factor[default_factor['peer_budget'].eq(5) &
                       default_factor['aggregation'].eq('median')][
    ['factor_set', 'coverage', 'median_ape', 'mean_paired_delta',
     'targets_better', 'targets_worse']].sort_values('median_ape'))
factor_cross = pd.read_csv(I / 'factors_by_facet/comparison.csv')
factor_focus = factor_cross[factor_cross['peer_budget'].eq(5) &
                            factor_cross['aggregation'].eq('median')]
display(factor_focus.pivot(index='factor_set', columns='facet_condition',
                           values='median_ape').round(2))
display(factor_focus[factor_focus['factor_set'].eq('business_only')][
    ['facet_condition', 'coverage', 'median_ape', 'common_targets',
     'mean_paired_gain', 'targets_better', 'targets_worse']])
regression = pd.read_csv(I / 'regression/summary.csv')
display(regression.sort_values('median_ape'))
fig, ax = plt.subplots(figsize=(8, 3.8))
ordered = regression.sort_values('median_ape')
ax.barh(ordered['method'], ordered['median_ape'], color='#557e75')
ax.invert_yaxis(); ax.set(xlabel='Median absolute percentage error (%)', title='Same 160 targets')
plt.tight_layout(); plt.show()
"""),
        md("""
## 19. Growth events and observed outcomes

Xiaozhe's pipeline has three event extractors, a dated-event feature builder, and an observed 1/2/3-year revenue-growth label builder. The ten-company `holdout_c` set tests extraction; its saved pages were captured in October 2026. Features below use events available by 2026-10-19. The separate SEC 10-K revenue table supplies observed outcomes after fiscal 2022. Its large year-on-year changes are flagged for review, not automatically treated as errors. Since the event and outcome cohorts have different dates, this notebook does not fit a growth forecast or score 2026 features against 2022 outcomes. Sources: [growth component](../../pre-v0/growth_signals/README.md), [SEC collector](../../pre-v0/growth_signals/edgar_revenue.py), [saved labels](../../pre-v0/growth_signals/eval/2026-10-19/README.md).
"""),
        code("""
growth = pd.read_csv(I / 'growth/rule_metrics.csv')
display(growth[growth['event_type'] == 'ALL'][
    ['cohort', 'predicted', 'true', 'correct', 'precision', 'recall']])
display(growth[(growth['cohort'] == 'holdout_c') & (growth['event_type'] != 'ALL')][
    ['event_type', 'predicted', 'true', 'correct', 'precision', 'recall']])
"""),
        code("""
growth_llm = pd.read_csv(I / 'growth_llm/holdout_c_metrics.csv')
growth_methods = pd.concat([growth.assign(method='rules'), growth_llm], ignore_index=True)
display(growth_methods[(growth_methods['cohort'] == 'holdout_c') &
                       (growth_methods['event_type'] == 'ALL')][
    ['method', 'predicted', 'true', 'correct', 'precision', 'recall']])
"""),
        code("""
features = pd.read_csv(I / 'growth_llm/holdout_c_features.csv')
display(features.groupby('method', as_index=False).agg(
    companies=('IQ_COMPANY_ID', 'nunique'),
    companies_with_events=('evidence_365d_count', lambda values: int(values.gt(0).sum())),
    events_in_last_365_days=('evidence_365d_count', 'sum')))
outcomes = json.loads((I / 'growth_outcomes/summary.json').read_text(encoding='utf-8'))
display(pd.DataFrame([
    {'universe': '560 source companies', 'cutoff_revenue': outcomes['companies_with_cutoff_revenue'],
     **outcomes['outcome_counts']},
    {'universe': '533 valuation-eligible companies',
     'cutoff_revenue': outcomes['eligible_companies_with_cutoff_revenue'],
     **outcomes['eligible_outcome_counts']}]))
display(pd.DataFrame([{'companies flagged for revenue review, 2022–2025':
                       outcomes['companies_flagged_in_2022_2025']}]))
"""),
        md("""
## 20. Company report and error diagnosis

The input accepts an exact name, ticker, ID or website in the 533-company sample. It returns a ranked ten-peer list, similarity, public-peer multiples and an EV/EBITDA estimate; dollar EV is calculated only if the user supplies positive target EBITDA. The report lists its source files. Kethan's saved-result analysis separately locates historical facet-label mismatch, model disagreement, candidate loss and judge disagreement. These are diagnosis queues, not independent proof of causal error. Sources: [company report code](../scripts/integration_company_report.py), [error-analysis code](../scripts/error_analysis.py).
"""),
        code("""
import sys
sys.path.insert(0, str(ROOT / 'v1/scripts'))
from integration_company_report import report_company

example = report_company('aarcorp.com', method='source_reviewed')
display(pd.DataFrame(example['ranked_peers']))
display(pd.DataFrame([{'company': example['company'],
                       'estimated_EV_EBITDA': example['multiple_estimate'],
                       'target_EBITDA_provided': example['target_ebitda_supplied'],
                       'dollar_EV': example['enterprise_value_estimate']}]))
diagnosis = json.loads((I / 'source_reviewed_default/error_diagnosis/summary.json').read_text(encoding='utf-8'))
display(pd.DataFrame([{'facet_condition': key, **value} for key, value in diagnosis.items()
                      if isinstance(value, dict)]))
errors = pd.read_csv(I / 'source_reviewed_default/error_diagnosis/holdout_target_comparison.csv')
display(errors.sort_values('B3 selected', ascending=False)[
    ['ticker', 'company', 'facet_condition', 'B3 selected', 'B3 then LLM',
     'Direct LLM', 'LLM then B3']].head(12))
display(pd.read_csv(I / 'source_reviewed_default/error_diagnosis/stage_diagnostics.csv'))
"""),
        md("""
## 21. Executed configuration matrix

The full local CSV lists each executed valuation configuration and each golden-label peer-quality comparison, with its facet source, retrieval, selection, grading, factor set, aggregation, coverage and available metric. The 432 peer-quality rows have no valuation error; valuation rows have their own target counts. Different candidate pools or label cohorts are not directly pooled.
"""),
        code("""
matrix = pd.read_csv(I / 'experiment_matrix.csv')
display(matrix.groupby('stage', as_index=False).agg(
    configurations=('configuration', 'size'),
    min_targets=('target_count', 'min'),
    max_targets=('target_count', 'max')))
display(matrix[matrix['stage'].eq('GPT selector routes')][
    ['configuration', 'target_count', 'median_absolute_percentage_error']])
"""),
        md("""
## 22. Interpretation

The source-citing GPT facets attach an official-site line to all 5,188 filled fields. This improves traceability but does not improve the tested matcher: its reviewed-pair accuracy is 0.835 versus 0.868 for memory-first GPT, and its B3 median absolute percentage error is 33.69% on 159 targets versus 33.41% for memory-first GPT on those same targets. The paired uncertainty interval includes zero. None of the 20 tested retrieval rules, sector additions, or reviewer-calibrated threshold has a clear paired valuation advantage. The larger catalog offers more possible peers, but its tested first-pass retrievals miss many reviewed good peers.

On the historical 32-pair majority set, both dated and source-reviewed Sonnet B3 select 10 of 11 labeled peers and one of 21 labeled non-peers. GPT general B3 selects 9 and one; adding Fiona's categories selects 9 and zero. The majority set contains only PCTY and WEN, so this is a peer-quality diagnostic.

On those same two targets, the fresh GPT binary screen keeps only 3 of 11 labeled good peers from the GPT-general B3 shortlist; direct GPT selection lists 5 and no labeled bad peers. LLM→B3 has the same peer membership as direct LLM and changes only order and weights. The shared-union screen is a new inference protocol, so these figures are not a direct reproduction of the saved holdout LLM calls.

Across the 12 GPT B3 shortlists, the eight optional factor sets do not yield one consistently best policy at five peers with median aggregation. Under the source-reviewed Sonnet default, B3 selects peers for all 160 targets and has 34.52% median absolute multiple error. B3→LLM has 33.78% on 105 targets, direct LLM 30.60% on 119, and LLM→B3 31.34% on 119; no matching has 39.92% on all 160. Coverage differs, so these medians alone do not rank the methods. Against the dated Sonnet B3 input with the same rule, the corrected scope changes one peer list and reduces the 160-target median error by 0.0015 percentage points; the paired bootstrap interval includes zero. The separate GPT source-exception sensitivity remains a frozen comparison, not the default.

The source-citing judge scores all 293 reviewed pairs and exactly agrees with Barbara on 230 (78.5%). Keeping its grades 1–2 removes 61 of Barbara's 91 bad pairs while retaining 186 of 202 good pairs, but paired valuation error on 44 reviewed targets changes from 30.84% to 31.02%. The stricter grade-2 rule covers only ten reviewed targets. These are single-reviewer, training-pair diagnostics; neither rule has established a valuation gain. The direct-LLM and hybrid routes are reported separately with their own target coverage, not compared as if missing estimates were successes.

Factor, growth, and regression results are development comparisons, not selected production settings. The 160 public-as-private targets have already informed team decisions. No private-company valuation outcome or independent new final holdout is available here, so private-company accuracy and method superiority remain unestablished.
"""),
        md("""
## 23. Reproduction

The ordered local runner lists every step without executing it: `python v1/scripts/integration_pipeline.py`. Add `--execute` to run the complete study from the pinned inputs, or use `--from-stage` and `--through-stage` to rerun a named interval. A fresh full run requires the licensed WRDS sheets in `outputs-local/v1/integration/sources/` and a locally authenticated Codex CLI; the WRDS workbooks and raw CLI logs are not part of this GitHub result bundle. Opening the notebook does not trigger model calls. Each stage saves its own outputs, and `run_manifest.json` hashes the completed local study.
"""),
        code("""
import sys
sys.path.insert(0, str(ROOT / 'v1/scripts'))
from integration_pipeline import STAGES
display(pd.DataFrame([{'ordered_stages': len(STAGES),
                       'first': STAGES[0][0], 'last': STAGES[-1][0],
                       'runner': 'python v1/scripts/integration_pipeline.py'}]))
"""),
    ]


def main() -> None:
    notebook = nbf.read(NOTEBOOK, as_version=4)
    notebook.cells = [cell for cell in notebook.cells if TAG not in cell.metadata.get("tags", [])]
    notebook.cells.extend(extension())
    notebook.metadata.kernelspec = {"display_name": "Python 3 (project environment)",
                                    "language": "python", "name": "python3"}
    with NOTEBOOK.open("w", encoding="utf-8", newline="\n") as stream:
        nbf.write(notebook, stream)
    print(f"Updated integration notebook: {len(notebook.cells)} cells")


if __name__ == "__main__":
    main()
