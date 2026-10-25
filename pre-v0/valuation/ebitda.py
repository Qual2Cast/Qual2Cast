"""EBITDA construction and explicit adjustments; never infer missing accounts.

Basis: SEC Non-GAAP C&DIs 100.01-100.05 and 103.01-103.02; IPEV (2025) 3.4.
The arithmetic checks do not establish the economic validity of an adjustment.
"""
from datetime import date, timedelta
import math


def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def from_net_income(components):
    """Signed expenses: NI + interest + tax + depreciation + amortization.

    Values must refer to the same consolidated entity, period and units.
    Net interest is accepted only when explicitly defined by the source.
    Operating income + D&A is not silently substituted for this definition.
    """
    keys = ('net_income', 'interest', 'tax', 'depreciation', 'amortization')
    missing = [k for k in keys if not finite(components.get(k))]
    return {'value': None if missing else float(sum(components[k] for k in keys)),
            'basis': 'net_income_bridge', 'missing': missing,
            'status': 'incomplete_components' if missing else 'arithmetic_reconciled',
            'components': {k: components.get(k) for k in keys}}


def adjust_ebitda(base, adjustments, policy='reviewed'):
    """Apply signed expense addbacks / gain removals with a retained ledger.

    issuer_reconciliation reproduces an issuer's statement, not our endorsement.
    reviewed requires an identified reviewer, rationale and explicit acceptance.
    Duplicate IDs and base-bridge items are always rejected to avoid double count.
    """
    if policy not in ('reviewed', 'issuer_reconciliation'):
        raise ValueError('Unknown adjustment policy')
    if not finite(base):
        return {'value': None, 'status': 'missing_base', 'ledger': []}
    ids = [a.get('id') for a in adjustments]
    if None in ids or len(ids) != len(set(ids)):
        raise ValueError('Every adjustment requires a unique ID')
    ledger = []
    for item in adjustments:
        a = dict(item)
        reasons = []
        if not finite(a.get('amount')): reasons.append('missing_amount')
        if not a.get('source_url'): reasons.append('missing_source')
        if a.get('category') in ('interest', 'tax', 'depreciation', 'amortization'):
            reasons.append('already_in_ebitda_bridge')
        if policy == 'reviewed':
            if a.get('decision') != 'accept': reasons.append('not_accepted')
            if not a.get('reviewer') or not a.get('rationale'): reasons.append('missing_review')
            if a.get('normal_recurring_cash_cost') is not False:
                reasons.append('recurrence_requires_review')
        a.update(applied=not reasons, exclusion_reasons=reasons)
        ledger.append(a)
    value = base + sum(a['amount'] for a in ledger if a['applied'])
    return {'value': float(value), 'basis': 'adjusted_ebitda', 'policy': policy,
            'status': 'issuer_reproduced_not_endorsed' if policy == 'issuer_reconciliation'
                      else 'reviewed_adjustments_only', 'ledger': ledger,
            'pending_adjustments': sum(not a['applied'] for a in ledger)}


def ltm_ebitda(periods, method, as_of):
    """Four discrete quarters, or FY + current YTD - prior corresponding YTD.

    Dates are inclusive. No annualization of a lone quarter. Fiscal 52/53-week
    calendars needing a custom calendar are rejected by the YTD route.
    """
    if method not in ('four_quarters', 'fy_plus_ytd'):
        raise ValueError('Unknown LTM method')
    expected = 4 if method == 'four_quarters' else 3
    if len(periods) != expected: raise ValueError('Wrong number of periods')
    for p in periods:
        for k in ('start', 'end', 'available_on', 'basis', 'currency', 'units', 'entity', 'source_url'):
            if not p.get(k): raise ValueError('Missing period metadata: '+k)
        if not finite(p.get('value')): raise ValueError('Missing period value')
        if date.fromisoformat(p['available_on']) > date.fromisoformat(as_of):
            raise ValueError('Financial statement was not available at the measurement date')
        if not p['start'] <= p['end'] <= p['available_on']:
            raise ValueError('Invalid reporting chronology')
    for k in ('basis', 'currency', 'units', 'entity'):
        if len({p[k] for p in periods}) != 1: raise ValueError('Incompatible '+k)
    if method == 'four_quarters':
        p = sorted(periods, key=lambda x:x['start'])
        if any(not 75 <= (date.fromisoformat(x['end'])-date.fromisoformat(x['start'])).days+1 <= 100 for x in p):
            raise ValueError('Expected discrete quarterly flows, not cumulative YTD')
        if any(date.fromisoformat(b['start']) != date.fromisoformat(a['end'])+timedelta(days=1)
               for a,b in zip(p,p[1:])): raise ValueError('Quarter gap or overlap')
        start,end,value = p[0]['start'],p[-1]['end'],sum(x['value'] for x in p)
    else:
        fy, current, prior = periods
        fy_end = date.fromisoformat(fy['end'])
        if not 350 <= (fy_end-date.fromisoformat(fy['start'])).days+1 <= 380:
            raise ValueError('Expected a complete fiscal year')
        if date.fromisoformat(current['start']) != fy_end+timedelta(days=1) or prior['start'] != fy['start']:
            raise ValueError('YTD does not align with fiscal year')
        a,b = date.fromisoformat(current['end']),date.fromisoformat(prior['end'])
        if (a.month,a.day) != (b.month,b.day) or a.year != b.year+1 or prior['end'] > fy['end']:
            raise ValueError('Noncorresponding YTD periods')
        start,end,value = (b+timedelta(days=1)).isoformat(),current['end'],fy['value']+current['value']-prior['value']
    if not 350 <= (date.fromisoformat(end)-date.fromisoformat(start)).days+1 <= 380:
        raise ValueError('Combined period is not approximately twelve months')
    return {'value':float(value),'start':start,'end':end,'method':method,
            'basis':periods[0]['basis'],'currency':periods[0]['currency'],
            'units':periods[0]['units'],'source_urls':list(dict.fromkeys(p['source_url'] for p in periods)),
            'status':'period_arithmetic_verified'}
