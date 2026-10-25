"""Fixed, exploratory direct-valuation challengers; ten targets excluded from fit."""
from pathlib import Path
import sys,json,hashlib,os
import numpy as np
import pandas as pd
from sklearn.pipeline import make_pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import Ridge
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.decomposition import TruncatedSVD
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/'src'))
from modular_validation.data import load_corpus
from modular_validation.evaluation import verify_experiment_seal
OUT=Path(os.environ.get('QUAL2CAST_EXPERIMENT_DIR') or 'outputs-local/modular-validation')
OUT=(OUT if OUT.is_absolute() else ROOT/OUT).resolve()
PARAMETERS=OUT/'parameters.json' if (OUT/'parameters.json').exists() else ROOT/'config/modular_validation_parameters.json'

def digest(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def frozen_model_configuration(parameters):
    """Check the actual fixed model definitions against their declared forms."""
    expected=['Ridge(alpha=10)', 'HistGradientBoostingRegressor(max_iter=100,max_leaf_nodes=15,l2_regularization=1,early_stopping=False)']
    declared=parameters['direct_valuation_challengers']
    if declared.get('models')!=expected or declared.get('seed')!=4511:
        raise RuntimeError('Direct-model implementation does not match frozen declared hyperparameters')
    return declared

def prediction_diagnostics(prediction, observed, target_ebitda, financial_row):
    """Record uncertainty and finite errors without changing the fitted model."""
    finite_prediction=bool(np.isfinite(prediction))
    valid=finite_prediction and prediction>0 and np.isfinite(observed) and observed>0 and np.isfinite(target_ebitda) and target_ebitda>0
    missing_fields=financial_row.index[financial_row.isna()].tolist()
    return {'prediction':float(prediction) if finite_prediction else None,
            'finite_prediction':finite_prediction,'financial_missing_fields':json.dumps(missing_fields),
            'financial_missing_count':len(missing_fields),
            'financial_missing_policy':'training_median_imputation_with_indicators_no_new_abstention_threshold',
            'observed_multiple':float(observed) if np.isfinite(observed) else None,
            'snapshot_ape':float(abs(prediction-observed)/observed) if valid else None,
            'snapshot_absolute_log_error':float(abs(np.log(prediction/observed))) if valid else None,
            'status':'exploratory_undated_cross_section' if finite_prediction else 'unavailable_nonfinite_prediction'}

def main():
    out=OUT; design=json.loads((out/'design_freeze.json').read_text())
    seal=out/'evaluation/all_rankings_freeze.json'
    if not seal.exists(): raise RuntimeError('Rankings must be frozen before valuation training')
    frozen=json.loads(seal.read_text())
    current={'ranking_inputs':{rel:digest(out/rel) for rel in frozen['ranking_inputs']},
             'design_sha256':digest(out/'design_freeze.json'),
             'parameter_sha256':digest(PARAMETERS),
             'evaluation_script_sha256':digest(ROOT/'scripts/evaluate_modular_validation.py'),
             'direct_valuation_script_sha256':digest(__file__),
             'module_sha256':{p.name:digest(p) for p in sorted((ROOT/'src/modular_validation').glob('*.py'))}}
    proof=verify_experiment_seal(frozen,current)
    parameters=json.loads(PARAMETERS.read_text())
    declared=frozen_model_configuration(parameters)
    corpus=load_corpus(design['team_root']); U=corpus.universe.set_index('IQ_COMPANY_ID')
    data=pd.read_csv(Path(design['team_root'])/'data-local/snapshots/company_list_v3_websites_fixed.csv',dtype=str).set_index('IQ_COMPANY_ID').reindex(U.index)
    cols=['target_revenue','target_margin','target_debt_to_revenue']
    financial=data[cols].apply(pd.to_numeric,errors='coerce').replace([np.inf,-np.inf],np.nan)
    financial['target_revenue']=np.log1p(financial.target_revenue.where(financial.target_revenue>=0))
    y=pd.to_numeric(data.target_ev_to_ebitda,errors='coerce')
    ebitda=pd.to_numeric(data.target_ebitda,errors='coerce')
    targets=[t['IQ_COMPANY_ID'] for t in design['targets']]
    train=(~U.index.isin(targets))&np.isfinite(y)&(y>0)&np.isfinite(ebitda)&(ebitda>0)
    train_ids=U.index[train].tolist(); test_ids=[c for c in targets if c in U.index]
    if len(test_ids)!=len(targets) or len(set(test_ids))!=len(targets):
        raise RuntimeError('Every unique frozen target must be present in the full direct-model corpus')
    assert not(set(train_ids)&set(targets))
    tfidf=TfidfVectorizer(ngram_range=(1,2),min_df=2,max_df=.4,sublinear_tf=True,stop_words='english')
    text_train=tfidf.fit_transform(U.loc[train_ids,'clean_text'])
    text_test=tfidf.transform(U.loc[test_ids,'clean_text'])
    svd=TruncatedSVD(n_components=min(20,len(train_ids)-1,text_train.shape[1]-1),random_state=4511)
    Xt=svd.fit_transform(text_train); Xv=svd.transform(text_test)
    records=[]
    for information in ['financial_only','financial_plus_website']:
        a=financial.loc[train_ids].to_numpy(); b=financial.loc[test_ids].to_numpy()
        if information=='financial_plus_website': a=np.c_[a,Xt]; b=np.c_[b,Xv]
        for name,model in [('ridge',Ridge(alpha=10)),('hist_gradient_boosting',HistGradientBoostingRegressor(max_iter=100,max_leaf_nodes=15,l2_regularization=1,early_stopping=False,random_state=4511))]:
            learner=make_pipeline(SimpleImputer(strategy='median',add_indicator=True),StandardScaler(),model)
            learner.fit(a,np.log(y.loc[train_ids]))
            predictions=np.exp(learner.predict(b))
            for cid,prediction in zip(test_ids,predictions):
                records.append({'target_id':cid,'ticker':data.loc[cid,'target_ciq_ticker'],'model':name,
                                'information':information,'training_companies':len(train_ids),
                                **prediction_diagnostics(prediction,y.loc[cid],ebitda.loc[cid],financial.loc[cid]),
                                'role':'development' if data.loc[cid,'target_ciq_ticker']=='PCTY' else 'fresh_pilot'})
    pd.DataFrame(records).to_csv(out/'evaluation/direct_valuation_results.csv',index=False)
    (out/'evaluation/direct_valuation_manifest.json').write_text(json.dumps({'train_ids':train_ids,'held_out_ids':targets,
        'experiment_dir':str(out),'parameter_path':str(PARAMETERS),
        'training_universe':'full website-eligible team corpus, not the reduced peer-candidate pilot',
        'training_universe_company_count':len(U),'training_universe_ids':U.index.tolist(),
        'training_label_eligibility':'non-target companies with finite positive EV/EBITDA and EBITDA after seal verification',
        'prediction_target_ids':test_ids,'prediction_target_count':len(test_ids),
        'target_leakage_check':not bool(set(train_ids)&set(targets)),'text_vocabulary_fit':'training companies only',
        'svd_fit':'training companies only','imputation_and_scaling_fit':'training companies only',
        'parameters_frozen_before_outcome_access':proof['verified'],'freeze_verification':proof,
        'verified_digests':current,'declared_model_configuration':declared,'no_hyperparameter_search':True,
        'forecast_validation':False,'business_relevance_validation':False,
        'limitation':'All ten test cases share the supplied undated snapshot. These predictive estimates are not comparable-company explanations and are not a replication of the published learned-peer algorithm.'},indent=2),encoding='utf-8')
    print('DIRECT_VALUATION_COMPLETE',len(train_ids),'training companies',len(records),'predictions')
if __name__=='__main__':main()
