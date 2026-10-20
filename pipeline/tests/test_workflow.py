"""Workflow boundary and numerical regression checks."""
import json
import numpy as np
import pandas as pd
import pytest
from pipeline.config import Configuration
from pipeline.inputs import aligned_inputs
from pipeline.workflow import CompanyWorkflow
from pipeline.evaluation import human_ranking_metrics
from matching.factors import rank_distances
from matching.evidence_review import validate_review
from valuation.aggregators import aggregate_multiple

@pytest.fixture
def workflow():
    n=8
    raw=pd.DataFrame({'IQ_COMPANY_ID':[str(i) for i in range(n)],
        'target_ciq_ticker':[f'T{i}' for i in range(n)],'target_company_name':['Company']*n,
        'target_ciq_website':['https://example.org']*n,'text':['business']*n,'urls':['https://example.org']*n,
        'words':[200]*n,'status':['ok']*n,'page_count':[1]*n,'target_revenue':np.arange(1,n+1)*100.,
        'target_ebitda':np.arange(1,n+1)*10.,'target_debt_to_revenue':[.1]*n,
        'target_ev_to_ebitda':np.arange(1,n+1)*2.,'target_sic4_code':['7370']*n})
    d,f,o=aligned_inputs(raw)
    E=np.random.default_rng(13).normal(size=(n,4))
    return CompanyWorkflow(d,f,{name:E for name in ['mpnet','tfidf','lsa']}),o.set_index('IQ_COMPANY_ID').target_ev_to_ebitda

def test_target_outcome_never_changes_prediction(workflow):
    w,y=workflow
    first=w.run('T0',peer_multiples=y)
    altered=y.copy();altered.loc['0']=999999.
    second=w.run('T0',peer_multiples=altered)
    assert first['peers']==second['peers']
    assert first['valuation']==second['valuation']
    assert not first['audit']['self_match']

def test_restricted_candidate_pool_is_obeyed(workflow):
    w,y=workflow
    r=w.run('T0',peer_multiples=y,candidate_ids=['0','1','2'])
    assert {x['peer_id'] for x in r['peers']}<={'1','2'}
    assert r['valuation']['multiple'] is None

def test_missing_scale_abstains_instead_of_imputing_match(workflow):
    w,y=workflow;w.finance.loc['0','revenue']=np.nan
    r=w.run('T0',Configuration(factors='revenue'),y)
    assert r['peers']==[] and r['valuation']['multiple'] is None

def test_nonpositive_target_ebitda_abstains(workflow):
    w,y=workflow;w.finance.loc['0','ebitda']=-1
    r=w.run('T0',peer_multiples=y)
    assert r['valuation']['multiple'] is None and r['valuation']['ev_source_units'] is None

def test_no_false_equity_value(workflow):
    w,y=workflow
    assert w.run('T0',peer_multiples=y)['valuation']['equity_value'] is None

def test_positive_multiples_and_harmonic_mean():
    assert aggregate_multiple([2,4,8,-3,np.nan],'harmonic')['multiple']==pytest.approx(24/7)
    assert aggregate_multiple([2,4,-3],'median')['multiple'] is None

def test_weight_rescaling_invariant():
    f=pd.DataFrame({'a':[1.,3.,5.],'b':[3.,2.,1.]})
    a=rank_distances(f.iloc[0],f,f,['a','b'],[.3,.7])
    b=rank_distances(f.iloc[0],f,f,['a','b'],[3,7])
    np.testing.assert_allclose(a,b)

def test_ndcg_uses_full_judged_pool():
    m=human_ranking_metrics(['weak'],{'weak':1,'strong':3},k=1)
    assert m['ndcg']==pytest.approx(1/7)
    assert human_ranking_metrics(['x'],{})['ndcg'] is None
    assert human_ranking_metrics(['x'],{'y':3})['status']=='incomplete_judgments'

def test_model_quote_does_not_become_human_validation():
    doc={'source_id':'A:1','text':'This firm distributes industrial equipment to factories.', 'source_excerpt_truncated':False}
    obj={'verdict':'strong','target_source_id':'A:1','peer_source_id':'A:1',
         'target_quote':doc['text'],'peer_quote':doc['text']}
    r=validate_review({'text':json.dumps(obj)},[doc],[doc])
    assert r['validated_verdict']=='strong' and not r['human_verified']
    obj['peer_quote']='This firm manufactures all industrial equipment itself.'
    assert validate_review({'text':json.dumps(obj)},[doc],[doc])['validated_verdict']=='invalid'

def test_invalid_weights_rejected():
    with pytest.raises(ValueError): Configuration(factors='all_three',factor_weights=(-1,1,1))
    with pytest.raises(ValueError): Configuration(factors='all_three',factor_weights=(0,0,0))
