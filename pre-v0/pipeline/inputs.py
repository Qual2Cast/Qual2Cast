"""Separate company descriptors, permitted financials and evaluation outcomes."""
import pandas as pd

def aligned_inputs(companies):
    """Separate descriptors, allowed financials, and evaluation-only outcomes."""
    raw = companies.copy()
    raw.IQ_COMPANY_ID = raw.IQ_COMPANY_ID.astype(str)
    raw.target_sic4_code = raw.target_sic4_code.astype(str).str.zfill(4)
    descriptors = raw[['IQ_COMPANY_ID','target_ciq_ticker','target_company_name',
                       'target_ciq_website','text','urls','words','status','page_count']].copy()
    finance = pd.DataFrame({
        'company_id':raw.IQ_COMPANY_ID, 'revenue':pd.to_numeric(raw.target_revenue),
        'ebitda':pd.to_numeric(raw.target_ebitda),
        'debt_to_revenue':pd.to_numeric(raw.target_debt_to_revenue)})
    finance['margin'] = finance.ebitda / finance.revenue.where(finance.revenue > 0)
    # Debt is derived from the supplied ratio; it is not a newly obtained debt observation.
    finance['debt_derived'] = finance.revenue * finance.debt_to_revenue
    finance['date_verified'] = False
    finance['units'] = 'source units; team describes millions, independently unverified'
    outcomes = raw[['IQ_COMPANY_ID','target_ciq_ticker','target_sic4_code','target_ev_to_ebitda']].copy()
    return descriptors, finance.set_index('company_id'), outcomes
