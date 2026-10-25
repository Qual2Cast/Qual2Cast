"""Company name / website entry point and a concise evidence-linked report.

The current public-company demonstration resolves against existing captures.
An unknown URL is never silently substituted with a similar known company.
"""
import re
from html import escape
from urllib.parse import urlsplit
import numpy as np
import pandas as pd
from pipeline.config import Configuration, AGGREGATORS, FACTOR_SETS
from valuation.aggregators import aggregate_multiple
from valuation.measurement import valuation_scenarios


def _json_safe(value):
    if isinstance(value,dict): return {k:_json_safe(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)): return [_json_safe(v) for v in value]
    if isinstance(value,(float,np.floating)): return float(value) if np.isfinite(value) else None
    if isinstance(value,np.integer): return int(value)
    return value


def _host(value):
    value=str(value).strip().lower()
    if '://' not in value: value='https://'+value
    parsed=urlsplit(value)
    if parsed.scheme not in ('http','https') or parsed.username or parsed.password: return ''
    return (parsed.hostname or '').removeprefix('www.').rstrip('.')


def _name(value):
    tokens=re.findall(r'[a-z0-9]+',str(value).lower())
    while tokens and tokens[-1] in ('inc','incorporated','corp','corporation','co','company','ltd','limited','plc'):
        tokens.pop()
    return ' '.join(tokens)


def resolve_company(workflow, query):
    query=str(query).strip()
    if not query: return {'status':'empty_query','matches':[]}
    d=workflow.data
    if '://' in query or ('.' in query and ' ' not in query):
        host=_host(query)
        mask=d.target_ciq_website.map(_host).eq(host) if host else pd.Series(False,index=d.index)
        match_type='website_host'
    else:
        ticker=d.target_ciq_ticker.str.upper().eq(query.upper())
        names=d.target_company_name.map(_name)
        mask=ticker | names.eq(_name(query)); match_type='ticker_or_normalized_name'
        if not mask.any() and _name(query):
            # Whole-token name containment only, with ambiguity returned to caller.
            wanted=' '+_name(query)+' '
            mask=names.map(lambda x:wanted in ' '+x+' '); match_type='unique_name_fragment'
    rows=d.loc[mask,['IQ_COMPANY_ID','target_ciq_ticker','target_company_name','target_ciq_website']]
    return {'status':'resolved' if len(rows)==1 else 'ambiguous' if len(rows)>1 else 'not_in_cached_universe',
            'query':query,'match_type':match_type,'matches':rows.to_dict('records'),
            'scope':f'Existing {len(d)}-company website corpus; no live discovery or new scrape in this call'}


