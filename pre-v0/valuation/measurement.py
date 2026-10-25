"""Financial comparability and value bridges, separate from text similarity."""
from datetime import date
import numpy as np
from valuation.ebitda import finite


def financial_comparability(target, peers, as_of=None, max_period_gap_days=0):
    """Check declared source metadata. Exact period alignment is the default.

    A caller may explicitly permit a date gap. This is an engineering policy,
    not an empirically calibrated threshold or an audit of the source records.
    Different currency/unit scales are allowed for dimensionless multiples only
    when each numerator and denominator is internally consistent.
    """
    if max_period_gap_days < 0: raise ValueError('Period-gap tolerance cannot be negative')
    fields = ('period_start','period_end','available_on','basis','currency','units',
              'lease_basis','source_url')
    def problems(record, is_peer=False):
        missing = ['unknown_'+k for k in fields if not record.get(k)]
        if record.get('definition_verified') is not True: missing.append('definition_unverified')
        if record.get('consolidated_scope_verified') is not True: missing.append('scope_unverified')
        if as_of is None: missing.append('measurement_date_unknown')
        if record.get('period_start') and record.get('period_end'):
            days=(date.fromisoformat(record['period_end'])-date.fromisoformat(record['period_start'])).days+1
            if not 350 <= days <= 380: missing.append('not_twelve_months')
        if record.get('available_on') and record.get('period_end') and record['available_on'] < record['period_end']:
            missing.append('invalid_release_date')
        if as_of and record.get('available_on') and record['available_on'] > as_of:
            missing.append('lookahead_source')
        if is_peer:
            if not record.get('ev_date') or record['ev_date'] != as_of: missing.append('ev_date_unaligned')
            if record.get('multiple_basis_verified') is not True: missing.append('multiple_basis_unverified')
            if record.get('ev_definition_verified') is not True: missing.append('ev_definition_unverified')
        return missing
    target_issues = problems(target)
    rows=[]
    for p in peers:
        issues=problems(p,True)
        for key in ('basis','lease_basis'):
            if p.get(key) and target.get(key) and p[key]!=target[key]: issues.append('different_'+key)
        if p.get('period_end') and target.get('period_end'):
            gap=abs((date.fromisoformat(p['period_end'])-date.fromisoformat(target['period_end'])).days)
            if gap > max_period_gap_days: issues.append('period_end_unaligned')
        rows.append({'peer_id':p.get('peer_id'),'issues':issues,
                     'compatible':not issues and not target_issues})
    return {'status':'metadata_aligned' if not target_issues and rows and all(r['compatible'] for r in rows)
                    else 'unverified_financial_basis',
            'target_issues':target_issues,'peers':rows,
            'compatible_peers':sum(r['compatible'] for r in rows),
            'max_period_gap_days':max_period_gap_days,
            'business_relevance_verified':False}


def equity_bridge(ev, *, cash=None, debt=None, preferred=None, noncontrolling=None,
                  other_claims=None, nonoperating_assets=None, basis_verified=False):
    """EV + excess cash + other nonoperating assets - debt - senior claims.

    Caller must supply explicit zeros and consistent lease treatment; missing
    values are not zero. A negative residual is flagged, not floored silently.
    """
    fields=dict(cash=cash,debt=debt,preferred=preferred,noncontrolling=noncontrolling,
                other_claims=other_claims,nonoperating_assets=nonoperating_assets)
    missing=[k for k,v in fields.items() if not finite(v)]
    if not finite(ev): missing.append('enterprise_value')
    if missing or not basis_verified:
        return {'value':None,'status':'incomplete_or_unverified_bridge','missing':missing}
    value=ev+cash+nonoperating_assets-debt-preferred-noncontrolling-other_claims
    return {'value':float(value),'status':'negative_equity_residual_requires_review' if value<0 else 'computed',
            'components':fields}


def valuation_scenarios(ebitda, multiple, changes=(-.2,0,.2)):
    """Analyst-assumed sensitivity grid; not a forecast or confidence interval."""
    if not finite(ebitda) or not finite(multiple) or ebitda<=0 or multiple<=0: return []
    changes=tuple(changes)
    if any(not finite(c) or c<=-1 for c in changes): raise ValueError('Invalid scenario change')
    return [{'ebitda_change':e,'multiple_change':m,'ebitda':ebitda*(1+e),
             'multiple':multiple*(1+m),'ev':ebitda*(1+e)*multiple*(1+m),
             'meaning':'assumed sensitivity; not probability interval'} for e in changes for m in changes]


def accuracy_summary(actual, predicted):
    """Coverage plus multiple error; all-target success includes abstentions."""
    a,p=np.asarray(actual,float),np.asarray(predicted,float)
    if a.shape!=p.shape or a.ndim!=1: raise ValueError('Expected aligned one-dimensional observations')
    valid=np.isfinite(a)&np.isfinite(p)&(a>0)&(p>0)
    ratio=p[valid]/a[valid]; ape=100*np.abs(ratio-1)
    summary={'targets':len(a),'scored':int(valid.sum()),
             'coverage':float(valid.mean()) if len(a) else None,
             'status':'scored_development_only' if valid.any() else 'no_valid_pairs'}
    for name,val in {
        'median_ape':np.median(ape) if len(ape) else None,
        'mean_ape':np.mean(ape) if len(ape) else None,
        'p90_ape':np.quantile(ape,.9) if len(ape) else None,
        'median_signed_percentage_error':np.median(100*(ratio-1)) if len(ratio) else None,
        'mean_absolute_log_error':np.mean(np.abs(np.log(ratio))) if len(ratio) else None,
        'mae_multiple':np.mean(np.abs(p[valid]-a[valid])) if valid.any() else None,
        'within25_all_targets':np.sum(ape<=25)/len(a) if len(a) else None,
        'within50_all_targets':np.sum(ape<=50)/len(a) if len(a) else None,
    }.items(): summary[name]=None if val is None else float(val)
    return summary
