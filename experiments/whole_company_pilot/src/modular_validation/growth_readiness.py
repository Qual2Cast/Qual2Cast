"""Pure growth-data contracts, not a collector, forecaster or source-truth oracle.

Functions accept in-memory mappings and return JSON-safe diagnostics. They never
read files, request a service, inspect valuations, or assign predictive weights.
Timestamp strings must contain an explicit timezone. Date-only publication
records must be conservatively resolved by the adapter, not guessed here.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from datetime import date, datetime, timedelta, timezone
import hashlib
import math
import re
from urllib.parse import urlsplit

VERSION = '2026-10-18-growth-contract-v1'
EVENT_SOURCE_TYPES = {'company_website', 'company_press', 'careers', 'regulator', 'trial_registry'}
REGIMES = {'website_only', 'candidate_filing_enriched', 'mentor_permitted_financial'}
HASH = re.compile(r'^[a-fA-F0-9]{64}$')


def _time(value, field):
    if isinstance(value, datetime):
        result = value
    elif isinstance(value, str):
        result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    else:
        raise ValueError(f'{field} must be an ISO timestamp with timezone')
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError(f'{field} must contain an explicit timezone')
    return result.astimezone(timezone.utc)


def _day(value, field):
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if not isinstance(value, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
        raise ValueError(f'{field} must be YYYY-MM-DD')
    return date.fromisoformat(value)


def _anniversary(value, years):
    try:
        return value.replace(year=value.year + years)
    except ValueError:  # February 29 -> February 28, never an inferred fiscal date.
        return value.replace(year=value.year + years, day=28)


def _host(url):
    try:
        parsed = urlsplit(str(url))
        return parsed.hostname.lower() if parsed.scheme in ('http', 'https') and parsed.hostname and not parsed.username else None
    except ValueError:
        return None


def _allowed(url, allowed_domains):
    host = _host(url)
    return bool(host and any(host == d.lower() or host.endswith('.' + d.lower()) for d in allowed_domains))


def _result(errors, warnings=(), **extra):
    return {'valid': not errors, 'errors': list(errors), 'warnings': list(warnings), **extra}


def validate_source(source: Mapping, *, company_role: str, regime: str,
                    allowed_domains: Sequence[str]) -> dict:
    """Validate declared provenance/policy; metadata cannot prove a source true.

    A live fetch with an old printed publication date does not establish old
    availability. Earlier availability requires separately retained archive or
    publication-proof metadata. Callers must verify that proof's content.
    """
    if company_role not in ('target', 'candidate') or regime not in REGIMES:
        raise ValueError('Unknown company role or information regime')
    errors, warnings = [], []
    for key in ('source_id', 'company_id', 'source_url', 'source_type'):
        if not str(source.get(key, '')).strip(): errors.append('missing_' + key)
    if not _allowed(source.get('source_url'), allowed_domains): errors.append('source_domain_not_allowed')
    for key in ('content_sha256', 'evidence_text_sha256'):
        if not HASH.fullmatch(str(source.get(key, ''))): errors.append('invalid_' + key)
    kind = source.get('source_type')
    url = str(source.get('source_url', '')).lower()
    looks_filing = bool(re.search(r'/archives/edgar/|(?:form[-_/ ]?)10[-_ ]?[kq]\b|/sec-filings/', url))
    if looks_filing and kind != 'filing': errors.append('filing_url_misclassified')
    if kind == 'filing' or looks_filing:
        if company_role == 'target': errors.append('target_filing_prohibited')
        elif regime != 'candidate_filing_enriched': errors.append('candidate_filing_requires_separate_arm')
    elif kind == 'approved_financial_data':
        if regime != 'mentor_permitted_financial': errors.append('financial_source_requires_separate_arm')
    elif kind not in EVENT_SOURCE_TYPES:
        errors.append('source_type_not_supported')
    times = {}
    for key in ('captured_at', 'first_available_at'):
        try: times[key] = _time(source.get(key), key)
        except (ValueError, TypeError): errors.append('invalid_' + key)
    if source.get('published_at') is not None:
        try: times['published_at'] = _time(source['published_at'], 'published_at')
        except (ValueError, TypeError): errors.append('invalid_published_at')
    if 'first_available_at' in times:
        first = times['first_available_at']
        basis = source.get('availability_basis')
        if basis == 'first_observed_capture':
            if 'captured_at' in times and first < times['captured_at']:
                errors.append('live_capture_cannot_backdate_availability')
        elif basis in ('archived_capture', 'independent_publication_proof'):
            proof = source.get('availability_proof', {})
            if not _host(proof.get('url')) or not HASH.fullmatch(str(proof.get('sha256', ''))):
                errors.append('availability_proof_missing')
            try:
                proof_time = _time(proof.get('observed_at'), 'proof.observed_at')
                if first < proof_time: errors.append('availability_precedes_proof')
                if 'captured_at' in times and proof_time > times['captured_at']:
                    errors.append('proof_after_capture')
            except (ValueError, TypeError): errors.append('invalid_availability_proof_time')
            warnings.append('Proof metadata is checked structurally; source contents and timestamps require audit.')
        else: errors.append('availability_basis_missing_or_unsupported')
        if 'published_at' in times and first < times['published_at']:
            errors.append('availability_precedes_publication')
        if 'captured_at' in times and 'published_at' in times and times['published_at'] > times['captured_at']:
            errors.append('publication_after_capture')
    warnings.append('Allowed domain and literal evidence do not establish independent truth or whole-company coverage.')
    return _result(errors, warnings)


def validate_event(event: Mapping, *, cutoff, company_role: str, regime: str,
                   allowed_domains: Sequence[str], evidence_texts: Mapping[str, str]) -> dict:
    """Validate one dated, attributed source-backed event before feature counts.

    event_date is the observed announcement/completion date; effective_date may
    be future only for an explicitly announced/planned event. Unknown duration
    remains unknown. No event gets a growth weight here.
    """
    cut = _time(cutoff, 'cutoff')
    errors, warnings = [], []
    for key in ('event_id', 'event_key', 'company_id', 'event_type'):
        if not str(event.get(key, '')).strip(): errors.append('missing_' + key)
    source = event.get('source')
    if not isinstance(source, Mapping): return _result(errors + ['source_missing'])
    checked = validate_source(source, company_role=company_role, regime=regime, allowed_domains=allowed_domains)
    errors += checked['errors']; warnings += checked['warnings']
    if source.get('company_id') != event.get('company_id'): errors.append('source_company_mismatch')
    if event.get('subject_company_id') != event.get('company_id'): errors.append('event_subject_mismatch')
    subject_role = event.get('subject_role')
    if subject_role == 'subsidiary':
        if not event.get('group_scope_evidence'): errors.append('subsidiary_scope_unverified')
        else: warnings.append('Group-scope evidence needs independent entity review; existence of a field is not proof.')
    elif subject_role != 'own_company': errors.append('customer_partner_or_executive_event_not_own_activity')
    if event.get('signal_duration') not in ('temporary', 'durable', 'unknown'):
        errors.append('duration_must_be_explicit')
    status = event.get('event_status')
    if status not in ('announced', 'completed', 'cancelled'): errors.append('invalid_event_status')
    try:
        event_day = _day(event.get('event_date'), 'event_date')
        if event_day > cut.date(): errors.append('event_after_cutoff')
    except (ValueError, TypeError): errors.append('invalid_event_date')
    if event.get('effective_date') is not None:
        try:
            if _day(event['effective_date'], 'effective_date') > cut.date() and status != 'announced':
                errors.append('future_effective_date_not_announced')
        except (ValueError, TypeError): errors.append('invalid_effective_date')
    try:
        if _time(source.get('first_available_at'), 'first_available_at') > cut:
            errors.append('source_not_available_at_cutoff')
    except (ValueError, TypeError): pass  # Already reported by source validator.
    sid = source.get('source_id'); text = evidence_texts.get(sid)
    quote = event.get('evidence_quote')
    if not isinstance(text, str): errors.append('evidence_text_unavailable')
    else:
        if hashlib.sha256(text.encode('utf-8')).hexdigest() != source.get('evidence_text_sha256'):
            errors.append('evidence_text_hash_mismatch')
        if not isinstance(quote, str) or not quote.strip() or quote not in text:
            errors.append('evidence_quote_not_literal')
    return _result(errors, warnings, eligible_for_feature_count=not errors,
                   signal_duration=event.get('signal_duration'), predictive_weight=None)


def validate_event_batch(events: Sequence[Mapping], **kwargs) -> dict:
    """Keep one eligible record per supplied semantic event_key; never count PR copies.

    event_key assignment itself needs an entity/product/date audit. Matching
    quotes or URLs alone cannot establish that two articles describe one event.
    """
    duplicate_ids={k for k,n in Counter(e.get('event_id') for e in events).items() if n>1}
    checked=[validate_event(e, **kwargs) for e in events]
    seen=set(); included=[]; rows=[]
    def availability_key(i):
        source=events[i].get('source',{})
        try: available=_time(source.get('first_available_at'), 'first_available_at')
        except (ValueError, TypeError, AttributeError): available=datetime.max.replace(tzinfo=timezone.utc)
        return available, str(events[i].get('event_id',''))
    order=sorted(range(len(events)), key=availability_key)
    for i in order:
        e=events[i]; r=checked[i]
        if e.get('event_id') in duplicate_ids:
            r['errors'].append('duplicate_event_id');r['valid']=False;r['eligible_for_feature_count']=False
        key=(e.get('company_id'),e.get('event_key'))
        duplicate=r['eligible_for_feature_count'] and key in seen
        if r['eligible_for_feature_count'] and not duplicate:
            seen.add(key);included.append(e['event_id'])
        rows.append({'event_id':e.get('event_id'),'validation':r,'duplicate_event_key':bool(duplicate),
                     'counted':r['eligible_for_feature_count'] and not duplicate})
    return {'included_event_ids':included,'rows':rows,'no_fixed_predictive_weights':True}


def _panel_key(row):
    return tuple(row.get(k) for k in ('company_id','metric','frequency','period_start','period_end'))


def validate_revenue_panel(rows: Sequence[Mapping]) -> dict:
    """Validate actual periodic revenues and explicitly versioned restatements.

    Numeric values are supplied by the caller; this module reads no outcomes.
    Currency, unit, consolidation/accounting definitions are required. Values
    from different scopes/units are never silently standardized or converted.
    """
    errors=[]; groups=defaultdict(list)
    if not rows: errors.append({'codes':['no_revenue_observations']})
    id_counts=Counter(r.get('observation_id') for r in rows)
    for i,r in enumerate(rows):
        local=[]
        for key in ('observation_id','company_id','revision_id','currency','unit','consolidation_scope','accounting_basis'):
            if not str(r.get(key,'')).strip(): local.append('missing_'+key)
        if id_counts[r.get('observation_id')]>1: local.append('duplicate_observation_id')
        if r.get('metric')!='revenue' or r.get('value_status')!='actual': local.append('requires_actual_revenue')
        try:
            value=float(r.get('value'))
            if not math.isfinite(value) or value<0: local.append('revenue_not_finite_nonnegative')
        except (TypeError,ValueError,OverflowError): local.append('invalid_revenue_value')
        frequency=r.get('frequency')
        if frequency not in ('annual','quarterly','ttm'): local.append('unsupported_frequency')
        try:
            start=_day(r.get('period_start'),'period_start');end=_day(r.get('period_end'),'period_end')
            days=(end-start).days+1
            bounds=(70,110) if frequency=='quarterly' else (330,400)
            if not bounds[0]<=days<=bounds[1]: local.append('period_duration_inconsistent')
            available=_time(r.get('first_available_at'),'first_available_at')
            if available.date()<end: local.append('actual_revenue_available_before_period_end')
        except (ValueError,TypeError): local.append('invalid_period_or_availability')
        sources=r.get('sources')
        if not isinstance(sources,list) or not sources or any(not isinstance(s,Mapping) or not _host(s.get('url')) or not HASH.fullmatch(str(s.get('sha256',''))) for s in sources):
            local.append('revenue_source_provenance_missing')
        groups[_panel_key(r)].append(r)
        if local: errors.append({'row':i,'observation_id':r.get('observation_id'),'codes':local})
    for key,versions in groups.items():
        if len(versions)<2: continue
        rev=[r.get('revision_id') for r in versions]
        if len(set(rev))!=len(rev):
            errors.append({'period':key,'codes':['duplicate_firm_period_revision']})
        try: ordered=sorted(versions,key=lambda r:_time(r['first_available_at'],'first_available_at'))
        except (ValueError,TypeError,KeyError): continue
        if len({_time(r['first_available_at'],'first_available_at') for r in ordered})!=len(ordered):
            errors.append({'period':key,'codes':['ambiguous_same_time_vintages']})
        if any(not r.get('is_restated',False) for r in ordered[1:]):
            errors.append({'period':key,'codes':['later_vintage_not_marked_restatement']})
        definitions=[tuple(r.get(k) for k in ('currency','unit','consolidation_scope','accounting_basis')) for r in ordered]
        if len(set(definitions))>1: errors.append({'period':key,'codes':['vintage_definition_changed_requires_reconciliation']})
    return _result(errors, rows=len(rows), firm_periods=len(groups),
                   limitations=['Schema validation does not verify reported figures or financial definitions against source contents.'])


def select_revenue_vintage(rows: Sequence[Mapping], *, cutoff) -> list[dict]:
    """Latest available, explicitly versioned observation per firm-period as of cutoff."""
    check=validate_revenue_panel(rows)
    if not check['valid']: raise ValueError(f'Invalid revenue panel: {check["errors"]}')
    cut=_time(cutoff,'cutoff');groups=defaultdict(list)
    for row in rows:
        if _time(row['first_available_at'],'first_available_at')<=cut: groups[_panel_key(row)].append(row)
    return [dict(max(group,key=lambda r:_time(r['first_available_at'],'first_available_at')))
            for _,group in sorted(groups.items())]


def trailing_twelve_month_revenue(quarters: Sequence[Mapping]) -> dict:
    """Sum exactly four actual consecutive quarters with compatible definitions.

    Caller must first select point-in-time vintages. Missing quarters do not
    become zero and overlapping year-to-date observations cannot be summed.
    """
    check=validate_revenue_panel(quarters)
    if not check['valid']: return {'status':'unavailable','reason':'invalid_panel','details':check['errors']}
    if len(quarters)!=4 or any(r['frequency']!='quarterly' for r in quarters):
        return {'status':'unavailable','reason':'requires_exactly_four_quarters'}
    ordered=sorted(quarters,key=lambda r:r['period_start'])
    keys=('company_id','metric','currency','unit','consolidation_scope','accounting_basis')
    if len({tuple(r[k] for k in keys) for r in ordered})!=1:
        return {'status':'unavailable','reason':'incompatible_quarter_definitions'}
    if any(_day(b['period_start'],'start')!=_day(a['period_end'],'end')+timedelta(days=1) for a,b in zip(ordered,ordered[1:])):
        return {'status':'unavailable','reason':'quarter_gap_or_overlap'}
    total_days=(_day(ordered[-1]['period_end'],'end')-_day(ordered[0]['period_start'],'start')).days+1
    if not 330<=total_days<=400: return {'status':'unavailable','reason':'not_a_year_of_quarters'}
    lineage=[r['observation_id'] for r in ordered]
    observation={k:ordered[0][k] for k in keys}
    observation.update(observation_id='ttm:'+'+'.join(lineage),revision_id='derived:'+ '+'.join(r['revision_id'] for r in ordered),
        frequency='ttm',period_start=ordered[0]['period_start'],period_end=ordered[-1]['period_end'],
        value=math.fsum(float(r['value']) for r in ordered),value_status='actual',is_restated=any(r.get('is_restated',False) for r in ordered),
        first_available_at=max(_time(r['first_available_at'],'first_available_at') for r in ordered).isoformat(),
        sources=[s for r in ordered for s in r['sources']])
    return {'status':'available','observation':observation,'lineage_observation_ids':lineage,'is_forecast':False}


def revenue_cagr(start: Mapping, end: Mapping, *, horizon_years=3, fiscal_tolerance_days=7) -> dict:
    """Realized annual/TTM endpoint CAGR only, not a prediction.

    Horizon is between the two revenue-period ends. A fiscal calendar tolerance
    permits 52/53-week year shifts; this does not change the exponent 1/years.
    Start must be positive; zero ending revenue yields -1; negatives are invalid.
    """
    if not isinstance(horizon_years,int) or horizon_years<1 or fiscal_tolerance_days<0:
        raise ValueError('Invalid CAGR horizon or tolerance')
    check=validate_revenue_panel([start,end])
    if not check['valid']: return {'status':'unavailable','reason':'invalid_panel','details':check['errors']}
    keys=('company_id','metric','frequency','currency','unit','consolidation_scope','accounting_basis')
    if any(start[k]!=end[k] for k in keys): return {'status':'unavailable','reason':'incompatible_endpoint_definitions'}
    if start['frequency'] not in ('annual','ttm'): return {'status':'unavailable','reason':'quarterly_revenue_is_not_annual_cagr'}
    expected=_anniversary(_day(start['period_end'],'period_end'),horizon_years)
    actual=_day(end['period_end'],'period_end')
    if abs((actual-expected).days)>fiscal_tolerance_days:
        return {'status':'unavailable','reason':'endpoint_horizon_mismatch'}
    a,b=float(start['value']),float(end['value'])
    if a<=0: return {'status':'undefined','reason':'nonpositive_start_revenue'}
    value=-1.0 if b==0 else math.expm1((math.log(b)-math.log(a))/horizon_years)
    return {'status':'available','realized_cagr':value,'horizon_years':horizon_years,
            'label_period_start':start['period_end'],'label_period_end':end['period_end'],
            'label_available_at':max(_time(r['first_available_at'],'availability') for r in (start,end)).isoformat(),
            'lineage_observation_ids':[start['observation_id'],end['observation_id']],
            'is_forecast':False,'uncertainty_interval':None}


def validate_rolling_origin_split(train: Sequence[Mapping], test: Sequence[Mapping], *, fit_at,
        preprocessing_fit_row_ids: Sequence[str], horizon_years=3, embargo_days=0,
        company_holdout=False, evaluation_at=None) -> dict:
    """Check feature and label availability, forecast horizon, split and fit lineage.

    Required row metadata: row_id, company_id, origin_at, label_period_start/end,
    label_available_at, feature_sources[{source_id, first_available_at}], and
    base_revenue_available_at. Feature proof validation is a separate earlier
    gate; passing timestamps here does not establish valid provenance.
    """
    fit=_time(fit_at,'fit_at')
    if not isinstance(horizon_years,int) or horizon_years<1 or embargo_days<0: raise ValueError('Invalid horizon or embargo')
    errors=[]
    train_ids=[r.get('row_id') for r in train];test_ids=[r.get('row_id') for r in test]
    if not train or not test: errors.append('train_and_test_must_be_nonempty')
    all_rows=list(train)+list(test)
    if any(not x for x in train_ids+test_ids): errors.append('missing_row_id')
    if any(not str(r.get('company_id','')).strip() for r in all_rows): errors.append('missing_company_id')
    if len(set(train_ids+test_ids))!=len(train_ids+test_ids): errors.append('row_overlap_or_duplicate')
    keys=[(r.get('company_id'),r.get('origin_at')) for r in all_rows]
    if len(set(keys))!=len(keys): errors.append('duplicate_company_origin')
    if not set(preprocessing_fit_row_ids)<=set(train_ids): errors.append('preprocessing_fit_includes_nontraining_rows')
    if company_holdout and {r.get('company_id') for r in train}&{r.get('company_id') for r in test}:
        errors.append('company_holdout_overlap')
    origins={'train':[],'test':[]}
    for split,rows in [('train',train),('test',test)]:
        for row in rows:
            rid=str(row.get('row_id'));prefix=split+':'+rid+':'
            try:
                origin=_time(row.get('origin_at'),'origin_at');origins[split].append(origin)
                begin=_day(row.get('label_period_start'),'label_period_start')
                end=_day(row.get('label_period_end'),'label_period_end')
                label_available=_time(row.get('label_available_at'),'label_available_at')
                base_available=_time(row.get('base_revenue_available_at'),'base_revenue_available_at')
                if begin>origin.date() or base_available>origin: errors.append(prefix+'base_revenue_unavailable_at_origin')
                if end<=origin.date(): errors.append(prefix+'label_not_forward_of_origin')
                if abs((end-_anniversary(begin,horizon_years)).days)>7: errors.append(prefix+'label_horizon_mismatch')
                if label_available.date()<end: errors.append(prefix+'label_available_before_period_end')
                sources=row.get('feature_sources')
                if not isinstance(sources,list) or not sources: errors.append(prefix+'feature_provenance_missing')
                else:
                    for source in sources:
                        if not source.get('source_id'): errors.append(prefix+'feature_source_id_missing')
                        if _time(source.get('first_available_at'),'feature.first_available_at')>origin:
                            errors.append(prefix+'feature_after_origin')
                if split=='train':
                    if origin>=fit: errors.append(prefix+'training_origin_not_before_fit')
                    if label_available>fit: errors.append(prefix+'training_label_unavailable_at_fit')
                    if end>fit.date()-timedelta(days=embargo_days): errors.append(prefix+'training_label_crosses_embargo')
                elif origin<fit: errors.append(prefix+'test_origin_before_fit')
                if evaluation_at is not None and label_available>_time(evaluation_at,'evaluation_at'):
                    errors.append(prefix+'label_unobserved_at_evaluation')
            except (ValueError,TypeError,KeyError): errors.append(prefix+'invalid_temporal_schema')
    if origins['train'] and origins['test'] and max(origins['train'])>=min(origins['test']):
        errors.append('rolling_origin_order_violation')
    return _result(errors, ['Each fold must refit preprocessing/models on permitted training rows; hyperparameter tuning must use an earlier nested temporal split.'],
                   train_rows=len(train),test_rows=len(test),is_model_evaluation=False,
                   label_horizon_years=horizon_years,company_holdout=company_holdout)
