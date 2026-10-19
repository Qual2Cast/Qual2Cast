"""Paired source-text sensitivity tests; no relevance labels or financial data.

Prepare freezes exact original/variant texts before any model scores are read.
Run uses cached frozen candidate matrices and an independently refitted, verified
TF-IDF transformer with original-corpus IDF. It never changes the core caches.
"""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from modular_validation.data import load_corpus

OUT=ROOT/'outputs-local/modular-validation'
CONFIG=OUT/'perturbation_config_freeze.json'
INPUT=OUT/'perturbation_frozen_inputs.json'

def digest_bytes(value):
    return hashlib.sha256(value).hexdigest()

def digest_text(value):
    return digest_bytes(value.encode('utf-8'))

def file_sha(path):
    return digest_bytes(Path(path).read_bytes())

def write(path,value):
    Path(path).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

def load():
    design=json.loads((OUT/'design_freeze.json').read_text(encoding='utf-8'))
    return design,load_corpus(design['team_root'])

def freeze_shared(corpus,root):
    B=corpus.team_baseline
    texts=B.page_texts(Path(root)/'outputs-local/website_scrape')
    meta=corpus.companies.merge(texts,on='IQ_COMPANY_ID',how='left')
    counts=Counter(s.lower() for text in meta.raw_text.fillna('')
                   for s in set(B.to_sentences(text)))
    return sorted(k for k,n in counts.items() if n>=B.SHARED_SENTENCE_SITES)

def process(record,B,shared):
    _,pages=B.build_prompt(record)
    text='\n'.join(pages.values())
    text,_=B.mask(text,B.name_variants(record['company_name'],record['website']),[])
    sents=B.to_sentences(text)
    rejected_boiler=[s for s in sents if B.BOILERPLATE.search(s)]
    rejected_shared=[s for s in sents if not B.BOILERPLATE.search(s) and s.lower() in shared]
    kept=[s for s in sents if not B.BOILERPLATE.search(s) and s.lower() not in shared]
    return dict(clean_text=' '.join(kept),kept_sentences=kept,
                rejected_boilerplate=rejected_boiler,rejected_shared=rejected_shared,
                masked_page_word_counts={k:len(v.split()) for k,v in pages.items()})