def analyze_company(workflow, query, peer_multiples, config=None):
    """Return identity, evidence, comps, factors, valuation, growth and open issues.

    Target finance is auto-filled from the supplied public snapshot to simulate
    privately supplied revenue/EBITDA/debt. It is not extracted from a homepage.
    The target's observed multiple is never exposed in this decision report.
    """
    resolution=resolve_company(workflow,query)
    if resolution['status']!='resolved': return {'identity':resolution,'status':'identity_required'}
    config=config or Configuration()
    match=resolution['matches'][0]
    report=workflow.run(match['target_ciq_ticker'],config,peer_multiples)
    report['identity']=resolution
    report['status']='development_company_report'
    report['target_inputs']['origin']='Sponsor snapshot, simulating privately supplied financials'
    cid=report['company_id']; factors=[]
    for row in report['peers']:
        p=workflow.finance.loc[row['peer_id']]
        factors.append({'peer':row['peer'],'revenue':float(p.revenue),
                        'ebitda_margin':float(p.margin),'debt_to_revenue':float(p.debt_to_revenue),
                        'retrieval_measure':row.get('measure'),
                        'retrieval_score':row.get('retrieval_score'),
                        'factor_distance':row.get('factor_distance'),
                        'selection_rank':row['selection_rank']})
    report['factor_comparison']={'selected':list(FACTOR_SETS[config.factors]),
        'target':workflow.finance.loc[cid,['revenue','margin','debt_to_revenue']].to_dict(),
        'peers':factors,'score_interpretation':'Relative ranking within this method and corpus; not a probability of comparability'}
    report['aggregation_comparison']=[{'method':m,**aggregate_multiple(
        [p['public_peer_multiple'] for p in report['peers']],m,config.min_peers)} for m in AGGREGATORS]
    v=report['valuation']; e=report['target_inputs']['ebitda']
    v['peer_dispersion_ev'] = ([float(e*v['q25']),float(e*v['q75'])]
        if v['multiple'] is not None and np.isfinite(e) and e>0 else None)
    report['sensitivity']=valuation_scenarios(e,v['multiple'])
    report['questions_to_resolve']=[
        'Confirm all material business lines, operating roles and customer overlap for each peer.',
        'Confirm consolidated LTM EBITDA definition, period, source units, currency and adjustments.',
        'Align public-peer enterprise values, EBITDA definitions and measurement dates.',
        'Check whether EV/EBITDA suits this business; banks/lenders may require equity-based methods.',
        'Obtain cash, preferred equity, minority interests and other claims before an equity bridge.',
        'Validate dated growth evidence before estimating growth or adjusting a multiple.']
    names=', '.join(str(p['peer']) for p in report['peers']) or 'none'
    report['assessment']={
        'company':report['company_name'],
        'candidate_peers':names,
        'valuation':(f"Indicative EV/EBITDA {v['multiple']:.2f}x; enterprise-value proxy {v['ev_source_units']:,.2f} in source units."
                     if v['multiple'] is not None and v['ev_source_units'] is not None else 'Insufficient evidence for a value estimate.'),
        'range':((f"Peer-dispersion EV band {v['peer_dispersion_ev'][0]:,.2f} to {v['peer_dispersion_ev'][1]:,.2f} in source units. "
                  if v['peer_dispersion_ev'] else '')+
                 'The peer IQR and +/-20% EBITDA/multiple grid describe dispersion and assumed sensitivity; neither is a probability interval.'),
        'decision':'Initial due-diligence report. A buy/sell conclusion, expected return and verified fair value are not established.',
        'evidence_status':'Source-linked but unapproved business matches; financial measurement basis remains unverified.'}
    return _json_safe(report)


def report_html(report):
    """Small standalone reading copy; escape every external text field."""
    if report.get('status')=='identity_required':
        return '<h1>Company identity required</h1><pre>'+escape(str(report['identity']))+'</pre>'
    def table(rows):
        return pd.DataFrame(rows).to_html(index=False,escape=True,border=0) if rows else '<p>No observations.</p>'
    a=report['assessment']; v=report['valuation']
    blocks=['<!doctype html><meta charset="utf-8"><title>Company Analysis</title>',
        '<style>body{font:16px/1.6 system-ui;max-width:1120px;margin:40px auto;padding:0 24px;color:#172b3a}table{border-collapse:collapse;width:100%;font-size:13px}td,th{padding:8px;border-bottom:1px solid #ccd6db;text-align:left;overflow-wrap:anywhere}h2{margin-top:32px}a{color:#16627c}</style>',
        '<h1>'+escape(a['company'])+'</h1>',
        '<p><strong>Development estimate — public company used as a private target</strong></p>',
        '<p>'+escape(a['valuation'])+'</p><p>'+escape(a['decision'])+'</p>',
        '<p>'+escape(a['evidence_status'])+'</p>',
        '<h2>Business evidence</h2>',table(report['business_evidence']['all_known_activities']),
        '<h2>Comparable companies</h2>',table([{k:p.get(k) for k in ('peer','retrieval_score','factor_distance','selection_rank','public_peer_multiple','source_urls')} for p in report['peers']]),
        '<h2>Financial factors</h2>',table(report['factor_comparison']['peers']),
        '<h2>Multiple estimates</h2>',table([{k:r.get(k) for k in ('method','multiple','q25','q75','leave_one_peer_out_span')} for r in report['aggregation_comparison']]),
        '<p>'+escape(a['range'])+'</p><h2>Value sensitivity</h2>',table(report['sensitivity']),
        '<h2>Growth evidence</h2><pre>'+escape(str(report['growth_evidence']))+'</pre>',
        '<h2>Required review</h2><ul>'+''.join('<li>'+escape(x)+'</li>' for x in report['questions_to_resolve'])+'</ul>',
        '<p>Configuration: '+escape(str(report['configuration']))+'</p>']
    return '\n'.join(blocks)
