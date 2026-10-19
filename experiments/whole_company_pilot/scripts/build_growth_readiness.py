"""Build integration contracts using metadata and SYNTHETIC tests only.

No company outcome table, valuation artifact, network request, or collector is
opened. The teammate collector remains an upstream integration dependency.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from src.modular_validation import growth_readiness as g


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    out=ROOT/'outputs-local/modular-validation/growth-readiness'
    out.mkdir(parents=True,exist_ok=True)
    config_path=ROOT/'config/modular_validation_parameters.json'
    design_path=ROOT/'outputs-local/modular-validation/design_freeze.json'
    design=json.loads(design_path.read_text(encoding='utf-8'))
    config=json.loads(config_path.read_text(encoding='utf-8'))
    team_root=Path(design['team_root'])
    handoff=team_root/'conversations/growth-signals.md'
    # This is the only upstream text read. Nothing is inferred from financial CSVs.
    handoff_text=handoff.read_text(encoding='utf-8')
    assert 'Historical revenue outcomes and cutoff dates have not been added.' in handoff_text
    test_path=ROOT/'tests/test_growth_readiness.py'
    spec=importlib.util.spec_from_file_location('synthetic_growth_contract_tests',test_path)
    test_module=importlib.util.module_from_spec(spec);spec.loader.exec_module(test_module)
    suite=unittest.defaultTestLoader.loadTestsFromModule(test_module)
    log=io.StringIO();result=unittest.TextTestRunner(stream=log,verbosity=2).run(suite)
    stamp=datetime.now(timezone.utc).isoformat()
    artifacts=[config_path,design_path,handoff,ROOT/'src/modular_validation/growth_readiness.py',test_path,Path(__file__)]
    provenance=[{'path':str(p),'sha256':digest(p)} for p in artifacts]
    validation={'generated_at_utc':stamp,'data_class':'SYNTHETIC ONLY; no real company outcomes',
        'tests_run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),
        'passed':result.wasSuccessful(),'test_output':log.getvalue(),'provenance':provenance,
        'not_established':['Collector integration','Real-source truth or extraction recall','Forecast accuracy','Prediction-interval calibration']}
    event=test_module.event();opts=test_module.options()
    train=[test_module.fold_row('SYNTH_A',2016,2017)]
    test=[test_module.fold_row('SYNTH_A',2020,2021)]
    examples={'data_class':'SYNTHETIC ONLY; fictitious issuer.example and artificial values',
      'event':event,'source_evidence_text':test_module.TEXT,
      'event_validation':g.validate_event(event,**opts),
      'revenue_endpoints':[test_module.revenue(2020,100),test_module.revenue(2023,133.1)],
      'realized_label_example':g.revenue_cagr(test_module.revenue(2020,100),test_module.revenue(2023,133.1)),
      'rolling_split':{'train':train,'test':test,'fit_at':'2021-03-01T00:00:00Z'},
      'rolling_validation':g.validate_rolling_origin_split(train,test,fit_at='2021-03-01T00:00:00Z',preprocessing_fit_row_ids=[train[0]['row_id']])}
    missing=[
      {'id':'collector_adapter','status':'not_integrated','input':'Merged teammate growth collector, strict event schema and archived source records','why':'The read handoff documents branch work; this task does not duplicate or validate that absent implementation.'},
      {'id':'historical_availability','status':'not_supplied','input':'Dated historical source versions or retained independent availability proofs for every feature vintage','why':'An old date printed on a live page cannot by itself establish what text was available at a past forecast origin.'},
      {'id':'event_coverage','status':'not_established','input':'Company-cutoff source discovery/fetch success, lookback coverage, extraction abstentions and entity attribution audits','why':'No accepted events can mean missing collection, unknown evidence, or no events; it is not automatically a zero feature.'},
      {'id':'revenue_panel','status':'not_supplied_in_read_handoff','input':'Repeated firm-year or four consecutive firm-quarter actual revenues, timestamps, revisions, currency/unit/accounting/consolidation definitions and approved source lineage','why':'One undated cross-section cannot provide observable three-year labels or historical feature vintages.'},
      {'id':'label_origin_definition','status':'must_be_frozen','input':'Choose fiscal-end-to-fiscal-end annual/TTM CAGR versus exactly three years after prediction origin','why':'An annual base revenue published after fiscal close makes these different horizons. Current helper implements endpoint CAGR, not an exact origin-to-origin return.'},
      {'id':'rolling_evaluation','status':'not_run','input':'Several genuine historical origins with labels observable before each fit and untouched later holdouts','why':'Synthetic leakage tests are software checks, not evidence of predictive accuracy.'},
      {'id':'uncertainty_calibration','status':'not_run','input':'Independent temporal calibration/evaluation residuals and specified interval method','why':'There is no defensible company growth interval from event counts alone.'}
    ]
    interfaces=[
      {'function':'validate_source','input':'source mapping; company_role; regime; allowed_domains','output':'valid/errors/warnings','integration':'Apply to every event and every underlying revenue source before passing their lineage to other helpers. The revenue panel helper checks lineage shape, not information-regime permission.'},
      {'function':'validate_event','input':'source-backed event; cutoff; company role/regime/domain allowlist; source_id-to-evidence_text map','output':'eligible_for_feature_count plus diagnostics; predictive_weight always null','integration':'Map teammate date/quote/event fields without guessing. Hash canonical evidence text separately from raw HTML. Keep unresolved dates, third-party attribution or scope in an abstention queue.'},
      {'function':'validate_event_batch','input':'events plus validate_event arguments','output':'included_event_ids and rejected/duplicate diagnostics','integration':'Assign and audit semantic event_key for company/product/action/date. Keeps earliest UTC-available eligible event; exact ID collisions reject all copies. Counts remain separated by temporary/durable/unknown duration and event type/status.'},
      {'function':'validate_revenue_panel','input':'actual annual/quarterly/TTM observations with explicit revisions and source lineage','output':'schema/period/duplicate/restatement diagnostics','integration':'Accept repeated periods as distinct dated revisions only. Reconcile acquisitions, disposals, currency, unit and accounting changes before comparing endpoint scopes.'},
      {'function':'select_revenue_vintage','input':'validated observations; cutoff','output':'latest available revision per firm-period','integration':'Select independently at each origin/fit; never replace an earlier available value with a later restatement.'},
      {'function':'trailing_twelve_month_revenue','input':'exactly four as-of-selected actual consecutive quarters','output':'derived TTM with lineage and latest availability, or reason unavailable','integration':'No zero filling; no adding overlapping YTD values. If inputs are YTD, a separately audited transformation is required.'},
      {'function':'revenue_cagr','input':'compatible annual/TTM endpoints; horizon_years default3; fiscal tolerance default7 days','output':'realized_cagr and label availability/lineage; is_forecast false; uncertainty_interval null','integration':'Endpoint CAGR=(end/start)^(1/3)-1. Starting revenue must be positive. Fiscal calendar tolerance is explicit; do not describe endpoint horizon as an exact three-year forecast from publication date.'},
      {'function':'validate_rolling_origin_split','input':'train/test metadata; fit time; preprocessing fit row IDs; optional embargo/evaluation time/company holdout','output':'temporal leakage and split diagnostics only','integration':'Training labels must be known at fit; all feature sources and base revenue known at origin. Refit preprocessing and nested tuning within permitted training history. Same firms may recur under temporal forecasting; company holdout is a separate experiment.'}
    ]
    contracts={'version':g.VERSION,'generated_at_utc':stamp,'team_revision':design['team_revision'],
      'purpose':'Future growth integration readiness; not a Monday forecast requirement or a valuation approval.',
      'priority':'CEO/Aziz: efficient defensible private-company comparable selection and valuation with explanations. Growth work remains complementary.',
      'status':'contract_checks_passed' if result.wasSuccessful() else 'contract_checks_failed',
      'forecasts_produced':0,'financial_outcomes_read':False,'target_ev_to_ebitda_opened':False,
      'collector_duplicated':False,'interfaces':interfaces,'missing_inputs':missing,
      'source_policy':{'website_only':'Default controlled event evidence arm. Approved official company/press/careers/regulator/trial sources with attribution.',
          'candidate_filing_enriched':'Candidate-only filings require explicit separate arm; target filings remain prohibited.',
          'mentor_permitted_financial':'Mentor-permitted financial context is separate from website-only tests. Permission does not establish source date, metric comparability, or predictive validity.',
          'url_detection_limit':'Obvious filing URLs are flagged; arbitrary filenames or links cannot be classified perfectly from URL text. Adapter classification and content audit remain required.'},
      'date_policy':'Timestamps require timezone. Never infer historical availability from live-page publication date alone. Date-only publication must be conservatively resolved by adapter with explicit timezone/day-end policy; event_date is coarse announcement/completion date, while timestamped source availability controls feature eligibility.',
      'coverage_policy':'Publish denominators for attempted/available sources, dated records, attributed events and abstentions. Unknown or uncovered periods remain missing. No automatic predictive weights.',
      'read_handoff_claims':{'test_functions_reported':64,'pilot_articles_reported':24,'dated_articles_reported':23,'events_reported':7,'independently_rerun_here':False},
      'frozen_growth_gate':config['blocked_comparisons']['three_year_growth_and_intervals'],
      'provenance':provenance}
    for name,value in [('contract.json',contracts),('synthetic_validation.json',validation),('synthetic_examples.json',examples)]:
        (out/name).write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    lines=['GROWTH DATA READINESS — FUTURE INTEGRATION CONTRACT',f'Generated UTC: {stamp}',
      '',contracts['purpose'],contracts['priority'],
      f"\nImplemented: {len(interfaces)} pure interfaces; {result.testsRun} entirely synthetic tests; failures={len(result.failures)}, errors={len(result.errors)}.",
      'No real financial outcomes, target EV/EBITDA, forecasts or prediction intervals were read or produced.',
      'The collector was not duplicated. The teammate handoff is evidence of reported work, not proof that its code or data was tested here.',
      '\nINTEGRATION ORDER',
      '1. Merge the teammate collector separately; retain raw sources, source text hashes, IDs, publication/capture/availability times and precise event quotes.',
      '2. Run source-policy and evidence gates before cutoff aggregation. Audit entity attribution, semantic event deduplication and whole-company discovery coverage.',
      '3. Preserve event counts by taxonomy, status and temporary/durable/unknown duration. Emit source-coverage denominators and missingness flags; no event-count-to-growth rule is assumed.',
      '4. Supply authorized point-in-time revenue observations. Validate definitions/revisions, select vintages at each cutoff and derive TTM only from four contiguous quarters.',
      '5. Freeze the outcome and origin definition. Build realized endpoint labels only when both revenues are observed. Then construct rolling-origin folds with available labels and earlier nested tuning.',
      '6. Fit a simple benchmark and competing methods only after actual inputs satisfy the gates. Calibrate and test intervals on later observed outcomes before publishing them.',
      '\nMISSING INPUTS']
    for item in missing:lines += [f"- {item['id']} [{item['status']}]: {item['input']}",f"  {item['why']}"]
    lines += ['\nWHAT THE CHECKS DO NOT PROVE',
      'Literal quote support is not independent factual truth or complete business coverage. An allowed domain can quote customers, partners or executive history. A field claiming subsidiary ownership is not an entity review.',
      'A structurally valid archive proof still needs source-content/timestamp verification. SHA256 detects changes to saved bytes/text; it does not authenticate a publisher or reported figure.',
      'Revenue lineage is checked structurally. Every underlying source still needs validate_source under its correct target/candidate information regime. Currency/accounting/consolidation compatibility is not verified by a string alone.',
      'A valid temporal split is not a trained or evaluated model. Synthetic tests demonstrate the contract rejects specified faults; they supply no evidence of growth forecasting or interval coverage.',
      '\nAPI AND EXAMPLES',
      'contract.json lists exact interfaces, missing inputs and provenance hashes. synthetic_examples.json is explicitly fictitious and must never enter the real training corpus. synthetic_validation.json records the executed tests.',
      'Run: .venv\\Scripts\\python.exe -X utf8 scripts\\build_growth_readiness.py',
      '\nRESEARCH BOUNDARY',
      'The existing source-backed hypotheses in sector_facets_and_growth_hypotheses.json are candidates to test, not coefficients or causal forecasts. Clinical-phase evidence supports separating stages, not transplanting trial-success rates into company revenue growth.',
      'Relevant primary sources already reviewed: https://pmc.ncbi.nlm.nih.gov/articles/PMC6409418/ and https://www.fda.gov/patients/drug-development-process/step-3-clinical-research .',
      'Evidence support versus completeness: https://aclanthology.org/2023.emnlp-main.741/ . These papers do not validate this project’s predictions.',
      '\nThis package is future readiness; the immediate investment-committee delivery still requires source-grounded comparable rationale, aligned financial definitions and clear limitations.']
    (out/'READINESS_REPORT.txt').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps({'output':str(out),'tests':result.testsRun,'passed':result.wasSuccessful(),'forecasts':0}))
    return 0 if result.wasSuccessful() else 1


if __name__=='__main__':raise SystemExit(main())