def prepare():
    if CONFIG.exists() or INPUT.exists():
        raise FileExistsError('Frozen perturbation inputs already exist; refusing implicit replacement.')
    design,C=load(); B=C.team_baseline
    fixtures=json.loads((OUT/'evidence_perturbation_fixtures.json').read_text(encoding='utf-8'))
    shared=freeze_shared(C,design['team_root']); shared_set=set(shared)
    index=C.universe.set_index('IQ_COMPANY_ID')
    inputs=[]
    for f in fixtures:
        if f['fixture_id']=='RIGL_live_inventory_acquisition_control':
            continue
        cid=f['company_id']
        rec=json.loads((Path(design['team_root'])/'outputs-local/website_scrape/page_text'/f'{cid}.json').read_text(encoding='utf-8'))
        pid=f['source']['page_id']
        page=next(p for p in rec['pages'] if p['page_id']==pid)
        variant=deepcopy(rec)
        changed=next(p for p in variant['pages'] if p['page_id']==pid)
        if 'restore_actual_removed_sentence' in f['fixture_id']:
            assert '\n'.join(page['blocks'])==f['original_text']
            # Never re-run upstream clean_block_logged: that is the defect tested.
            changed['blocks']=page['blocks']+[f['source']['text']]
            assert '\n'.join(changed['blocks'])==f['variant_text']
            edit_kind='restore_exact_removed_sentence_on_one_page'
            expected=f['expected_behavior']
            changed_span=f['source']['text']
        elif f['fixture_id']=='XERS_previous_employer_attribution_control':
            changed_span=f['original_text']
            assert page['blocks'].count(changed_span)==1
            changed['blocks']=[b for b in page['blocks'] if b!=changed_span]
            edit_kind='remove_one_previous_employer_block_on_P1_only'
            expected=('This single-page exclusion may move duplicate evidence to P2. '
                      'It is not a guaranteed company-wide biography exclusion. '+f['expected_behavior'])
        else:
            raise ValueError(f['fixture_id'])
        before=process(rec,B,shared_set); after=process(variant,B,shared_set)
        baseline=index.loc[cid,'clean_text'] if cid in index.index else None
        # Record whether original is exactly the frozen baseline instead of assuming.
        names=B.name_variants(rec['company_name'],rec['website'])
        changed_masked=B.mask(changed_span,names,[])[0]
        change_sents=B.to_sentences(changed_masked)
        retained_before=[s for s in change_sents if s in before['kept_sentences']]
        retained_after=[s for s in change_sents if s in after['kept_sentences']]
        scope=dict(
          source_page_id=pid,source_url=page['url'],fetched_at=page.get('fetched_at'),
          source_json_sha256=file_sha(Path(design['team_root'])/'outputs-local/website_scrape/page_text'/f'{cid}.json'),
          edit_kind=edit_kind,source_span=changed_span,source_span_after_masking=changed_masked,
          parsed_changed_sentence_count=len(change_sents),retained_changed_sentences_before=retained_before,
          retained_changed_sentences_after=retained_after,
          frozen_boilerplate_rejects=[s for s in change_sents if B.BOILERPLATE.search(s)],
          frozen_shared_rejects=[s for s in change_sents if s.lower() in shared_set],
          duplicate_source_occurrences_before=sum(changed_span in b for p in rec['pages'] for b in p['blocks']),
          duplicate_source_occurrences_after=sum(changed_span in b for p in variant['pages'] for b in p['blocks']),
          expected_source_scope_behavior=expected,
          semantic_extraction_status='not_evaluated_here; text retention is not factual semantic extraction')
        inputs.append(dict(fixture_id=f['fixture_id'],company_id=cid,ticker=index.loc[cid,'target_ciq_ticker'],
          page_id=pid,original_matches_frozen_baseline=(before['clean_text']==baseline),
          original_text_sha256=digest_text(before['clean_text']),variant_text_sha256=digest_text(after['clean_text']),
          original=before,variant=after,source_change=scope))
    assert len(inputs)==4
    assert all(x['company_id'] in index.index for x in inputs)
    # No scores or candidate matrix values have been read in prepare().
    inputs_doc=dict(created_at_utc=datetime.now(timezone.utc).isoformat(),cases=inputs,
        acquisition_diagnostic=next(f for f in fixtures if f['fixture_id']=='RIGL_live_inventory_acquisition_control'))
    write(INPUT,inputs_doc)
    freeze=dict(created_at_utc=datetime.now(timezone.utc).isoformat(),methods=['team_tfidf','team_mpnet_cosine'],
      design_sha256=file_sha(OUT/'design_freeze.json'),fixtures_sha256=file_sha(OUT/'evidence_perturbation_fixtures.json'),
      frozen_input_sha256=file_sha(INPUT),runner_sha256=file_sha(__file__),
      team_revision=design['team_revision'],candidate_ids=C.universe.IQ_COMPANY_ID.tolist(),candidate_count=len(C.universe),
      source_cleaning='Edit only specified page body blocks; retain title/meta and all other pages; no upstream scraper cleaner rerun.',
      postprocessing='Same team build_prompt/name masking/global word cap, double masking, sentence split and original global shared-sentence/boilerplate filters for both arms.',
      shared_sentence_sha256=digest_text(json.dumps(shared,ensure_ascii=False)),shared_sentence_count=len(shared),
      tfidf='Refit exact original-corpus vectorizer; verify numerical equality with cached matrix; frozen vocabulary/IDF for all variants.',
      mpnet='Pinned cached model, CPU query encoding, original 200-word normalized-chunk mean and company normalization; candidate matrix unchanged.',
      mpnet_revision='e8c3b32edf5434bc2275fc9bab85f82640a19130',
      metrics=['query cosine original-vs-variant','query cosine original-vs-core','candidate score delta','top5 IDs/tickers','top5 overlap and Jaccard','mean/max absolute rank shift among finite candidate scores'],
      ranking='Exclude self; descending finite score, ascending company ID for ties; fixed original 534-company universe.',
      rigel='Separate live-vs-captured acquisition probe; no original-date assertion or synthetic ranking enrichment.',
      exclusions='No financial files/columns/outcomes; no relevance labels; no accuracy or winner claim.',
      interpretation='Post-audit diagnostic chosen because source defects were observed; not a preregistered relevance benchmark.')
    write(CONFIG,freeze)
    print(json.dumps({'stage':'prepared','cases':len(inputs),'originals_exact_baseline':sum(x['original_matches_frozen_baseline'] for x in inputs),'input_sha256':freeze['frozen_input_sha256']},indent=2),flush=True)

def find_cache(method,ids,params):
    matches=[]
    for path in (OUT/'feature-cache').glob(method+'_*/metadata.json'):
        meta=json.loads(path.read_text(encoding='utf-8'))
        if meta.get('method_id')==method and meta.get('ids')==ids and meta.get('parameters')==params:
            matches.append((path.parent,meta))
    if len(matches)!=1:
        raise RuntimeError(f'Expected one completed frozen {method} cache; found {len(matches)}. Run core first.')
    return matches[0]

