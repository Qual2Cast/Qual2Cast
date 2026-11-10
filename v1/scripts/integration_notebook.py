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
# Integrated v1 experiment: source to estimate

This continuation runs the shared v1 components in order: source alignment, current business scope, facet construction, candidate retrieval, peer assessment, financial factors, valuation, growth signals, and error analysis. The **533-company public-as-private sample** uses the fixed 373/160 SIC2 split. A larger public catalog is a separate retrieval experiment. Financial multiples enter only after peers are chosen. Scores describe this development sample, not actual private-company accuracy.

All new language-model decisions use **GPT-6.1 Sol through the locally authenticated Codex CLI**. The completed general pass used two simultaneous calls. A four-call sector trial exceeded the C-drive activity limit and was reduced to two. Text embeddings use the local `all-mpnet-base-v2` model on the available GPU; retrieval, fitting, valuation and metrics are deterministic Python computations. Input and model fingerprints govern reuse; every reused embedding is compared numerically with the installed model.

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
## 1. Identity and source alignment

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
## 2. Current business scope

Yiming's dated exit check changes only a facet whose **old text exactly matches** the saved Sonnet fill and whose completed exit has acceptable evidence. It applies 116 values across 42 firms; 44 review rows stay visible. The company retains one ID and all current businesses. The source-audited ten-company benchmark tests activity status and economic grouping. A separate blind GPT-6.1 Sol scope check uses the same activity names and only cited saved website lines, with the reference labels withheld. Only two of the ten cases had a benchmark reference page among those saved lines, so this check also measures evidence availability. The 293-pair score and 160-target multiple test measure downstream effects. Sources: [Yiming's check](https://drive.google.com/file/d/1-yKpdRVMDSjGCnLUQh0fuqvqJeT-Kmw4/view), [business-scope rule](../GOLDEN_SET_ROUND2.md), [implementation](../scripts/integration_sources.py).
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
"""),
        md("""
## 3. Facet construction and model comparison

The original whole-company facets are the common base. Fiona adds sector and sub-sector descriptions; Barbara adds SIC2-specific fields. Missing or inapplicable fields do not receive a match score. The saved Haiku/Sonnet fills and 48 B3 configurations are compared on Barbara's 293 graded pairs and the same 160 development valuation targets. Pair ranking, good-peer retention and multiple error can disagree; no variant is chosen from the 160 targets as a final test. GPT-6.1 Sol fills use the same general, sector and SIC2 schemas in separate local runs; fill count alone is not factual accuracy. Sources: [facet definitions](../scripts/facets.py), [Fiona's sector model](../scripts/sector_facets.py), [Barbara's SIC2 dictionary](../scripts/reference/sic2_industry_facet_dictionary.md), [B3 ablation](../scripts/b3_facet_add_drop.py).
"""),
        code("""
facet_runs = [('Haiku general', 'facets/tables/facets.csv'),
              ('Sonnet general', 'facets_sonnet/tables/facets.csv'),
              ('Sonnet current-scope general', 'integration/sources/facets_sonnet_corrected.csv'),
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
## 4. Candidate construction

B0–B3, M2, TF-IDF, SIC pool restrictions, whole-profile MPNet/TF-IDF/LSA/rank fusion, Ward's tree and UMAP/HDBSCAN groups are rerun separately on corrected Sonnet and GPT whole-company fields. All rank the same 373 eligible training peers and use the same 293 reviewer pairs and 160 development valuation targets. The unsupervised tree and density partitions see all 533 business descriptions but no labels or multiples. B3 blends facet-level embedding and TF-IDF similarity; its standard list retains mutual top-ten peers with a three-peer top-up. The tree and density rules gate whole-profile cosine ranks; cluster outliers use the team's mutual-neighbor fallback. Strict SIC restrictions may return no peer. The earlier activity/transport caches used a different candidate pool; they are not imported into this comparison. A **separate candidate-universe experiment** searches Barbara's 38,788 eligible groups with website excerpts using TF-IDF or MPNet; Barbara's own published top-ten lists use 30,416 descriptions and are a different pool. Published text-based industry and M&A peer-selection studies motivate testing business text beside industry codes, but do not establish private-company performance here. Sources: [B3 and M2 code](../scripts/facet_weighting.py), [team tree and cluster selectors](../../pre-v0/matching/peer_selectors.py), [retrieval comparison](../scripts/integration_candidate_methods.py), [Sentence-BERT](https://aclanthology.org/D19-1410/), [LSA](https://asistdl.onlinelibrary.wiley.com/doi/10.1002/%28SICI%291097-4571%28199009%2941%3A6%3C391%3A%3AAID-ASI1%3E3.0.CO%3B2-9), [RRF](https://cormack.uwaterloo.ca/cormacksigir09-rrf.pdf), [Ward](https://iv.cns.iu.edu/sw/data/ward.pdf), [UMAP](https://arxiv.org/abs/1802.03426), [HDBSCAN](https://doi.org/10.1007/978-3-642-37456-2_14), [Hoberg and Phillips](https://www.journals.uchicago.edu/doi/full/10.1086/688176), [M&A peer selection](https://www.sciencedirect.com/science/article/pii/S0304405X21003834), [Barbara's published results](https://barbara069.github.io/private-company-comparables-research/).
The same 20 fixed-pool retrieval methods are also evaluated with the source-cited GPT facets under the same twelve-field schema.
"""),
        code("""
base_candidates = pd.read_csv(I / 'candidate_methods/reviewed_metrics.csv')
base_valuation = pd.read_csv(I / 'candidate_methods/valuation_summary.csv')
display(base_candidates.merge(base_valuation[['comp rule', 'targets', 'median abs % error']],
                              left_on='method', right_on='comp rule', validate='one_to_one',
                              suffixes=('_reviewed', ''))[
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
## 5. Peer selection and grading

The baseline notebook above retains cosine, direct LLM, cosine→LLM and LLM→cosine as distinct selection routes. The source-citing judge applies the team's unchanged company-level **0–2 rubric**: 2 = products and customers fit across material current businesses; 1 = meaningful overlap with material unmatched scope; 0 = no meaningful company-level overlap. Barbara's 293 rows are one reviewer, not consensus labels. Her 292 scored overlaps with the saved agent form a diagnostic confusion table; the original 36-pair majority set remains separate. Sources: [rubric](../GOLDEN_SET_ROUND2.md), [judge implementation](../scripts/agent_loop.py), [review data](https://docs.google.com/spreadsheets/d/1LPWjEdTV7-T5BY5eCTqop3JITM6UTSGt/edit).
"""),
        code("""
review = json.loads((I / 'review/summary.json').read_text(encoding='utf-8'))
confusion = pd.read_csv(I / 'review/confusion.csv', index_col=0)
display(pd.DataFrame([review]))
display(confusion)
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
The new GPT-6.1 Sol source-citing judge is run **without reviewer scores in its prompts** on all 293 Barbara pairs. Exact and peer/non-peer agreement are reported alongside coverage and the saved agent on the same overlapping pairs. Its two existing selection policies, keeping grades 1–2 or only grade 2, are tested on the **same 293 reviewed pairs and 45 training targets**; those partial lists are not a full holdout selection test. A single reviewer is a diagnostic reference, not a consensus gold standard. Website and search evidence may postdate the multiple snapshot, so this is a current-business diagnostic rather than an ex-ante backtest. The four selection routes then run on the fixed 160 public-as-private targets. All six valuation rows per facet condition use the same positive public-peer multiples after peer selection. A Sonnet-content control uses the same GPT model and GPT-general candidate list, so its difference reflects prompt content rather than a new model. The all-additions condition changes both the shortlist and prompt content. Sources: [ReAct](https://arxiv.org/abs/2210.03629), [LLM-as-a-judge evaluation](https://arxiv.org/abs/2306.05685), [agent loop](../scripts/agent_loop.py), [judge selection](../scripts/integration_judge_selection.py), [holdout routes](../scripts/holdout_batched_routes.py), [valuation code](../scripts/integration_holdout_eval.py).
"""),
        code("""
judge_eval = json.loads((I / 'judge_gpt61sol/eval_293/summary.json').read_text(encoding='utf-8'))
display(pd.DataFrame([judge_eval]))
display(pd.read_csv(I / 'judge_gpt61sol/eval_293/confusion.csv', index_col=0))
display(pd.read_csv(I / 'judge_gpt61sol/eval_293/selection_metrics.csv'))
display(pd.read_csv(I / 'judge_gpt61sol/eval_293/selection_valuation.csv'))
display(pd.read_csv(I / 'judge_gpt61sol/eval_293/selection_paired.csv'))
route_dirs = {'Sonnet content, GPT model': 'control_sonnet',
              'GPT general': 'gpt_general', 'GPT general + Fiona + Barbara': 'gpt_all'}
route_results = []
for label, folder in route_dirs.items():
    table = pd.read_csv(I / 'holdout_routes' / folder / 'evaluation/summary.csv')
    route_results.append(table.assign(facet_condition=label))
route_results = pd.concat(route_results, ignore_index=True)
display(route_results[['facet_condition', 'comp rule', 'targets',
                       'median abs % error', '% within 25%']])
paired = pd.concat([
    pd.read_csv(I / 'holdout_routes' / folder / 'evaluation/paired_common.csv')
      .assign(facet_condition=label)
    for label, folder in route_dirs.items()], ignore_index=True)
display(paired[['facet_condition', 'method', 'common_targets',
                'median_paired_gain_vs_b3', 'gain_ci_low', 'gain_ci_high']])
display(pd.read_csv(I / 'holdout_routes/condition_comparison.csv')[[
    'old_condition', 'new_condition', 'method', 'common_targets',
    'median_gain_percentage_points', 'gain_ci_low', 'gain_ci_high']])
fig, ax = plt.subplots(figsize=(8, 4))
pivot = route_results.pivot(index='comp rule', columns='facet_condition',
                            values='median abs % error')
pivot.plot.barh(ax=ax); ax.set(xlabel='Median absolute multiple error (%)')
plt.tight_layout(); plt.show()
"""),
        md("""
## 6. Private-supplied factors and valuation

Revenue, EBITDA margin and debt/revenue are **optional target inputs** after business matching; the eight subsets include business-only. Within a fixed B3 top-ten shortlist, each subset reranks peers by empirical percentile distance, then selects 3, 5 or 10 and applies six positive-multiple aggregators. Peer count is tested rather than fixed: a published multiples study found ten closely selected peers competitive with a whole-industry set in its sample, with a smaller loss at five. The second estimator family fits FF49 pooled OLS, ridge and elastic-net regressions on 373 training firms, with and without qualitative facet categories; hyperparameters use training folds only. All rows below use the same 160 public-as-private development targets. Overall median error and paired wins can rank the factor sets differently, so both are reported. Period, currency, lease and EBITDA definitions require case-level confirmation before a dollar valuation. Sources: [SARD study](https://research.cbs.dk/da/publications/stick-to-the-fundamentals-and-discover-your-peers/), [peer-count study](https://doi.org/10.1111/eufm.12405), [Baker and Ruback](https://www.hbs.edu/ris/Publication%20Files/EstimatingIndustry_b4e64d71-c8fd-4a5e-b31a-623d3a7d02bc.pdf), [Barbara's method memo](https://drive.google.com/file/d/1B32xAUsOAmDMW1U0IoGLYeonRm4Czkbu/view), [factor code](../scripts/integration_factors.py).
"""),
        code("""
factor = pd.read_csv(I / 'factors/method_results.csv')
focus = factor[(factor['peer_budget'] == 5) & (factor['aggregation'] == 'median')]
display(focus[['factor_set', 'coverage', 'median_ape', 'mean_paired_delta',
               'targets_better', 'targets_worse', 'targets_equal']]
        .sort_values('median_ape'))
regression = pd.read_csv(I / 'regression/summary.csv')
display(regression.sort_values('median_ape'))
fig, ax = plt.subplots(figsize=(8, 3.8))
ordered = regression.sort_values('median_ape')
ax.barh(ordered['method'], ordered['median_ape'], color='#557e75')
ax.invert_yaxis(); ax.set(xlabel='Median absolute percentage error (%)', title='Same 160 targets')
plt.tight_layout(); plt.show()
"""),
        md("""
## 7. Growth events

The existing dated-page extractor distinguishes contracts, launches, hiring, layoffs, expansion and credit events. Rules, LLM and their agreement are distinct extraction methods; an event label is not a revenue-growth outcome. The ten-company `holdout_c` set tests event extraction from saved pages, without a verified page-capture cutoff. Its precision and recall are shown by event type. No cutoff-valid annual revenue history is present in this local snapshot, so an association with later revenue growth cannot be estimated here. Source: [growth component](../../pre-v0/growth_signals/README.md), [saved labels](../../pre-v0/growth_signals/eval/2026-10-19/README.md).
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
        md("""
## 8. Company report and error diagnosis

The input accepts an exact name, ticker, ID or website in the 533-company sample. It returns a ranked ten-peer list, similarity, public-peer multiples and an EV/EBITDA estimate; dollar EV is calculated only if the user supplies positive target EBITDA. The report lists its source files. Kethan's saved-result analysis separately locates historical facet-label mismatch, model disagreement, candidate loss and judge disagreement. These are diagnosis queues, not independent proof of causal error. Sources: [company report code](../scripts/integration_company_report.py), [error-analysis code](../scripts/error_analysis.py).
"""),
        code("""
import sys
sys.path.insert(0, str(ROOT / 'v1/scripts'))
from integration_company_report import report_company

example = report_company('aarcorp.com', method='gpt_general')
display(pd.DataFrame(example['ranked_peers']))
display(pd.DataFrame([{'company': example['company'],
                       'estimated_EV_EBITDA': example['multiple_estimate'],
                       'target_EBITDA_provided': example['target_ebitda_supplied'],
                       'dollar_EV': example['enterprise_value_estimate']}]))
diagnosis = json.loads((I / 'error_diagnosis/summary.json').read_text(encoding='utf-8'))
display(pd.DataFrame([{'facet_condition': key, **value} for key, value in diagnosis.items()
                      if isinstance(value, dict)]))
errors = pd.read_csv(I / 'error_diagnosis/holdout_target_comparison.csv')
display(errors.sort_values('B3 selected', ascending=False)[
    ['ticker', 'company', 'facet_condition', 'B3 selected', 'B3 then LLM',
     'Direct LLM', 'LLM then B3']].head(12))
display(pd.read_csv(I / 'error_diagnosis/stage_diagnostics.csv'))
"""),
        md("""
## 9. Executed configuration matrix

The full local CSV lists each configuration actually run, with its facet source, retrieval, selection, grading, factor set, aggregation, coverage and development error. Rows from different candidate pools or label cohorts are not directly pooled.
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
## 10. Interpretation

The source-citing GPT facets attach an official-site line to all 5,188 filled fields. This improves traceability but does not improve the tested matcher: its reviewed-pair accuracy is 0.835 versus 0.868 for memory-first GPT, and its B3 median absolute percentage error is 33.69% on 159 targets versus 33.41% for memory-first GPT on those same targets. The paired uncertainty interval includes zero. None of the 20 tested retrieval rules, sector additions, or reviewer-calibrated threshold has a clear paired valuation advantage. The larger catalog offers more possible peers, but its tested first-pass retrievals miss many reviewed good peers.

The source-citing judge scores all 293 reviewed pairs and exactly agrees with Barbara on 230 (78.5%). Keeping its grades 1–2 removes 61 of Barbara's 91 bad pairs while retaining 186 of 202 good pairs, but paired valuation error on 44 reviewed targets changes from 30.84% to 31.02%. The stricter grade-2 rule covers only ten reviewed targets. These are single-reviewer, training-pair diagnostics; neither rule has established a valuation gain. The direct-LLM and hybrid routes are reported separately with their own target coverage, not compared as if missing estimates were successes.

Factor, growth, and regression results are development comparisons, not selected production settings. The 160 public-as-private targets have already informed team decisions. No private-company valuation outcome or independent new final holdout is available here, so private-company accuracy and method superiority remain unestablished.
"""),
        md("""
## 11. Reproduction

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
