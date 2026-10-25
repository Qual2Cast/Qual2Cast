"""Run frozen module comparisons on the team's current, checksum-verified corpus.

This is a local experiment runner. It never writes to the team snapshot or sends
data to a service. Ranking and held-out valuation are separate stages.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from modular_validation.data import load_corpus
from modular_validation.numeric import balanced_ot, unbalanced_ot
from modular_validation.evidence_policy import profile_eligibility

OUT = Path(os.environ.get("QUAL2CAST_EXPERIMENT_DIR", ROOT / "outputs-local/modular-validation"))
if not OUT.is_absolute(): OUT = ROOT / OUT
CONFIG = OUT / "parameters.json" if (OUT / "parameters.json").exists() else ROOT / "config/modular_validation_parameters.json"
DESIGN = OUT / "design_freeze.json"

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, ensure_ascii=False, default=str), encoding="utf-8")

def start_execution(run, extra=None):
    """Preserve previous execution manifests when implementation fixes occur."""
    run.mkdir(parents=True, exist_ok=True)
    now=datetime.now(timezone.utc)
    manifest={"created_at_utc":now.isoformat(),"design_sha256":sha(DESIGN),
              "parameter_sha256":sha(CONFIG),"runner_sha256":sha(__file__),
              "module_sha256":{p.name:sha(p) for p in sorted((ROOT/'src/modular_validation').glob('*.py'))},
              "target_outcomes_opened":False, **(extra or {})}
    previous=run/'run_freeze.json'
    if previous.exists():
        history=run/'execution-history';history.mkdir(exist_ok=True)
        archived=history/f'{sha(previous)[:20]}.json'
        if not archived.exists():archived.write_bytes(previous.read_bytes())
    write_json(previous,manifest)
    write_json(run/f'execution_started_{now.strftime("%Y%m%dT%H%M%SZ")}.json',manifest)
    return manifest

def score_rows(ids, target_id, values, method, tickers):
    values = np.asarray(values, dtype=float)
    frame = pd.DataFrame({"target_id": target_id, "candidate_id": ids, "method": method,
                          "score": values})
    frame = frame[frame.candidate_id != target_id].copy()
    frame["available"] = np.isfinite(frame.score)
    frame = frame.sort_values(["available", "score", "candidate_id"], ascending=[False, False, True], kind="stable")
    frame["rank"] = pd.array([i+1 if ok else None for i, ok in enumerate(frame.available)], dtype="Int64")
    frame["target_ticker"] = tickers[target_id]
    frame["candidate_ticker"] = frame.candidate_id.map(tickers)
    return frame

def rank_matrix(matrix, index):
    values = matrix @ matrix[index].T
    return np.asarray(values.toarray() if hasattr(values, "toarray") else values).ravel()

def run_core():
    from modular_validation.features import build_features
    design, params = json.loads(DESIGN.read_text()), json.loads(CONFIG.read_text())
    run = OUT / "core"
    start_execution(run)
    corpus = load_corpus(design["team_root"])
    U = corpus.universe
    ids, tickers = U.IQ_COMPANY_ID.tolist(), dict(zip(corpus.companies.IQ_COMPANY_ID, corpus.companies.target_ciq_ticker))
    index = {cid: i for i, cid in enumerate(ids)}
    methods = ["team_tfidf", "team_lsa", "team_mpnet_cosine", "doc2vec_dbow_cosine",
               "mpnet_page_balanced", "mpnet_home_only", "mpnet_conservative_cleaning"]
    matrices, ledger, ranking_parts = {}, [], []
    targets = design["targets"]
    for method in methods:
        started = time.monotonic()
        try:
            feature_params = params
            result = build_features(corpus, OUT / "feature-cache", method, parameters=feature_params)
            assert result["ids"] == ids
            matrices[method] = result["matrix"]
            write_json(run / f"{method}_metadata.json", result["metadata"])
            for target in targets:
                cid = target["IQ_COMPANY_ID"]
                values = rank_matrix(result["matrix"], index[cid]) if cid in index else np.full(len(ids), np.nan)
                valid_rows = np.asarray(result['metadata']['valid_rows'], dtype=bool)
                values[~valid_rows] = np.nan
                if cid in index and not valid_rows[index[cid]]:
                    values[:] = np.nan
                ranking_parts.append(score_rows(ids, cid, values, method, tickers))
            ledger.append({"method": method, "status": "executed", "seconds": time.monotonic()-started,
                           "feature_cache_key": result["cache_key"]})
        except Exception as error:
            ledger.append({"method": method, "status": "failed", "reason": str(error), "traceback": traceback.format_exc()})
        write_json(run / "method_ledger.json", ledger)
        print(method, ledger[-1]["status"], round(time.monotonic()-started, 1), flush=True)
    financial_names = ["target_revenue", "target_margin", "target_debt_to_revenue"]
    snapshot = Path(design["team_root"]) / "data-local/snapshots/company_list_v3_websites_fixed.csv"
    F = pd.read_csv(snapshot, usecols=["IQ_COMPANY_ID"]+financial_names, dtype={"IQ_COMPANY_ID":str}).set_index("IQ_COMPANY_ID").reindex(ids)
    F = F.apply(pd.to_numeric, errors="coerce").replace([np.inf,-np.inf],np.nan)
    percentile = F.rank(method="average", pct=True)
    F.to_csv(run / "permitted_financial_predictors.csv", index=True)
    for target in targets:
        cid, sic = target["IQ_COMPANY_ID"], target["target_sic4_code"]
        if cid not in index:
            continue
        idx = index[cid]
        base = {m: rank_matrix(x,idx) for m,x in matrices.items()}
        if all(m in base for m in ["team_tfidf","team_lsa","team_mpnet_cosine"]):
            zscores=[]
            for m in ["team_tfidf","team_lsa","team_mpnet_cosine"]:
                v=base[m].copy(); reference=np.delete(v,idx)
                zscores.append((v-reference.mean())/reference.std(ddof=1))
            ranking_parts.append(score_rows(ids,cid,np.mean(zscores,axis=0),"team_equal_z_ensemble",tickers))
        distance = (percentile-percentile.iloc[idx]).abs().mean(axis=1).to_numpy()
        complete = F.notna().all(axis=1).to_numpy() & F.iloc[idx].notna().all()
        financial = np.where(complete,-distance,np.nan)
        ranking_parts.append(score_rows(ids,cid,financial,"financial_rank_adapted",tickers))
        same = U.target_sic4_code.eq(sic).to_numpy()
        ordinal = {c:i for i,c in enumerate(sorted(ids))}
        ranking_parts.append(score_rows(ids,cid,np.where(same,[-ordinal[c] for c in ids],np.nan),"same_sic4_id_baseline",tickers))
        ranking_parts.append(score_rows(ids,cid,np.where(same,financial,np.nan),"same_sic4_financial",tickers))
        if "team_mpnet_cosine" in base:
            dense=base["team_mpnet_cosine"]
            ranking_parts.append(score_rows(ids,cid,np.where(same,dense,np.nan),"same_sic4_mpnet",tickers))
            # Stable-ID ordinal rank RRF; exclude self from the rank reference.
            dr=score_rows(ids,cid,dense,"_dense",tickers).set_index("candidate_id")["rank"]
            fr=score_rows(ids,cid,financial,"_finance",tickers).set_index("candidate_id")["rank"]
            fusion=np.array([0.5/(60+float(dr[c]))+0.5/(60+float(fr[c])) if c!=cid and pd.notna(fr[c]) and pd.notna(dr[c]) else np.nan for c in ids])
            ranking_parts.append(score_rows(ids,cid,fusion,"mpnet_financial_rrf",tickers))
    ranking=pd.concat(ranking_parts,ignore_index=True)
    ranking.to_csv(run/"rankings.csv",index=False)
    derived=set(ranking.method)-set(methods)
    ledger += [{"method":m,"status":"executed","derivation":"frozen component combination or candidate rule"} for m in sorted(derived)]
    write_json(run/"method_ledger.json",ledger)
    write_json(run/"ranking_freeze.json",{"sha256":sha(run/"rankings.csv"),"created_at_utc":datetime.now(timezone.utc).isoformat(),"target_outcomes_opened":False})
    corpus.companies.to_csv(run/"company_identifiers.csv",index=False)
    U[["IQ_COMPANY_ID","clean_words","target_sic4_code"]].to_csv(run/"text_coverage.csv",index=False)
    write_json(run/"input_provenance.json",corpus.provenance)
    print("CORE_COMPLETE",len(ranking),"rows",ranking.method.nunique(),"methods",flush=True)

def run_profiles(profile_path):
    from modular_validation.features import build_activity_embeddings, _encode_groups, _unit
    design=json.loads(DESIGN.read_text()); corpus=load_corpus(design["team_root"])
    if design.get('pilot_company_ids'):
        selected=set(design['pilot_company_ids'])
        corpus.universe=corpus.universe[corpus.universe.IQ_COMPANY_ID.isin(selected)].copy()
        corpus.documents=corpus.documents[corpus.documents.company_id.isin(selected)].copy()
        if set(corpus.universe.IQ_COMPANY_ID)!=selected:raise RuntimeError('Pilot IDs not all website eligible')
        corpus.provenance={**corpus.provenance,'pilot_company_ids':sorted(selected),'candidate_pool_sha256':sha(OUT/'candidate_pool_freeze.json')}
    U=corpus.universe; ids=U.IQ_COMPANY_ID.tolist(); idx={c:i for i,c in enumerate(ids)}
    tickers=dict(zip(corpus.companies.IQ_COMPANY_ID,corpus.companies.target_ciq_ticker))
    profiles=json.loads(Path(profile_path).read_text(encoding="utf-8"))
    if set(profiles)!=set(ids):raise RuntimeError('Profile map must exactly match comparison universe')
    eligibility={cid:profile_eligibility(profiles.get(cid)) for cid in ids}
    params=json.loads(CONFIG.read_text()); run=OUT/'profiles'; run.mkdir(exist_ok=True)
    start_execution(run,{'profile_map_sha256':sha(profile_path)})
    activities=build_activity_embeddings(corpus,OUT/"feature-cache",profiles,parameters=params)
    centroids=np.full((len(ids),768),np.nan)
    for cid,record in activities.items():
        M=record['matrix']
        if eligibility[cid][0] and len(M) and np.isfinite(M).all():
            centroids[idx[cid]]=_unit(M.mean(axis=0,keepdims=True))[0]
    parts=[]; transport=[]; facet_diagnostics=[]
    all_facets=sorted(set(sum([params['sector_profiles'][s] for s in ['7370','2834']],[])))
    facet_texts=[]; facet_keys=[]
    for cid in ids:
        for facet in all_facets:
            values=[]
            for activity in profiles.get(cid,{}).get('known_activities',[]):
                value=activity.get('facets',{}).get(facet)
                if isinstance(value,str) and value.strip().casefold() not in {'','unknown','not stated','none','n/a'}:
                    values.append(value.strip())
            values=list(dict.fromkeys(values))
            facet_texts.append('; '.join(values)); facet_keys.append((cid,facet))
    facet_vectors,facet_encoding_info=_encode_groups(facet_texts)
    facets=dict(zip(facet_keys,facet_vectors))
    np.save(run/'profile_centroids.npy',centroids,allow_pickle=False)
    np.save(run/'facet_vectors.npy',facet_vectors,allow_pickle=False)
    write_json(run/'facet_keys.json',facet_keys)
    for target in design['targets']:
        cid=target['IQ_COMPANY_ID']; sic=target['target_sic4_code']; ti=idx.get(cid)
        if ti is None: continue
        parts.append(score_rows(ids,cid,rank_matrix(centroids,ti),'profile_activity_centroid',tickers))
        values={m:np.full(len(ids),np.nan) for m in ['balanced_activity_ot','unbalanced_activity_ot','unbalanced_ot_rho_0.25','unbalanced_ot_rho_4.0','sector_activity_profile']}
        A=activities[cid]['matrix']
        for peer in ids:
            if peer==cid:continue
            pi=idx[peer]; B=activities[peer]['matrix']
            if eligibility[cid][0] and eligibility[peer][0] and len(A) and len(B) and np.isfinite(A).all() and np.isfinite(B).all():
                cost=np.clip(1-A@B.T,0,2); a=np.ones(len(A))/len(A); b=np.ones(len(B))/len(B)
                specifications=[('balanced_activity_ot',None),('unbalanced_activity_ot',1.0),('unbalanced_ot_rho_0.25',0.25),('unbalanced_ot_rho_4.0',4.0)]
                for method,rho in specifications:
                    r=balanced_ot(cost,a,b) if rho is None else unbalanced_ot(cost,a,b,reg=.05,reg_m=rho)
                    if r.get('distance') is not None: values[method][pi]=-r['distance']
                    transport.append({'target_id':cid,'candidate_id':peer,'method':method,
                                      'target_activities':len(A),'candidate_activities':len(B),
                                      'target_profile_status':profiles[cid]['status'],'candidate_profile_status':profiles[peer]['status'],
                                      **{key:r.get(key) for key in ['status','distance','full_objective','linear_cost','transported_mass','source_l1_deviation','target_l1_deviation','source_deficit','target_deficit','source_surplus','target_surplus','objective_terms','converged','warnings']}})
            if eligibility[cid][0] and eligibility[peer][0] and str(U.iloc[pi].target_sic4_code)==sic:
                scores=[]; known=[]
                for facet in params['sector_profiles'][sic]:
                    x,y=facets[(cid,facet)],facets[(peer,facet)]
                    if np.isfinite(x).all() and np.isfinite(y).all():
                        scores.append(float(np.clip(x@y,-1,1)));known.append(facet)
                if scores: values['sector_activity_profile'][pi]=float(np.mean(scores))
                facet_diagnostics.append({'target_id':cid,'candidate_id':peer,'shared_known_facets':known,
                                          'known_count':len(known),'declared_count':5,'scores':scores,
                                          'unknown_handling':'missing facets excluded and coverage reported; not encoded as mismatch',
                                          'scope_warning':'facets derived from unreviewed source-constrained model outputs'})
        for method,v in values.items():parts.append(score_rows(ids,cid,v,method,tickers))
        print('PROFILE_TARGET_COMPLETE',target['target_ciq_ticker'],len(A),'activities',flush=True)
    ranking=pd.concat(parts,ignore_index=True); ranking.to_csv(run/'rankings.csv',index=False)
    pd.DataFrame(transport).to_json(run/'transport_diagnostics.jsonl',orient='records',lines=True)
    write_json(run/'sector_facet_diagnostics.json',facet_diagnostics)
    write_json(run/'profile_coverage.json',[{'company_id':cid,'activities':len(activities[cid]['matrix']),
              'ranking_eligible':eligibility[cid][0],'eligibility_reason':eligibility[cid][1],
              **activities[cid]['metadata']} for cid in ids])
    write_json(run/'method_ledger.json',[{'method':m,'status':'executed','human_validated':False} for m in sorted(ranking.method.unique())])
    write_json(run/'ranking_freeze.json',{'sha256':sha(run/'rankings.csv'),'created_at_utc':datetime.now(timezone.utc).isoformat(),'target_outcomes_opened':False})
    write_json(run/'facet_encoding_metadata.json',facet_encoding_info)
    print('PROFILES_COMPLETE',ranking.method.nunique(),'methods',flush=True)

if __name__=="__main__":
    parser=argparse.ArgumentParser(); parser.add_argument("stage",choices=["core","profiles"])
    parser.add_argument("--profiles"); args=parser.parse_args()
    if args.stage=="core": run_core()
    else: run_profiles(args.profiles)