def rank(ids,scores,target):
    import numpy as np
    valid=[(cid,float(score)) for cid,score in zip(ids,scores) if cid!=target and np.isfinite(score)]
    return sorted(valid,key=lambda x:(-x[1],x[0]))

def run():
    import numpy as np
    import pandas as pd
    from scipy import sparse
    from sklearn.feature_extraction.text import TfidfVectorizer, ENGLISH_STOP_WORDS
    from sentence_transformers import SentenceTransformer
    from huggingface_hub import hf_hub_download
    import modular_validation.features as features
    os.environ['HF_HUB_OFFLINE']='1'
    os.environ['TRANSFORMERS_OFFLINE']='1'
    freeze=json.loads(CONFIG.read_text(encoding='utf-8'))
    assert file_sha(INPUT)==freeze['frozen_input_sha256']
    assert file_sha(OUT/'design_freeze.json')==freeze['design_sha256']
    assert file_sha(OUT/'evidence_perturbation_fixtures.json')==freeze['fixtures_sha256']
    inp=json.loads(INPUT.read_text(encoding='utf-8'))
    design,C=load(); B=C.team_baseline
    ids=C.universe.IQ_COMPANY_ID.tolist()
    assert ids==freeze['candidate_ids'] and len(ids)==534
    params=json.loads((ROOT/'config/modular_validation_parameters.json').read_text(encoding='utf-8'))
    caches={m:find_cache(m,ids,params) for m in freeze['methods']}
    tf_folder,tf_meta=caches['team_tfidf']
    mp_folder,mp_meta=caches['team_mpnet_cosine']
    TF=sparse.load_npz(tf_folder/'matrix.npz')
    MP=np.load(mp_folder/'matrix.npy',allow_pickle=False)
    vectorizer=TfidfVectorizer(stop_words=list(ENGLISH_STOP_WORDS | B.EXTRA_STOP),ngram_range=(1,2),
        min_df=2,max_df=0.4,sublinear_tf=True,token_pattern=r'(?u)\b[a-zA-Z][a-zA-Z]+(?:-[a-zA-Z]+)*\b')
    fitted=vectorizer.fit_transform(C.universe.clean_text)
    d=fitted-TF
    tf_error=float(np.max(np.abs(d.data))) if d.nnz else 0.0
    assert fitted.shape==TF.shape and tf_error<1e-12,tf_error
    model_dir=str(Path(hf_hub_download(features.MPNET_ID,'model.safetensors',revision=features.MPNET_REVISION,
                                     local_files_only=True,token=False)).parent)
    # Local process override only, not a core-module change or cache rewrite.
    features._ENCODER=SentenceTransformer(model_dir,device='cpu',local_files_only=True,trust_remote_code=False)
    import torch
    torch.set_num_threads(min(8,os.cpu_count() or 1))
    texts=[case[arm]['clean_text'] for case in inp['cases'] for arm in ('original','variant')]
    query_mp,mp_diag=features._encode_groups(texts)
    query_tf=vectorizer.transform(texts)
    tickers=dict(zip(C.companies.IQ_COMPANY_ID,C.companies.target_ciq_ticker))
    index={cid:i for i,cid in enumerate(ids)}
    results=[]
    for ci,case in enumerate(inp['cases']):
        for method,M,Q,meta in [('team_tfidf',TF,query_tf,tf_meta),('team_mpnet_cosine',MP,query_mp,mp_meta)]:
            original,variant=Q[ci*2],Q[ci*2+1]
            def dot(a,b):
                v=a@b.T
                return float(v.toarray().ravel()[0] if sparse.issparse(v) else np.asarray(v).ravel()[0])
            def scores(q):
                v=M@q.T
                out=np.asarray(v.toarray() if sparse.issparse(v) else v).ravel().astype(float)
                out[~np.asarray(meta['valid_rows'],dtype=bool)]=np.nan
                return out
            a,b=scores(original),scores(variant)
            ra,rb=rank(ids,a,case['company_id']),rank(ids,b,case['company_id'])
            rka={cid:i+1 for i,(cid,_) in enumerate(ra)};rkb={cid:i+1 for i,(cid,_) in enumerate(rb)}
            common=set(rka)&set(rkb)
            shifts=[abs(rka[c]-rkb[c]) for c in common]
            ta,tb=[c for c,_ in ra[:5]],[c for c,_ in rb[:5]]
            overlap=len(set(ta)&set(tb));union=len(set(ta)|set(tb))
            comparable=np.isfinite(a)&np.isfinite(b)&(np.asarray(ids)!=case['company_id'])
            deltas=np.abs(a[comparable]-b[comparable])
            result=dict(fixture_id=case['fixture_id'],company_id=case['company_id'],ticker=case['ticker'],method=method,
              original_text_sha256=case['original_text_sha256'],variant_text_sha256=case['variant_text_sha256'],
              original_matches_frozen_baseline=case['original_matches_frozen_baseline'],
              original_vector_cosine_to_core=dot(original,M[index[case['company_id']]]),
              original_variant_vector_cosine=dot(original,variant),
              target_text_changed=case['original']['clean_text']!=case['variant']['clean_text'],
              source_change=case['source_change'],
              original_word_count=len(case['original']['clean_text'].split()),variant_word_count=len(case['variant']['clean_text'].split()),
              added_sentence_set=sorted(set(case['variant']['kept_sentences'])-set(case['original']['kept_sentences'])),
              removed_sentence_set=sorted(set(case['original']['kept_sentences'])-set(case['variant']['kept_sentences'])),
              top5_original=[dict(company_id=c,ticker=tickers[c],score=s) for c,s in ra[:5]],
              top5_variant=[dict(company_id=c,ticker=tickers[c],score=s) for c,s in rb[:5]],
              top5_overlap_count=overlap,top5_jaccard=overlap/union if union else None,
              top5_order_unchanged=ta==tb,finite_candidate_count=len(ra),
              mean_absolute_score_change=float(np.mean(deltas)),max_absolute_score_change=float(np.max(deltas)),
              mean_absolute_rank_shift=float(np.mean(shifts)),max_absolute_rank_shift=max(shifts),
              inference='Representation/ranking sensitivity only; no ground-truth accuracy, causal or valuation inference.')
            results.append(result)
            print(case['ticker'],method,'cosine',round(result['original_variant_vector_cosine'],6),'overlap',overlap,flush=True)
    report=dict(created_at_utc=datetime.now(timezone.utc).isoformat(),config_sha256=file_sha(CONFIG),
      frozen_inputs_sha256=file_sha(INPUT),runner_current_sha256=file_sha(__file__),
      source_adapter_sha256=file_sha(ROOT/'src/modular_validation/data.py'),feature_module_sha256=file_sha(ROOT/'src/modular_validation/features.py'),
      cache_provenance={m:dict(path=str(p),cache_key=meta['cache_key'],metadata_sha256=file_sha(p/'metadata.json'),
          matrix_sha256=file_sha(p/('matrix.npz' if meta['sparse'] else 'matrix.npy'))) for m,(p,meta) in caches.items()},
      tfidf_refit_max_absolute_error=tf_error,mpnet_query_device='cpu',mpnet_query_diagnostics=mp_diag,
      financial_outcomes_used=False,core_cache_modified=False,assessment_origin='AGENT',human_relevance_labels_used=False,
      results=results,acquisition_diagnostic=inp['acquisition_diagnostic'],
      caveats=['Source defects selected before any current rankings were viewed; perturbation choice remains exploratory.',
       'Candidate representations and membership never change; IDF and boilerplate rules remain frozen.',
       'Restored source facts are retained through identical postprocessing, not rerun through the defective upstream cleaner.',
       'XERS only removes one page occurrence; remaining duplicates and global prompt budget can change downstream page retention.',
       'RIGL is a separate live-source acquisition diagnostic; no corrected ranking or October 17 reconstruction is claimed.',
       'CPU/GPU numerical differences can affect exact ties; original-to-core cosine is recorded.'])
    write(OUT/'perturbation_results.json',report)
    flat=[{k:r[k] for k in ['fixture_id','ticker','method','original_matches_frozen_baseline','target_text_changed',
       'original_vector_cosine_to_core','original_variant_vector_cosine','original_word_count','variant_word_count',
       'top5_overlap_count','top5_jaccard','top5_order_unchanged','finite_candidate_count','mean_absolute_score_change',
       'max_absolute_score_change','mean_absolute_rank_shift','max_absolute_rank_shift']} for r in results]
    pd.DataFrame(flat).to_csv(OUT/'perturbation_results.csv',index=False)
    print('PERTURBATIONS_COMPLETE',len(results),'paired method results plus RIGL acquisition diagnostic',flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['prepare','run']);args=parser.parse_args()
    prepare() if args.stage=='prepare' else run()
