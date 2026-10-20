"""Financial definition, chronology, missing-data and input-identity boundaries."""
import numpy as np
import pandas as pd
import pytest
from types import SimpleNamespace
from valuation.ebitda import from_net_income,adjust_ebitda,ltm_ebitda
from valuation.measurement import financial_comparability,equity_bridge,accuracy_summary
from valuation.aggregators import aggregate_multiple
from pipeline.company import resolve_company


def test_ebitda_requires_net_income_and_preserves_signed_tax():
    assert from_net_income(dict(net_income=10,interest=2,tax=-1,depreciation=3,amortization=1))['value']==15
    assert from_net_income(dict(operating_income=10,depreciation=3,amortization=1))['value'] is None


def test_unapproved_and_duplicate_addbacks_are_not_accepted():
    item=dict(id='gain',amount=-4,source_url='https://example.org',category='gain',decision='pending')
    assert adjust_ebitda(100,[item])['value']==100
    assert adjust_ebitda(100,[item],'issuer_reconciliation')['value']==96
    with pytest.raises(ValueError): adjust_ebitda(100,[item,item])
    item.update(decision='accept',reviewer='Independent reviewer',rationale='Disposed asset',normal_recurring_cash_cost=False)
    assert adjust_ebitda(100,[item])['value']==96
    item['category']='depreciation'
    assert adjust_ebitda(100,[item])['value']==100


def period(start,end,value):
    return dict(start=start,end=end,value=value,available_on='2026-08-01',entity='A',
                currency='USD',units='million',basis='net_income_bridge',source_url='https://example.org')


def test_ltm_two_routes_and_lookahead():
    fy=period('2025-01-01','2025-12-31',100)
    ytd=period('2026-01-01','2026-06-30',60)
    prior=period('2025-01-01','2025-06-30',45)
    assert ltm_ebitda([fy,ytd,prior],'fy_plus_ytd','2026-10-19')['value']==115
    with pytest.raises(ValueError): ltm_ebitda([fy,ytd,prior],'fy_plus_ytd','2026-07-01')
    quarters=[period('2025-07-01','2025-09-30',25),period('2025-10-01','2025-12-31',30),
              period('2026-01-01','2026-03-31',28),period('2026-04-01','2026-06-30',32)]
    assert ltm_ebitda(quarters,'four_quarters','2026-10-19')['value']==115
    quarters[1]['start']='2025-09-30'
    with pytest.raises(ValueError): ltm_ebitda(quarters,'four_quarters','2026-10-19')


def test_basis_dates_and_periods_must_match():
    target=dict(period_start='2025-07-01',period_end='2026-06-30',available_on='2026-08-01',
        basis='net_income_bridge',currency='USD',units='million',lease_basis='rent_expensed',
        source_url='https://example.org',definition_verified=True,consolidated_scope_verified=True)
    peer=dict(target,peer_id='B',ev_date='2026-10-19',multiple_basis_verified=True,ev_definition_verified=True)
    assert financial_comparability(target,[peer],'2026-10-19')['status']=='metadata_aligned'
    peer['basis']='issuer_adjusted'
    assert financial_comparability(target,[peer],'2026-10-19')['compatible_peers']==0
    assert financial_comparability({},[{}])['compatible_peers']==0


def test_equity_needs_explicit_zero_not_missing():
    assert equity_bridge(100,cash=10,debt=30,basis_verified=True)['value'] is None
    assert equity_bridge(100,cash=10,debt=30,preferred=0,noncontrolling=0,other_claims=0,
                         nonoperating_assets=0,basis_verified=True)['value']==80


def test_abstentions_remain_in_success_denominator_and_log_error_is_symmetric():
    r=accuracy_summary([10,10,10],[10,20,np.nan])
    assert r['coverage']==pytest.approx(2/3) and r['within25_all_targets']==pytest.approx(1/3)
    assert accuracy_summary([10],[20])['mean_absolute_log_error']==pytest.approx(
        accuracy_summary([10],[5])['mean_absolute_log_error'])


def test_leave_out_uses_selected_estimator_not_always_median():
    r=aggregate_multiple([2,4,8],'harmonic')
    assert r['leave_one_peer_out_span']==pytest.approx(16/3-8/3)
    r=aggregate_multiple([2,4,8],'rank_weighted')
    expected=[(4/2+8/3)/(1/2+1/3),(2+8/3)/(1+1/3),(2+4/2)/(1+1/2)]
    assert r['leave_one_peer_out_span']==pytest.approx(max(expected)-min(expected))


def test_identity_name_host_ambiguity_and_no_domain_impersonation():
    w=SimpleNamespace(data=pd.DataFrame({'IQ_COMPANY_ID':['1','2'],
        'target_ciq_ticker':['AA','AB'],'target_company_name':['Example Holdings, Inc.','Example Systems Inc.'],
        'target_ciq_website':['https://www.example.com','https://systems.example.org']}))
    assert resolve_company(w,'Example Holdings')['status']=='resolved'
    assert resolve_company(w,'https://example.com/about')['status']=='resolved'
    assert resolve_company(w,'Example')['status']=='ambiguous'
    assert resolve_company(w,'https://example.com.attacker.org')['status']=='not_in_cached_universe'
    assert resolve_company(w,'https://user@example.com')['status']=='not_in_cached_universe'
