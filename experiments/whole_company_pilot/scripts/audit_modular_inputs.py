"""Identity, coverage and allowed-financial-input audit without valuation outcomes."""
from pathlib import Path
from urllib.parse import urlsplit
import sys,json,hashlib
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from modular_validation.data import load_corpus

def hostname(value):
    value=str(value);host=urlsplit(value if '://' in value else 'https://'+value).hostname or ''
    return host.lower().removeprefix('www.')

def main():
    out=ROOT/'outputs-local/modular-validation';design=json.loads((out/'design_freeze.json').read_text())
    c=load_corpus(design['team_root']);m=c.companies.copy();m['canonical_host']=m.target_ciq_website.map(hostname)
    duplicate_hosts=m[m.canonical_host.duplicated(keep=False)].to_dict('records')
    listing_duplicates=m[m.duplicated(['target_ciq_exchange','target_ciq_ticker'],keep=False)].to_dict('records')
    mismatches=[];lookup=m.set_index('IQ_COMPANY_ID').canonical_host.to_dict()
    for d in c.documents.itertuples():
        actual,expected=hostname(d.source_url),lookup[d.company_id]
        same=actual==expected or actual.endswith('.'+expected) or expected.endswith('.'+actual)
        if not same:mismatches.append({'company_id':d.company_id,'source_id':d.source_id,'source_url':d.source_url,
                                       'expected_host':expected,'actual_host':actual,'status':'requires_attribution_check'})
    fields=['target_revenue','target_ebitda','target_margin','target_debt_to_revenue']
    f=pd.read_csv(Path(design['team_root'])/'data-local/snapshots/company_list_v3_websites_fixed.csv',usecols=['IQ_COMPANY_ID']+fields,dtype=str).set_index('IQ_COMPANY_ID')
    f=f.apply(pd.to_numeric,errors='coerce').replace([np.inf,-np.inf],np.nan)
    calculated=f.target_ebitda/f.target_revenue.replace(0,np.nan)
    delta=(calculated-f.target_margin).abs()
    target_rows=[]
    U=c.universe.set_index('IQ_COMPANY_ID')
    for t in design['targets']:
        cid=t['IQ_COMPANY_ID'];docs=c.documents[c.documents.company_id==cid]
        target_rows.append({**t,'baseline_eligible':cid in U.index,'baseline_clean_words':int(U.loc[cid,'clean_words']) if cid in U.index else 0,
                            'source_pages':len(docs),'source_timestamps':docs.fetched_at.tolist(),
                            'empty_raw_pages':int(docs.text_raw.str.strip().eq('').sum()),
                            'economic_business_weights':'unknown','valuation_date':'unknown'})
    audit={'snapshot_sha256_verified':design['snapshot_sha256'],'duplicate_company_ids':int(m.IQ_COMPANY_ID.duplicated().sum()),
           'duplicate_exchange_tickers':listing_duplicates,'shared_website_hosts':duplicate_hosts,'cross_host_sources':mismatches,
           'allowed_financial_input_counts':{col:{'finite':int(f[col].notna().sum()),'nonpositive':int((f[col]<=0).sum())} for col in fields},
           'ebitda_margin_consistency':{'compared_rows':int(delta.notna().sum()),'max_absolute_difference':float(delta.max()),
                                      'rows_difference_over_0_0001':int((delta>1e-4).sum()),'units':'fraction, not percentage points'},
           'target_outcomes_loaded':False,'valuation_dates':'not provided in snapshot','financial_definitions':'not independently aligned',
           'listing_status':'supplied snapshot only; current public listing and legal consolidation not exhaustively verified',
           'notes':'Shared domains or cross-host pages are audit flags, not automatic duplicate entities or incorrect sources.',
           'targets':target_rows}
    (out/'input_quality_audit.json').write_text(json.dumps(audit,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in audit.items() if k not in ['targets','cross_host_sources']},indent=2))
    print('cross_host_sources',len(mismatches));print(pd.DataFrame(target_rows)[['target_ciq_ticker','baseline_eligible','baseline_clean_words','source_pages','empty_raw_pages']].to_string(index=False))
if __name__=='__main__':main()
