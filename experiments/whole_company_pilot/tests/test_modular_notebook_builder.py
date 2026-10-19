"""One-file notebook smoke test using only fictitious company inputs."""
from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
import zipfile

import nbformat
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("notebook_builder_test",
                                           ROOT / "scripts/build_modular_validation_notebook.py")
BUILDER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BUILDER)


def synthetic_archive():
    """No source snapshot, website output or real financial data is read."""
    prefix = "project/outputs-local/modular-validation/"
    files = {}

    def add_json(name, value):
        files[name] = json.dumps(value).encode()

    def add_csv(name, rows):
        files[name] = pd.DataFrame(rows).to_csv(index=False).encode()

    ids = [f"TEST{i}" for i in range(7)]
    tickers = ["PCTY"] + [f"FAKE{i}" for i in range(1, 7)]
    companies = [dict(IQ_COMPANY_ID=cid, target_ciq_ticker=tickers[i],
                      target_company_name=f"Fictitious Company {i}",
                      target_ciq_website=f"https://example.com/{i}",
                      target_sic4_code="1111" if i % 2 == 0 else "2222",
                      target_ebitda=10+i, target_ev_to_ebitda=5+i)
                 for i, cid in enumerate(ids)]
    targets = [{**companies[i], "role":role, "inclusion_probability":.2}
               for i, role in [(0, "development"), (1, "fresh_pilot")]]
    # A private target can be valued without an observed valuation outcome.
    companies[1]["target_ev_to_ebitda"] = None
    methods = ["team_mpnet_cosine", "balanced_activity_ot"]
    add_json(prefix+"design_freeze.json",
             dict(targets=targets, team_revision="synthetic-only",
                  snapshot_sha256="synthetic-only", frozen_at_utc="2026-10-18",
                  selection_rule="Fictitious test fixture only.", methods_predeclared=methods))
    add_json("project/config/modular_validation_parameters.json", {"blocked_comparisons":{}})
    add_csv("team/data-local/snapshots/company_list_v3_websites_fixed.csv", companies)
    add_csv(prefix+"core/company_identifiers.csv", companies)
    add_csv(prefix+"core/text_coverage.csv",
            [dict(IQ_COMPANY_ID=cid, clean_words=100+i*10) for i,cid in enumerate(ids)])
    rank_rows=[]
    for target in targets:
        for method in methods:
            candidates=[c for c in ids if c != target["IQ_COMPANY_ID"]]
            if method != methods[0]:
                candidates.reverse()
            for rank,candidate in enumerate(candidates, 1):
                rank_rows.append(dict(target_id=target["IQ_COMPANY_ID"], candidate_id=candidate,
                                      method=method, score=1/rank, available=True, rank=rank))
    add_csv(prefix+"core/rankings.csv", rank_rows)
    ranking_hash=hashlib.sha256(files[prefix+"core/rankings.csv"]).hexdigest()
    # Exercise Windows path normalization as well as the Linux-style archive keys.
    add_json(prefix+"evaluation/all_rankings_freeze.json",
             dict(ranking_inputs={"core\\rankings.csv":ranking_hash}, frozen_at_utc="2026-10-18"))
    add_json(prefix+"evaluation/evaluation_status.json", {"independent_human_labels_new":0})
    add_csv(prefix+"evaluation/blind_human_review.csv",
            [dict(pair_id=f"{t['IQ_COMPANY_ID']}-{cid}", target_id=t["IQ_COMPANY_ID"],
                  candidate_id=cid, target=t["target_ciq_ticker"], candidate=tickers[ids.index(cid)],
                  target_url=t["target_ciq_website"], candidate_url=f"https://example.com/{cid}",
                  reviewer_name="", whole_company_grade="")
             for t in targets for cid in ids if cid != t["IQ_COMPANY_ID"]])
    files["team/scraps/comps_first_pass/peer_labels.csv"] = (
        "# Fictitious test labels; not actual PCTY evidence.\n"
        "target,peer,grade,labeled_by,note\n"
        "PCTY,FAKE1,2,TEST_REVIEWER,synthetic\n"
        "PCTY,FAKE3,1,TEST_REVIEWER,synthetic\n"
        "PCTY,OUTSIDE_UNIVERSE,1,TEST_REVIEWER,synthetic\n").encode()
    profile_map={cid:dict(company_id=cid, config_hash="synthetic-config",
                         known_activities=[dict(activity=f"Fictitious activity {i}", role="vendor",
                                                source_id=cid+":P1", quote="Fictitious supported source span only.",
                                                facets={})],
                         rejected_activities=[], status="synthetic",
                         generation={"input_truncated":False,"output_hit_limit":False})
                 for i,cid in enumerate(ids)}
    # A retained activity must not bypass the whole-company truncation guard.
    profile_map['TEST6']['generation']['output_hit_limit']=True
    path=prefix+"profile-cache/synthetic/all_profiles_validated.json"
    add_json(path,profile_map)
    add_json(prefix+"profiles/run_freeze.json",
             {"profile_map_sha256":hashlib.sha256(files[path]).hexdigest()})
    for i,cid in enumerate(ids):
        add_json(f"team/outputs-local/website_scrape/page_text/{cid}.json",
                 dict(IQ_COMPANY_ID=cid,pages=[dict(page_id="P1",url=f"https://example.com/{i}",
                     fetched_at='2026-10-18',raw_blocks=['Fictitious supported source span only.'])]))
    pure_modules=("numeric","evaluation","evidence_policy","experiment_comparison")
    for name in pure_modules:
        files[f"project/src/modular_validation/{name}.py"]=(ROOT/f"src/modular_validation/{name}.py").read_bytes()
    for name in ('evaluate_modular_validation.py','run_direct_valuation.py'):
        files['project/scripts/'+name]=(ROOT/'scripts'/name).read_bytes()
    add_json(prefix+'evaluation/all_rankings_freeze.json',{
        'ranking_inputs':{'core\\rankings.csv':ranking_hash},'frozen_at_utc':'2026-10-18',
        'design_sha256':hashlib.sha256(files[prefix+'design_freeze.json']).hexdigest(),
        'parameter_sha256':hashlib.sha256(files['project/config/modular_validation_parameters.json']).hexdigest(),
        'evaluation_script_sha256':hashlib.sha256(files['project/scripts/evaluate_modular_validation.py']).hexdigest(),
        'direct_valuation_script_sha256':hashlib.sha256(files['project/scripts/run_direct_valuation.py']).hexdigest(),
        'module_sha256':{name+'.py':hashlib.sha256(files['project/src/modular_validation/'+name+'.py']).hexdigest()
                         for name in pure_modules}})
    add_json(prefix+'ic_case_reviews_software.json',{
        'independent_human_labels':0,'ranking_sha256':ranking_hash,
        'companies':{cid:{'name':f'Fictitious {cid}',
            'observed_business_scope':[{'activity':'Synthetic business activity'}],
            'scope_unknowns':['Synthetic scope is not evidence about any company.'],
            'source_records':[{'evidence_id':cid+':P1:0','quote':'Fictitious supported source span only.',
                'url':f'https://example.com/{ids.index(cid)}','fetched_at':'2026-10-18','page_id':'P1',
                'raw_block_index':0,'source_field':'raw_blocks','source_json_sha256':hashlib.sha256(
                    files[f'team/outputs-local/website_scrape/page_text/{cid}.json']).hexdigest()}]} for cid in ['TEST0','TEST1']},
        'pairs':[{'target_id':'TEST0','candidate_id':'TEST1','baseline_rank':1,
            'agent_provisional':True,'human_approved':False,
            'committee_rationale':'Synthetic provisional analysis; not a human label.',
            'overlap_claims':[{'claim':'Synthetic overlap','target_evidence_ids':['TEST0:P1:0'],
                               'candidate_evidence_ids':['TEST1:P1:0']}],
            'material_mismatches':[{'claim':'Synthetic difference'}],
            'unknowns':['Synthetic unknown'],'review_questions':['Synthetic question?']}]})
    files["requirements-embedded.txt"]=b"# Synthetic test environment.\n"
    manifest={"created_at_utc":"2026-10-18","files":{
        name:{"sha256":hashlib.sha256(data).hexdigest(),"bytes":len(data)} for name,data in files.items()}}
    add_json("payload_manifest.json",manifest)
    buffer=io.BytesIO()
    with zipfile.ZipFile(buffer,"w",zipfile.ZIP_DEFLATED) as archive:
        for name,data in files.items():
            archive.writestr(name,data)
    return buffer.getvalue(),manifest


