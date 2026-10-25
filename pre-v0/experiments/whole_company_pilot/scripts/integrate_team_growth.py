"""Integrate pinned team growth extraction with source/time contracts.

Commands: capture (bounded public HTML), analyze (offline), tests (synthetic).
Never opens financial outcomes or manufactures a historical revenue panel.
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.dont_write_bytecode=True
from src.modular_validation import growth_readiness as gates

DEFAULT_TEAM=Path('C:/Users/13156/ChatGPT-Local-Deliveries/Rational-AI-2026-10-18/team-source/41aa0078acde16afbc66a1ddea238c29a742b1fc')
OUT=ROOT/'outputs-local/modular-validation/growth-integration'
SITES=[
 {'case_id':'PCTY_blog','ticker':'PCTY','company_id':'IQ254957567','company_name':'Paylocity Holding Corporation',
  'url':'https://www.paylocity.com/resources/learn/blogs/introducing-paylocity-ignite-ai/',
  'reason':'Teammate pilot named Ignite AI; durable product-launch diagnostic.'},
 {'case_id':'PCTY_press','ticker':'PCTY','company_id':'IQ254957567','company_name':'Paylocity Holding Corporation',
  'url':'https://www.paylocity.com/company/about-us/newsroom/press-releases/paylocity-launches-ignite-ai-redefining-industry-ai-leadership/',
  'reason':'Official press article about the same named launch; cross-publication deduplication diagnostic.'},
 {'case_id':'PRGS_rag','ticker':'PRGS','company_id':'IQ33351','company_name':'Progress Software Corporation',
  'url':'https://investors.progress.com/news-releases/news-release-details/progress-software-connects-enterprise-knowledge-across-business',
  'reason':'Official October product-release article; durable capability diagnostic, not financial-results collection.'},
 {'case_id':'WING_card','ticker':'WING','company_id':'IQ260824267','company_name':'Wingstop Inc.',
  'url':'https://ir.wingstop.com/wingstop-announces-the-game-day-punch-card/',
  'reason':'Official dated limited-duration rewards offer; temporary launch diagnostic.'},
 {'case_id':'WING_club','ticker':'WING','company_id':'IQ260824267','company_name':'Wingstop Inc.',
  'url':'https://ir.wingstop.com/wingstop-turns-loyalty-into-cultural-currency-with-the-launch-of-club-wingstop/',
  'reason':'Official loyalty-program announcement with promotional context; event-scope/duration diagnostic.'}
]
REQUIRED=['growth_signals/schema.py','growth_signals/collect_events.py','growth_signals/extract_events.py',
          'growth_signals/build_features.py','growth_signals/build_outcomes.py',
          'website_scrape/fetch_and_clean.py','src/project_data.py','SOURCE_MANIFEST.json']

def now():return datetime.now(timezone.utc).isoformat()
def sha(b):return hashlib.sha256(b).hexdigest()
def write(p,value):Path(p).write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def module(path,name):
    spec=importlib.util.spec_from_file_location(name,path);mod=importlib.util.module_from_spec(spec)
    sys.modules[name]=mod;spec.loader.exec_module(mod);return mod

def load_team(root):
    for p in [root/'growth_signals',root/'website_scrape',root/'src']:
        sys.path.insert(0,str(p))
    schema=module(root/'growth_signals/schema.py','schema')
    discover=module(root/'growth_signals/collect_events.py','growth_discovery_control')
    extract=module(root/'growth_signals/extract_events.py','growth_extraction_control')
    features=module(root/'growth_signals/build_features.py','growth_features_control')
    cleaner=module(root/'website_scrape/fetch_and_clean.py','growth_raw_text_control')
    return schema,discover,extract,features,cleaner

def manifest(root):
    files=[]
    for rel in REQUIRED:
        p=root/rel
        files.append({'relative_path':rel,'absolute_path':str(p),'sha256':sha(p.read_bytes())})
    test_dependencies=sorted(set(root.joinpath('growth_signals').glob('*.py'))|set(root.joinpath('growth_signals/tests').glob('*.py'))|set(root.joinpath('website_scrape').glob('*.py')))
    return {'team_root':str(root),'team_revision':'41aa0078acde16afbc66a1ddea238c29a742b1fc',
      'retrieval':'Authenticated GitHub visible source; shared dependencies copied from unchanged ancestry. See team SOURCE_MANIFEST.json.',
      'required_files':files,'import_layout':'Keep growth_signals/, website_scrape/ and src/ under one separate team root. Script prepends these directories, imports schema under its team module name, and imports extraction/features under distinct control names.',
      'test_source_files':[{'relative_path':str(p.relative_to(root)).replace('\\','/'),'sha256':sha(p.read_bytes())} for p in test_dependencies],
      'local_dependencies':['scripts/cleaning_diagnostic.py (capture only)','src/modular_validation/growth_readiness.py','outputs-local/modular-validation/growth-integration/captures (offline replay)'],
      'matching_snapshot_unchanged':'da427dbf6b34a41d3b172ced6a2959e2c9335b0a',
      'source_manifest_sha256':sha((root/'SOURCE_MANIFEST.json').read_bytes()),
      'local_adapter_sha256':sha(Path(__file__).read_bytes()),
      'contract_sha256':sha((ROOT/'src/modular_validation/growth_readiness.py').read_bytes())}

def capture(root):
    OUT.mkdir(parents=True,exist_ok=True)
    if (OUT/'capture_manifest.json').exists():raise FileExistsError('Capture already exists; analyze saved sources instead of implicit refetch.')
    _,discover,extract,_,cleaner=load_team(root)
    # Reuse the earlier bounded ordinary HTTP utility; no browser or stealth path.
    http=module(ROOT/'scripts/cleaning_diagnostic.py','growth_bounded_http')
    freeze={'frozen_at_utc':now(),'cases':SITES,'selection':'Five purposively selected official articles, no replacements; diagnostic examples, not random evaluation or corpus recall.',
      'source_arm':'New current HTML captures; not restoration of the original teammate pilot or a historical training set.',
      'capture_policy':'One robots attempt per origin, one HTML attempt per allowed case; same-origin redirects only; 5MB HTML cap, no authentication/captcha/stealth fallback.',
      'retrospective_cutoff':'2026-10-01T23:59:59Z','confidence_policy':'Team constant .80 is a rule score, not a calibrated probability.',
      'restrictions':'No target filings, financial-result pages, valuation labels or source replacement. Official IR product news is an explicitly identified event-source arm.',
      'source_manifest':manifest(root)}
    write(OUT/'config_freeze.json',freeze)
    cases=[];robots={}
    for site in SITES:
        folder=OUT/'captures'/site['case_id'];folder.mkdir(parents=True,exist_ok=True)
        parts=urlsplit(site['url']);origin=f'{parts.scheme}://{parts.netloc}'
        if origin not in robots:
            rf=OUT/'captures'/('robots_'+parts.netloc+'.txt')
            log,text=http.http_get(origin+'/robots.txt',rf,524288)
            status=log.get('status_code');allowed=None
            if status==404 and not log.get('error'):allowed='missing_404'
            elif status and 200<=status<300 and text and '<html' not in text[:500].lower():
                allowed=RobotFileParser();allowed.parse(text.splitlines())
            robots[origin]=(log,allowed)
        robot_log,robot=robots[origin]
        case={**site,'robots':robot_log}
        permits=robot=='missing_404' or (isinstance(robot,RobotFileParser) and robot.can_fetch(http.UA,site['url']))
        if not permits:case['status']='robots_disallowed_or_unavailable'
        else:
            log,html=http.http_get(site['url'],folder/'source.html',5242880)
            case['capture']=log
            if not html or log.get('error') or not 200<=log.get('status_code',0)<300:case['status']='http_failed'
            elif urlsplit(log['final_url']).hostname!=parts.hostname:case['status']='cross_host_redirect_excluded'
            else:
                raw=cleaner.extract_page(html)
                text='\n'.join([raw.get('raw_title',''),raw.get('raw_meta',''),*raw.get('raw_blocks',[])])
                lower=html.lower()
                challenge=any(x in lower for x in ['cf-chl-','__cf_chl_','challenge-platform','verify you are human','incapsula incident','_incapsula_resource']) and len(text)<2000
                if challenge:case['status']='challenge_excluded'
                elif len(text.strip())<100:case['status']='empty_or_thin_excluded'
                else:
                    published,precision=discover.publication_date_from_html(html)
                    page={'page_id':site['case_id'],'category':'article','source_url':log['final_url'],
                      'fetched_at':log['completed_at_utc'],'published_date':published,'published_date_precision':precision,
                      'raw_title':raw.get('raw_title',''),'raw_meta':raw.get('raw_meta',''),'raw_blocks':raw.get('raw_blocks',[]),
                      'raw_html_file':str(folder/'source.html'),'raw_html_sha256':log['body_sha256'],
                      'discovery':'Fixed official article URL from primary web search before capture'}
                    record={'IQ_COMPANY_ID':site['company_id'],'company_name':site['company_name'],'pages':[page]}
                    events,audit=extract.extract_record(record)
                    write(folder/'page_record.json',record);write(folder/'original_events.json',[e.to_dict() for e in events])
                    write(folder/'extraction_audit.json',audit)
                    case.update(status='usable',published_date=published,event_count=len(events),page_record=str(folder/'page_record.json'))
        cases.append(case);write(folder/'capture.json',case)
        print(site['case_id'],case['status'],case.get('event_count'),flush=True)
    write(OUT/'capture_manifest.json',{'captured_at_utc':now(),'cases':cases,'required_source_manifest':manifest(root)})

def event_id(e):
    return 'event:'+sha(json.dumps(e.to_dict(),sort_keys=True).encode())[:20]

def analyze(root):
    OUT.mkdir(parents=True,exist_ok=True)
    schema,discover,extract,features,_=load_team(root)
    capture_log=read(OUT/'capture_manifest.json');freeze=read(OUT/'config_freeze.json')
    reviews=read(OUT/'agent_event_reviews.json') if (OUT/'agent_event_reviews.json').exists() else {}
    events=[];mapped=[];text_map={};pages={};extraction_audits=[]
    for case in capture_log['cases']:
        if case['status']!='usable':continue
        record=read(OUT/'captures'/case['case_id']/'page_record.json');these,audit=extract.extract_record(record);extraction_audits.append(audit)
        page=record['pages'][0];text='\n'.join([page['raw_title'],page['raw_meta'],*page['raw_blocks']])
        source_id='source:'+case['case_id'];text_map[source_id]=text;pages[source_id]=page
        for e in these:
            eid=event_id(e);review=reviews.get(eid,{})
            mapped_event={'event_id':eid,'event_key':review.get('event_key',eid),'company_id':e.IQ_COMPANY_ID,
              'subject_company_id':e.IQ_COMPANY_ID,'subject_role':review.get('subject_role','unknown'),
              'event_type':e.event_type,'event_status':review.get('event_status','announced'),
              'event_date':e.event_date,'signal_duration':review.get('signal_duration',e.signal_duration),
              'evidence_quote':e.source_text,
              'source':{'source_id':source_id,'company_id':e.IQ_COMPANY_ID,'source_url':e.source_url,
                'source_type':'company_press','content_sha256':page['raw_html_sha256'],
                'evidence_text_sha256':sha(text.encode()),'captured_at':e.retrieved_at,
                'first_available_at':e.retrieved_at,'availability_basis':'first_observed_capture'},
              'original_event':e.to_dict(),'case_id':case['case_id'],
              'agent_review':review or {'status':'not_reviewed'},
              'review_origin':'provisional AGENT; not human labels',
              'availability_note':'Exact current capture only; old printed date does not prove archived availability.',
              'publication_date_precision':e.event_date_precision}
            # Date-only publication is preserved separately, not converted into an invented timestamp.
            mapped.append(mapped_event);events.append(e)
    write(OUT/'original_events.json',[e.to_dict() for e in events]);write(OUT/'mapped_events.json',mapped)
    write(OUT/'extraction_audits.json',extraction_audits)
    snapshots=[];strict_diagnostics=[];comparison=[]
    current_cutoff=capture_log['captured_at_utc']
    for arm,cutoff in [('retrospective_without_archive_proof',freeze['retrospective_cutoff']),('current_capture',current_cutoff)]:
        cutoff_day=datetime.fromisoformat(cutoff.replace('Z','+00:00')).date()
        control=features.build_company_features(events,cutoff_day)
        checked=gates.validate_event_batch(mapped,cutoff=cutoff,company_role='target',regime='website_only',
          allowed_domains=['paylocity.com','progress.com','wingstop.com'],evidence_texts=text_map)
        included=set(checked['included_event_ids']);adjusted=[]
        for m in mapped:
            if m['event_id'] in included:
                d=dict(m['original_event']);d['signal_duration']=m['signal_duration'];adjusted.append(schema.Event.from_dict(d))
        strict=features.build_company_features(adjusted,cutoff_day)
        strict_by={r['IQ_COMPANY_ID']:r for r in strict}
        control_by={r['IQ_COMPANY_ID']:r for r in control}
        for cid in sorted({s['company_id'] for s in SITES}):
            company_cases=[c for c in capture_log['cases'] if c['company_id']==cid]
            available_sources=sum(c['status']=='usable' and datetime.fromisoformat(c['capture']['completed_at_utc'])<=datetime.fromisoformat(cutoff.replace('Z','+00:00')) for c in company_cases)
            comparison.append({'arm':arm,'cutoff':cutoff,'company_id':cid,'ticker':company_cases[0]['ticker'],
              'attempted_articles':len(company_cases),'usable_current_articles':sum(c['status']=='usable' for c in company_cases),
              'proven_available_articles_at_cutoff':available_sources,
              'coverage_status':'purposive_partial_coverage' if available_sources else 'no_proven_available_sources',
              'team_feature_row_emitted':cid in control_by,
              'team_rule_events_365d':control_by.get(cid,{}).get('evidence_365d_count'),
              'strict_supported_events_365d':strict_by.get(cid,{}).get('evidence_365d_count',0) if available_sources else None,
              'strict_temporary_launches_365d':strict_by.get(cid,{}).get('product_launch_temporary_365d_count',0) if available_sources else None,
              'strict_durable_launches_365d':strict_by.get(cid,{}).get('product_launch_durable_365d_count',0) if available_sources else None,
              'strict_unknown_duration_launches_365d':strict_by.get(cid,{}).get('product_launch_unknown_duration_365d_count',0) if available_sources else None,
              'zero_definition':'No eligible extracted event in these selected available pages, never evidence of no company growth.'})
        snapshots.append({'arm':arm,'cutoff':cutoff,'team_features':control,'strict_features':strict})
        strict_diagnostics.append({'arm':arm,'cutoff':cutoff,**checked})
    write(OUT/'feature_outputs.json',snapshots);write(OUT/'event_validation.json',strict_diagnostics)
    write(OUT/'feature_comparison.json',comparison)
    validation={'run_at_utc':now(),'raw_capture_checks':[], 'literal_agent_review_checks':[],
      'original_extraction_reproduced':True,'human_gold_labels':False}
    for case in capture_log['cases']:
        cap=case.get('capture',{})
        if cap.get('saved_path'):
            validation['raw_capture_checks'].append({'case_id':case['case_id'],
              'sha256_matches':sha((OUT/'captures'/case['case_id']/'source.html').read_bytes())==cap['body_sha256']})
        if case['status']=='usable':
            expected=read(OUT/'captures'/case['case_id']/'original_events.json')
            actual=[e.to_dict() for e in events if e.source_url==case['capture']['final_url']]
            if expected!=actual:validation['original_extraction_reproduced']=False
    for eid,r in reviews.items():
        text=text_map.get(r.get('source_id'),'')
        validation['literal_agent_review_checks'].append({'event_id':eid,
          'subject_evidence_present':r.get('subject_evidence','') in text,
          'duration_evidence_present':r.get('duration_evidence','') in text})
    validation['passed']=validation['original_extraction_reproduced'] and all(r['sha256_matches'] for r in validation['raw_capture_checks']) and all(r['subject_evidence_present'] and r['duration_evidence_present'] for r in validation['literal_agent_review_checks'])
    write(OUT/'integration_validation.json',validation)
    import csv
    with (OUT/'feature_comparison.csv').open('w',encoding='utf-8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(comparison[0]));writer.writeheader();writer.writerows(comparison)
    status={'generated_at_utc':now(),'team_revision':root.name,'source_manifest':manifest(root),
      'actual_integration':'Team schema, publication-date parser, raw text extractor, event extractor and feature aggregation executed on newly captured official article HTML.',
      'selected_articles':len(SITES),'usable_articles':sum(c['status']=='usable' for c in capture_log['cases']),
      'original_rule_event_records':len(events),'agent_reviewed_event_records':sum(bool(m['agent_review'].get('reviewed')) for m in mapped),
      'current_strict_event_records':len(strict_diagnostics[-1]['included_event_ids']),
      'historical_feature_reconstruction_status':'Unavailable without historical source proof; current retrieval timestamps cannot be backdated.',
      'forecast_status':'abstained_missing_historical_revenue_panel_and_repeated_feature_vintages',
      'real_revenue_outcome_rows_read':0,'forecasts_produced':0,'growth_model_fitted':False,'interval_calibration_run':False,
      'source_truth':'Provisional source-supported AGENT review, not independent human labels or full coverage.',
      'team_tests':read(OUT/'team_test_results.json') if (OUT/'team_test_results.json').exists() else None,
      'integration_validation_passed':validation['passed'],
      'source_scope_audit':read(OUT/'source_scope_audit.json') if (OUT/'source_scope_audit.json').exists() else None,
      'findings':[
        'Original build_company_features checks event_date only; strict adapter also gates first evidence availability and preserves unavailable coverage as null.',
        'Original extractor emits .80 for every rule match; no calibration or causal direction is established.',
        'Original signal_duration checks temporary markers across the whole page before evidence-specific product scope; review is needed for articles mixing durable programs and temporary promotions.',
        'Original semantic event deduplication is within identical sentences, not across different descriptions/publications. The adapter uses explicit AGENT-audited event keys.',
        'Original build_outcomes computes future endpoint ratios but does not establish financial date/vintage/unit/definition compatibility; use revenue contracts before its downstream outputs.',
        'News examples were selected purposively to test integration; they cannot estimate extraction precision, recall or forecasting performance.'
      ],
      'next_inputs':['Historical dated event versions/availability proofs','Company-period collection coverage','Revenue panel with units/scope/revisions/availability and approved sources','Frozen horizon/origin and rolling temporal folds','Independent human event audit and later outcome evaluation'],
      'primary_method_references':[
        {'url':'https://aclanthology.org/2023.emnlp-main.741/','scope':'Atomic evidence support motivates quote/source checks; not completeness or real truth.'},
        {'url':'https://otexts.com/fpp3/toolbox.html#time-series-cross-validation','scope':'Rolling-origin evaluation uses observations before each test origin; no validation from synthetic or unobserved labels.'},
        {'url':'https://pmc.ncbi.nlm.nih.gov/articles/PMC6409418/','scope':'Stage-specific clinical heterogeneity is a hypothesis-design example, not a transferable company-growth coefficient.'}]}
    write(OUT/'integration_status.json',status);write(OUT/'required_source_manifest.json',manifest(root))
    report=['TEAM GROWTH INTEGRATION — EXECUTED LOCAL DIAGNOSTIC',f"Generated UTC: {status['generated_at_utc']}",
      f"Team revision: {root.name}",status['actual_integration'],
      f"Selected articles: {len(SITES)}; usable: {status['usable_articles']}; original rule records: {len(events)}; current strict supported/deduplicated records: {status['current_strict_event_records']}.",
      '', 'This replaces only the prior statement that teammate integration had not been executed. It does not create a historical training panel or validate growth forecasts.',
      '',*status['findings'],'','CAPTURE RESULTS']
    report += [f"{c['case_id']}: {c['status']} — {c['url']}" for c in capture_log['cases']]
    report += ['','SOURCE AND TIME RULES','Original HTML bytes, robots decisions, final URLs, capture timestamps and hashes are retained. Only current capture establishes availability in this run. No company filing or financial-results page was requested.',
      'Date-only publication fields remain date-only. A dated article is a source claim about an event; it is not proof that the present text existed at that historical date.',
      'No event extracted is a conditional observation about selected sources. Null means no proven available evidence; neither is a zero-growth prediction.',
      '', 'FORECAST GATE',status['forecast_status'],'No real revenue outcomes, target EV/EBITDA, fitted growth model, fabricated forecast or prediction interval.',
      'The existing pure revenue/rolling-origin contracts are the model integration boundary until actual historical inputs are supplied.',
      '', 'REPRODUCTION','Use --team-root to point at the separately packaged 41aa007 source. analyze is offline; capture is explicit and refuses implicit overwrite; tests run synthetic teammate unit tests only.']
    (OUT/'INTEGRATION_REPORT.txt').write_text('\n'.join(report)+'\n',encoding='utf-8')
    print(json.dumps({k:status[k] for k in ['usable_articles','original_rule_event_records','current_strict_event_records','forecast_status']}))

def tests(root):
    OUT.mkdir(parents=True,exist_ok=True)
    if (OUT/'team_test_results.json').exists():
        write(OUT/('team_test_results_prior_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')+'.json'),read(OUT/'team_test_results.json'))
    temp=OUT/'test-work'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')
    if not temp.resolve().is_relative_to(OUT.resolve()) or temp.exists():raise ValueError('Temporary test path must be new and inside integration outputs')
    temp.parent.mkdir(parents=True,exist_ok=True)
    cmd=[sys.executable,'-B','-X','utf8','-m','pytest',str(root/'growth_signals/tests'),'-q','-p','no:cacheprovider','--basetemp',str(temp)]
    result=subprocess.run(cmd,capture_output=True,text=True,encoding='utf-8',cwd=ROOT)
    record={'run_at_utc':now(),'command':cmd,'returncode':result.returncode,'stdout':result.stdout,'stderr':result.stderr,
      'data_class':'Team tests use synthetic/in-memory fixtures and monkeypatches; no real financial outcome table read.',
      'is_predictive_evaluation':False,'test_sources':[{'path':str(p.relative_to(root)),'sha256':sha(p.read_bytes())} for p in sorted((root/'growth_signals/tests').glob('*.py'))]}
    write(OUT/'team_test_results.json',record);print('\n'.join(result.stdout.splitlines()[-3:]));print(result.stderr)
    return result.returncode

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('action',choices=['capture','analyze','tests'])
    parser.add_argument('--team-root',type=Path,default=DEFAULT_TEAM);args=parser.parse_args()
    if args.action=='tests':raise SystemExit(tests(args.team_root))
    globals()[args.action](args.team_root)