def synthetic_pilot_archive():
    """A smaller pool with a separate original-global hash and local parameters."""
    packed,_=synthetic_archive()
    old='project/outputs-local/modular-validation/'
    prefix='project/outputs-local/fictitious-pilot/'
    with zipfile.ZipFile(io.BytesIO(packed)) as archive:
        files={name.replace(old,prefix,1) if name.startswith(old) else name:archive.read(name)
               for name in archive.namelist() if name!='payload_manifest.json'}
    def put(name,value):files[name]=json.dumps(value).encode()
    ids=[f'TEST{i}' for i in range(6)]
    for name in ['rankings.csv','text_coverage.csv','company_identifiers.csv']:
        path=prefix+'core/'+name
        files[prefix+'global-controls/core/'+name]=files[path]
        frame=pd.read_csv(io.BytesIO(files[path]))
        frame=frame[frame['candidate_id' if name=='rankings.csv' else 'IQ_COMPANY_ID'].isin(ids)].copy()
        if name=='rankings.csv':
            frame['rank']=frame.groupby(['target_id','method'])['rank'].rank(method='first')
        files[path]=frame.to_csv(index=False).encode()
    pool={'version':'synthetic-pilot','company_ids':ids,
          'original_core_rankings_sha256':hashlib.sha256(files[prefix+'global-controls/core/rankings.csv']).hexdigest(),
          'evaluation_scope':'Synthetic restricted-pool fixture only.'}
    put(prefix+'candidate_pool_freeze.json',pool)
    design=json.loads(files[prefix+'design_freeze.json'])
    design.update(pilot_company_ids=ids,candidate_pool_sha256=hashlib.sha256(files[prefix+'candidate_pool_freeze.json']).hexdigest())
    put(prefix+'design_freeze.json',design)
    put(prefix+'parameters.json',{'blocked_comparisons':{},'version':'fictitious-pilot-parameters'})
    profile=prefix+'profile-cache/synthetic/all_profiles_validated.json'
    put(profile,{cid:record for cid,record in json.loads(files[profile]).items() if cid in ids})
    put(prefix+'profiles/run_freeze.json',{'profile_map_sha256':hashlib.sha256(files[profile]).hexdigest()})
    seal=json.loads(files[prefix+'evaluation/all_rankings_freeze.json'])
    seal.update(ranking_inputs={'core/rankings.csv':hashlib.sha256(files[prefix+'core/rankings.csv']).hexdigest()},
                design_sha256=hashlib.sha256(files[prefix+'design_freeze.json']).hexdigest(),
                parameter_sha256=hashlib.sha256(files[prefix+'parameters.json']).hexdigest())
    put(prefix+'evaluation/all_rankings_freeze.json',seal)
    manifest={'created_at_utc':'2026-10-18','experiment_prefix':prefix,
              'parameter_archive_path':prefix+'parameters.json',
              'files':{name:{'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data)} for name,data in files.items()}}
    put('payload_manifest.json',manifest)
    buffer=io.BytesIO()
    with zipfile.ZipFile(buffer,'w',zipfile.ZIP_DEFLATED) as archive:
        for name,data in files.items():archive.writestr(name,data)
    return buffer.getvalue(),manifest


class NotebookBuilderTests(unittest.TestCase):
    def test_pilot_scope_local_parameters_and_global_review_provenance(self):
        original=BUILDER.collect_payload
        BUILDER.collect_payload=synthetic_pilot_archive
        try:
            with tempfile.TemporaryDirectory(prefix='synthetic-pilot-notebook-',dir=ROOT/'outputs-local/modular-validation') as tmp:
                path=Path(tmp)/'pilot.ipynb'
                with contextlib.redirect_stdout(io.StringIO()):BUILDER.build(path)
                notebook=nbformat.read(path,as_version=4)
                env={}
                with contextlib.redirect_stdout(io.StringIO()):
                    for index,cell in enumerate(notebook.cells):
                        if cell.cell_type!='code':continue
                        exec(compile(cell.source,f'synthetic-pilot-cell-{index}','exec'),env)
                        if 'display' in env:env['display']=lambda *a,**k:None
                        if 'plt' in env:env['plt'].show=lambda:None
                self.assertEqual(env['PREFIX'],'project/outputs-local/fictitious-pilot/')
                self.assertEqual(env['params']['version'],'fictitious-pilot-parameters')
                self.assertEqual(len(env['eligible_ids']),7)
                self.assertEqual(len(env['comparison_ids']),6)
                self.assertEqual(len(env['global_controls']),24)
                self.assertEqual(len(env['rankings']),20)
                self.assertEqual(len(env['profiles']),6)
                self.assertEqual(env['ic_literal_quote_checks'],2)
                self.assertTrue(env['seal_verification']['verified'])
                self.assertEqual(len(env['configuration_results']),18)
                self.assertEqual(len(env['configuration_sensitivity']),18)
                self.assertEqual(set(env['rankings'].candidate_id),set(env['comparison_ids']))
                exported=env['export_workspace'](Path(tmp)/'exported-pilot')
                new_out=exported/'rerun-project/outputs-local/modular-validation'
                self.assertTrue((new_out/'candidate_pool_freeze.json').exists())
                self.assertEqual(json.loads((new_out/'parameters.json').read_text())['version'],'fictitious-pilot-parameters')
                preview=subprocess.run([sys.executable,str(exported/'rerun-project/rerun_workflow.py')],cwd=tmp,capture_output=True,text=True,check=True)
                self.assertIn('fixed-pool restriction',preview.stdout)
                self.assertFalse((new_out/'evaluation').exists())
        finally:
            BUILDER.collect_payload=original
            import matplotlib.pyplot as plt
            plt.close('all')

    def test_all_evidence_cards_and_offline_recalculation(self):
        cards=BUILDER.research_cards()
        self.assertEqual([int(v) for v in re.findall(r"^### E(\d+)\.",cards,re.M)],list(range(1,22)))
        import matplotlib
        matplotlib.use("Agg")
        original=BUILDER.collect_payload
        BUILDER.collect_payload=synthetic_archive
        try:
            with tempfile.TemporaryDirectory(prefix="synthetic-notebook-check-",dir=ROOT/"outputs-local/modular-validation") as tmp:
                path=Path(tmp)/"test.ipynb"
                with contextlib.redirect_stdout(io.StringIO()):
                    BUILDER.build(path)
                notebook=nbformat.read(path,as_version=4)
                env={}
                count=0
                with contextlib.redirect_stdout(io.StringIO()):
                    for cell in notebook.cells:
                        if cell.cell_type!="code":
                            continue
                        exec(compile(cell.source,f"synthetic-notebook-cell-{count}","exec"),env)
                        if "display" in env:
                            env["display"]=lambda *args,**kwargs:None
                        if "plt" in env:
                            env["plt"].show=lambda:None
                        count+=1
                self.assertGreaterEqual(count,14)
                self.assertEqual(len(env["valuation"]),2*2*3*3)
                self.assertEqual(env["human_labels_new"],0)
                self.assertEqual(len(env["profiles"]),7)
                self.assertFalse(env['source_support']['TEST6'])
                self.assertEqual(len(env['ic_reviews']),1)
                self.assertEqual(env['ic_literal_quote_checks'],2)
                self.assertTrue(env['seal_verification']['verified'])
                self.assertEqual(len(env['configuration_results']),18)
                self.assertEqual(len(env['configuration_sensitivity']),18)
                fresh=env["valuation"][env["valuation"].target_id.eq("TEST1")]
                self.assertTrue(fresh.estimated_ev_supplied_millions.notna().all())
                self.assertTrue(fresh.snapshot_ape.isna().all())
                self.assertTrue(fresh.strict_indication_status.eq('withheld').all())
                self.assertFalse(env["EXPORT_WORKSPACE"])
                self.assertEqual(len(env["historical_recomputed"]),2)
                row=env["historical_recomputed"].iloc[0]
                self.assertTrue(pd.isna(row["unknown_default_precision_at5"]))
                self.assertGreater(row["legacy_closed_world_ndcg_at10"],0)
                self.assertLess(row["legacy_closed_world_ndcg_at10"],1)
                self.assertEqual({p.name for p in Path(tmp).iterdir()},{"test.ipynb"},
                                 "Default Run All must not create companion files")
                exported=env["export_workspace"](Path(tmp)/"portable-export")
                rerun=exported/"rerun-project"
                relocated=json.loads((rerun/"outputs-local/modular-validation/design_freeze.json").read_text())
                self.assertEqual(Path(relocated["team_root"]),exported/"team")
                self.assertFalse((rerun/"outputs-local/modular-validation/evaluation").exists())
                self.assertTrue((exported/"project/outputs-local/modular-validation/evaluation/all_rankings_freeze.json").exists())
                preview=subprocess.run([sys.executable,str(rerun/"rerun_workflow.py")],
                                       cwd=tmp,capture_output=True,text=True,check=True)
                self.assertIn("Dry plan only",preview.stdout)
                with self.assertRaises(FileExistsError):
                    env["export_workspace"](exported)
        finally:
            BUILDER.collect_payload=original
            import matplotlib.pyplot as plt
            plt.close("all")


if __name__=="__main__":
    unittest.main()
