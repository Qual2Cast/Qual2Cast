"""Package sealed company experiments as a self-contained English notebook.

Run only after the coordinator freezes all rankings and authorizes outcome access.
The builder refuses an absent/stale ranking seal before reading the snapshot.
Default notebook execution uses embedded inference outputs, recalculates analysis,
and makes no network calls or file writes. Heavy inference is separately optional.
"""
from __future__ import annotations

import argparse
import ast
import base64
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import io
import json
import os
from pathlib import Path
import re
import textwrap
import zipfile

import nbformat

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EXPERIMENT = ROOT / "outputs-local/modular-validation"
OUT = Path(os.environ.get("QUAL2CAST_EXPERIMENT_DIR", DEFAULT_EXPERIMENT))
if not OUT.is_absolute():
    OUT = ROOT / OUT
DEFAULT_DESTINATION = Path(r"C:\Users\13156\ChatGPT-Local-Deliveries\Rational-AI-2026-10-18\Modular_Company_Validation.ipynb")


def parameter_path():
    """Use the active experiment contract, preserving the legacy fallback."""
    local = OUT / "parameters.json"
    return local if local.exists() else ROOT / "config/modular_validation_parameters.json"


def experiment_prefix():
    """Archive paths preserve the experiment version and never mix its rankings."""
    if not OUT.resolve().is_relative_to(ROOT.resolve()):
        raise ValueError("The experiment directory must be inside this project")
    return "project/" + OUT.resolve().relative_to(ROOT.resolve()).as_posix() + "/"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def safe_files(directory: Path):
    """Enumerate only the requested tree, pruning links/junctions before descent."""
    if not directory.exists():
        return
    root = directory.resolve()
    if directory.is_symlink() or getattr(directory, "is_junction", lambda: False)():
        raise ValueError(f"Linked collection root refused: {directory}")
    for current, dirs, files in os.walk(directory, followlinks=False):
        dirs[:] = sorted(d for d in dirs if d != "__pycache__" and
                         not (Path(current) / d).is_symlink() and
                         not getattr(Path(current) / d, "is_junction", lambda: False)())
        for name in sorted(files):
            path = Path(current) / name
            if path.is_symlink() or not path.resolve().is_relative_to(root):
                continue
            yield path


def check_seal():
    seal_path = OUT / "evaluation/all_rankings_freeze.json"
    if not seal_path.exists():
        raise RuntimeError("All-rankings freeze is required before packaging any outcome data")
    seal = json.loads(seal_path.read_text(encoding="utf-8"))
    if not seal.get("ranking_inputs"):
        raise RuntimeError("Ranking freeze has no input hashes")
    for rel, expected in seal["ranking_inputs"].items():
        path = (OUT / rel).resolve()
        if not path.is_relative_to(OUT.resolve()) or sha(path.read_bytes()) != expected:
            raise RuntimeError(f"Ranking freeze mismatch: {rel}")
    for name in ("core", "profiles", "llm", "llm-protocol-v2", "factors"):
        path = OUT / name / "rankings.csv"
        if path.exists() and path.relative_to(OUT).as_posix() not in {
                str(key).replace("\\", "/") for key in seal["ranking_inputs"]}:
            raise RuntimeError(f"Unsealed ranking artifact: {path}")
    if sha((OUT / "design_freeze.json").read_bytes()) != seal["design_sha256"]:
        raise RuntimeError("Design changed after all-rankings freeze")
    if sha(parameter_path().read_bytes()) != seal["parameter_sha256"]:
        raise RuntimeError("Parameters changed after all-rankings freeze")
    for key, name in [('evaluation_script_sha256', 'evaluate_modular_validation.py'),
                      ('direct_valuation_script_sha256', 'run_direct_valuation.py')]:
        if seal.get(key) != sha((ROOT / 'scripts' / name).read_bytes()):
            raise RuntimeError('Evaluator code changed or proof absent: ' + name)
    modules = {p.name: sha(p.read_bytes()) for p in sorted((ROOT / 'src/modular_validation').glob('*.py'))}
    if seal.get('module_sha256') != modules:
        raise RuntimeError('Method/evaluation module code changed or proof absent')
    if not (OUT / "evaluation/evaluation_status.json").exists():
        raise RuntimeError("Evaluation completion record is required")
    return seal


def collect_payload():
    seal = check_seal()  # MUST precede reading full financial snapshot.
    design = json.loads((OUT / "design_freeze.json").read_text(encoding="utf-8"))
    prefix = experiment_prefix()
    pool_path = OUT / "candidate_pool_freeze.json"
    if design.get("pilot_company_ids"):
        if not pool_path.exists() or sha(pool_path.read_bytes()) != design.get("candidate_pool_sha256"):
            raise RuntimeError("Pilot candidate-pool freeze is absent or changed")
        pool = json.loads(pool_path.read_text(encoding="utf-8"))
        if set(pool["company_ids"]) != set(design["pilot_company_ids"]):
            raise RuntimeError("Pilot design/pool membership mismatch")
    team = Path(design["team_root"]).resolve(strict=True)
    snapshot = team / "data-local/snapshots/company_list_v3_websites_fixed.csv"
    if sha(snapshot.read_bytes()) != design["snapshot_sha256"]:
        raise RuntimeError("Snapshot differs from target-selection freeze")
    files = {}

    def add(path, name):
        if not path.is_file() or path.is_symlink():
            return
        if name in files:
            raise RuntimeError(f"Duplicate archive key: {name}")
        files[name] = path.read_bytes()

    add(snapshot, "team/data-local/snapshots/company_list_v3_websites_fixed.csv")
    add(team / "data_manifest.json", "team/data_manifest.json")
    add(team / "docs/data_dictionary.md", "team/docs/data_dictionary.md")
    add(team / "scraps/comps_first_pass/peer_labels.csv",
        "team/scraps/comps_first_pass/peer_labels.csv")
    for path in safe_files(team / "outputs-local/website_scrape/page_text"):
        if path.suffix == ".json":
            add(path, "team/" + path.relative_to(team).as_posix())
    for directory in ("src", "website_scrape", "scraps/codex_profiles", "scraps/comps_first_pass"):
        for path in safe_files(team / directory):
            if path.suffix in (".py", ".json", ".txt") and path.stat().st_size < 2_000_000:
                add(path, "team/" + path.relative_to(team).as_posix())
    for path in safe_files(OUT):
        if any(part in {'test-work', '__pycache__', 'delivery-drafts', 'github-ready', 'final-publication-drafts'} for part in path.relative_to(OUT).parts):
            continue
        if path.suffix.lower() in (".csv", ".json", ".jsonl", ".txt", ".npy", ".npz") or (
                path.suffix.lower() == ".html" and any(path.is_relative_to(OUT / part)
                    for part in ('live-cleaning-diagnostic', 'growth-integration/captures'))):
            add(path, "project/" + path.relative_to(ROOT).as_posix())
    # Default reanalysis needs saved rankings, not the recomputable 534-company
    # feature arrays. Active pilot arrays remain embedded through OUT above.
    # A pilot can reuse immutable first-pass records outside its output tree.
    # Preserve those exact bytes too, so every canonical-map lineage hash can be
    # independently checked after downloading this one file.
    raw_profile_index={}
    for validation_path in (OUT/'profile-cache').glob('*/validation_manifest.json'):
        validation=json.loads(validation_path.read_text(encoding='utf-8'))
        for label,paths_key,hashes_key in [
                ('first_pass','first_pass_input_paths','first_pass_input_file_sha256'),
                ('selected','input_paths','input_file_sha256')]:
            entries={}
            for cid,source_path in validation.get(paths_key,{}).items():
                source=Path(source_path).resolve(strict=True)
                expected=validation[hashes_key][cid]
                if not source.is_relative_to(ROOT.resolve()) or sha(source.read_bytes())!=expected:
                    raise ValueError('Raw profile provenance mismatch: '+cid)
                archive_name='project/raw-profile-inputs/'+expected+'.json'
                if archive_name not in files:add(source,archive_name)
                entries[cid]={'path':archive_name,'sha256':expected}
            raw_profile_index[label]=entries
    if raw_profile_index:
        files['project/raw-profile-inputs/index.json']=json.dumps(raw_profile_index,indent=2).encode()
    growth_manifest_path = OUT / 'growth-integration/required_source_manifest.json'
    if growth_manifest_path.exists():
        growth_manifest = json.loads(growth_manifest_path.read_text(encoding='utf-8'))
        growth_root = Path(growth_manifest['team_root']).resolve(strict=True)
        upstream_manifest = json.loads((growth_root / 'SOURCE_MANIFEST.json').read_text(encoding='utf-8'))
        if upstream_manifest['commit'] != growth_manifest['team_revision']:
            raise ValueError('Growth source revision conflict')
        selected = dict(upstream_manifest['files'])
        for row in growth_manifest['required_files'] + growth_manifest.get('test_source_files', []):
            rel = row['relative_path'].replace('\\', '/')
            if rel in selected and selected[rel] != row['sha256']:
                raise ValueError('Conflicting growth source hash: ' + rel)
            selected[rel] = row['sha256']
        for rel, expected in selected.items():
            path = (growth_root / rel).resolve(strict=True)
            if not path.is_relative_to(growth_root) or sha(path.read_bytes()) != expected:
                raise ValueError('Growth source hash mismatch: ' + rel)
            add(path, 'team-growth/' + rel)
    software_builder = OUT / '_build_ic_software_reviews.py'
    if not software_builder.exists():
        software_builder = DEFAULT_EXPERIMENT / '_build_ic_software_reviews.py'
    add(software_builder, prefix + '_build_ic_software_reviews.py')
    for path in safe_files(ROOT / "src/modular_validation"):
        if path.suffix == ".py":
            add(path, "project/" + path.relative_to(ROOT).as_posix())
    scripts = ["run_modular_validation.py", "evaluate_modular_validation.py",
               "run_direct_valuation.py", "freeze_modular_design.py",
               "check_modular_runtime.py", "build_modular_validation_notebook.py",
               "run_local_peer_judgments.py", "run_local_peer_judgments_v2.py", "build_local_profiles.py",
               "run_evidence_perturbations.py", "audit_modular_inputs.py",
               "cleaning_diagnostic.py", "build_growth_readiness.py",
               "validate_local_profiles.py", "integrate_team_growth.py", "build_health_ic_reviews.py",
               "prepare_pilot_v2.py", "run_factor_ablation.py", "build_experiment_comparison.py",
               "audit_pilot_pool.py", "build_delivery_figures.py", "run_agent_assessment.py",
               "execute_pilot_stage.py", "prepare_profile_repairs.py", "gentle_run.py", "gentle_process_start.py", "validate_modular_notebook.py"]
    # Include later experiment runners without importing/executing them.
    scripts += [p.name for p in (ROOT / "scripts").glob("*modular*.py")]
    scripts += [p.name for p in (ROOT / "scripts").glob("*factor*.py")]
    scripts += [p.name for p in (ROOT / "scripts").glob("*comparison*.py")]
    for name in sorted(set(scripts)):
        add(ROOT / "scripts" / name, "project/scripts/" + name)
    for path in sorted((ROOT / "tests").glob("test_modular*.py")):
        add(path, "project/tests/" + path.name)
    for name in ("test_growth_readiness.py", "test_profile_validation.py", "test_evidence_policy.py",
                 "test_direct_valuation_safeguards.py", "test_factor_ablation.py",
                 "test_experiment_comparison.py", "test_profile_scope.py", "test_company_scope.py", "test_judgment_protocol.py"):
        add(ROOT / "tests" / name, "project/tests/" + name)
    add(ROOT / "config/modular_validation_parameters.json", "project/config/modular_validation_parameters.json")
    for path in safe_files(ROOT / 'data-local/sources/factor-research-2026-10-18'):
        if path.suffix.lower() in {'.json', '.txt'}:
            add(path, 'project/' + path.relative_to(ROOT).as_posix())
    authority_path = ROOT / 'data-local/sources/aziz-authority-update-2026-10-18.json'
    if authority_path.exists():
        authority_raw = authority_path.read_bytes()
        authority = json.loads(authority_raw)
        # The sendable report needs requirements, not unrelated group names or chat metadata.
        shareable = {key: authority[key] for key in ('observed_date_local', 'observed_timezone',
            'authority', 'requirements', 'scope_boundary') if key in authority}
        shareable['provenance'] = {'local_authority_record_sha256': sha(authority_raw),
            'selection': 'Project requirement summary only; private chat links and teammate updates omitted.'}
        files['project/data-local/sources/aziz-authority-update-2026-10-18.json'] = json.dumps(shareable,indent=2).encode()
    packages = ["numpy", "pandas", "scipy", "matplotlib", "ipython", "nbformat",
                "nbclient", "POT", "scikit-learn", "gensim", "sentence-transformers",
                "transformers", "torch", "accelerate", "huggingface-hub", "psutil",
                "requests", "beautifulsoup4", "lxml", "trafilatura", "readability-lxml"]
    versions = {}
    for package in packages:
        try:
            versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            versions[package] = None
    files["requirements-embedded.txt"] = ("# Observed build environment; heavy inference is optional.\n" +
        "\n".join(f"{name}=={version}" for name, version in versions.items() if version)).encode()
    manifest = {"created_at_utc": datetime.now(timezone.utc).isoformat(),
                "purpose": "Offline reanalysis of sealed real-company experiments",
                "files": {name: {"sha256": sha(data), "bytes": len(data)} for name, data in files.items()},
                "package_versions": versions, "ranking_freeze": seal,
                "experiment_prefix": prefix,
                "experiment_directory": OUT.relative_to(ROOT).as_posix(),
                "parameter_archive_path": "project/" + parameter_path().relative_to(ROOT).as_posix(),
                "candidate_scope": "frozen pilot pool" if design.get('pilot_company_ids') else "full eligible website corpus",
                "optional_recomputable_assets_omitted": ["Original 534-company feature arrays; raw evidence, source code, revisions, metadata and full original rankings retained"] if design.get('pilot_company_ids') else [],
                "contains_model_weights": False, "contains_conversation_history": False,
                "default_execution": "embedded model outputs; metrics and aggregation recomputed",
                "default_network_calls": False, "default_file_writes": False}
    files["payload_manifest.json"] = json.dumps(manifest, indent=2).encode()
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, data in sorted(files.items()):
            archive.writestr(name, data)
    return buffer.getvalue(), manifest


def research_cards():
    source = ROOT / "scripts/build_peer_methods_review.py"
    if not source.exists():
        return "The earlier literature review is not available in this build."
    tree = ast.parse(source.read_text(encoding="utf-8"))
    cards = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "md" and node.args:
            arg = node.args[0]
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                value = textwrap.dedent(arg.value).strip()
                for match in re.finditer(r"(?ms)^### E(\d+)\..*?(?=^#{2,3} |\Z)", value):
                    number = int(match.group(1))
                    if number in cards:
                        raise ValueError(f"Duplicate evidence card E{number}")
                    cards[number] = match.group(0).strip()
    if cards:
        if set(cards) != set(range(1, 22)):
            raise ValueError(f"Expected all 21 evidence cards; found {sorted(cards)}")
        cards[10] = """### E10. Valuation-supervised peer selection: relevant research, unresolved transfer — Grade B

[Frank et al. (August 2026 preprint)](https://arxiv.org/html/2608.12594v1), all BlackRock-affiliated, learn weighted CatBoost leaf co-occurrence from post-money equity valuations. Their 270,000-company universe supplies roughly 53,000 latest-transaction labels and 27 features, predominantly categorical. This is not an EV/EBITDA model. The paper specifies an 80/20 subindustry-stratified split and training-only preprocessing, fitting, weighting and calibration; it does not establish temporal validation. Table 4 reports OLS/CatBoost MAE 1.19/1.08 and RMSE 1.56/1.44, not gains over cosine. Financial Services Figure 4 favors learned proximity; exact plot values were not verified. Structured features versus internal-description embeddings change information as well as method. Latest financials paired with historical deals, percentage-error units and the conformal evaluation denominator need clarification. No public dataset/model release, deployed-product evaluation or independent whole-business peer approval is demonstrated.

Reproduction also needs the exact growth policy: the stated symmetric-tree description and leaf constraints require reconciliation with [CatBoost's parameter documentation](https://catboost.ai/docs/en/references/training-parameters/common#grow_policy). This background review neither changes the frozen experiment nor establishes a local winner."""
        return "\n\n".join(cards[number] for number in sorted(cards))
    return "The earlier literature review could not be extracted; see cited sources in Methods."


def build(destination=DEFAULT_DESTINATION, *, experiment_dir=None):
    if experiment_dir is not None:
        global OUT
        OUT = Path(experiment_dir)
        if not OUT.is_absolute():
            OUT = ROOT / OUT
        OUT = OUT.resolve()
    payload, manifest = collect_payload()
    nb = nbformat.v4.new_notebook()
    nb.metadata.update(kernelspec={"display_name": "Python 3", "language": "python", "name": "python3"},
                       language_info={"name": "python"}, title="Auditable Comparable-Company Valuation",
                       payload_sha256=sha(payload), build_created_at_utc=manifest["created_at_utc"])

    def md(value):
        value = textwrap.dedent(value).strip()
        def anchor(match):
            title=match.group(1)
            if title=='Abstract': key='abstract'
            elif re.match(r'\d+\.',title): key='section-'+title.split('.',1)[0]
            elif title.startswith('Appendix '): key='appendix-'+title.split()[1].rstrip('.').lower()
            else:return match.group(0)
            return '<a id="'+key+'"></a>\n\n'+match.group(0)
        value=re.sub(r'^## (.+)$',anchor,value,flags=re.M)
        nb.cells.append(nbformat.v4.new_markdown_cell(value))

    def code(value, **metadata):
        cell = nbformat.v4.new_code_cell(textwrap.dedent(value).strip())
        cell.metadata.update(tags=['analysis-code', 'hide-input'], jupyter={'source_hidden': True},
                             hide_input=True, collapsed=True)
        cell.metadata.update(metadata)
        nb.cells.append(cell)

    md("""
    # Auditable Comparable-Company Valuation
    ## A private-company valuation workflow with whole-business peer evidence

    **Qual2Cast · October 2026 · Local research deliverable**

    **Reader guide.** This single file includes the data, source evidence, code and results.
    **Run All** recalculates the analysis offline from saved inference outputs; no companion
    files or network calls are needed. Install NumPy, pandas, SciPy, matplotlib and IPython.
    Full inference is a separate opt-in workflow requiring the recorded models and dependencies.
    Code is initially folded where supported. GitHub provides a static view; the downloaded
    notebook is the canonical executable report.
    """)
    md("""
    ## Contents

    - [Abstract](#abstract)
    - [1. Research questions and proposal traceability](#section-1)
    - [2. Data, source boundaries and frozen sample](#section-2)
    - [3. Methods and evidence-based hypotheses](#section-3)
    - [4. Experimental design and evaluation boundaries](#section-4)
    - [5. Ranking results and top-five peers](#section-5)
    - [6. Whole-company profiles](#section-6)
    - [7. Valuation and investment-committee cases](#section-7)
    - [8. Independent human review](#section-8)
    - [9. Growth preparation](#section-9)
    - [10. Findings, limitations and integration](#section-10)
    - [Appendix A. Implementation and reproducibility](#appendix-a)
    - [Appendix B. Method research](#appendix-b)
    - [Appendix C. Factor and evaluation research](#appendix-c)
    """)
    md("""
    ## Abstract

    We construct inspectable comparable-company sets and exploratory enterprise-value calculations for a
    frozen ten-company, two-sector pilot, using the team's committed website evidence and
    permitted financial inputs. The intended application is a private target described by its
    name, website and basic financials. Each review sheet exposes proposed peers, supporting
    business activities, material scope questions, alternative-method disagreements and the
    calculation from peer multiples to enterprise value. These are proposed comparables,
    not independently approved investment-committee recommendations.

    The supporting experiments distinguish representation, comparison rule,
    information augmentation, candidate restrictions, peer-set size and valuation aggregation.
    Every applicable implemented method is recorded, including failures and unavailable inputs.
    Business compatibility concerns the full observed company rather than one convenient division.
    The financial outcome is an exploratory supplied-snapshot proxy; unknown source dates and
    definitions prevent interpreting it as a temporal valuation backtest. The computed status
    below states what this artifact actually establishes. A separate strict indication gate
    withholds an eligible valuation until original-peer evidence and financial date/definition
    checks pass; even that gate would not substitute for investment-committee approval.
    """)
    code("PAYLOAD_BASE64 = " + repr(base64.b64encode(payload).decode()) + "\nPAYLOAD_SHA256 = " + repr(sha(payload)),
         tags=["embedded-payload", "hide-input"], jupyter={"source_hidden": True})
    code(r'''
    import base64, hashlib, html, io, itertools, json, sys, types, zipfile
    import numpy as np
    import pandas as pd
    import matplotlib.pyplot as plt
    from IPython.display import display, HTML, Markdown, Code

    payload_bytes = base64.b64decode(PAYLOAD_BASE64)
    assert hashlib.sha256(payload_bytes).hexdigest() == PAYLOAD_SHA256
    archive = zipfile.ZipFile(io.BytesIO(payload_bytes))
    FILES = {name: archive.read(name) for name in archive.namelist()}
    payload_manifest = json.loads(FILES['payload_manifest.json'])
    for name, record in payload_manifest['files'].items():
        assert hashlib.sha256(FILES[name]).hexdigest() == record['sha256'], name
    PREFIX = payload_manifest.get('experiment_prefix','project/outputs-local/modular-validation/')
    PARAMETER_PATH = payload_manifest.get('parameter_archive_path','project/config/modular_validation_parameters.json')
    def read_json(name, default=None):
        return json.loads(FILES[name]) if name in FILES else default
    def read_csv(name, **kwargs):
        kwargs.setdefault('float_precision','round_trip')
        return pd.read_csv(io.BytesIO(FILES[name]), **kwargs) if name in FILES else pd.DataFrame()
    def as_bool(series):
        return series.astype(str).str.lower().isin(['true', '1'])
    def table(frame, rows=40):
        if frame is None or frame.empty:
            display(Markdown('*No available observations for this table.*'))
        else:
            display(frame.head(rows).style.hide(axis='index'))
            if len(frame) > rows:
                display(Markdown(f'*Showing {rows:,} of {len(frame):,} rows; the complete table remains in memory.*'))
    def safe_url(value):
        value = str(value or '').strip()
        if not value or value.lower() == 'nan': return ''
        if '://' not in value: value = 'https://' + value
        return value if value.startswith(('https://', 'http://')) else ''
    def links_table(frame, link_columns):
        shown = frame.copy()
        for col in link_columns:
            shown[col] = shown[col].map(lambda x: ('<a href="' + html.escape(safe_url(x), quote=True) +
                 '" target="_blank">' + html.escape(str(x)) + '</a>') if safe_url(x) else '')
        for col in shown.columns:
            if col not in link_columns: shown[col] = shown[col].map(lambda x: html.escape(str(x)))
        display(HTML(shown.to_html(index=False, escape=False)))

    # Load only pure numeric/evaluation modules; heavy inference code remains readable source.
    package = types.ModuleType('embedded_modular_validation')
    package.__path__ = []
    sys.modules[package.__name__] = package
    pure_modules=['numeric','evaluation','evidence_policy']
    if 'project/src/modular_validation/experiment_comparison.py' in FILES:pure_modules.append('experiment_comparison')
    for optional in ['local_llm','judgments','judgment_protocol']:
        if 'project/src/modular_validation/'+optional+'.py' in FILES:pure_modules.append(optional)
    for name in pure_modules:
        module_name = package.__name__ + '.' + name
        module = types.ModuleType(module_name)
        module.__package__ = package.__name__
        module.__file__ = 'embedded://src/modular_validation/' + name + '.py'
        sys.modules[module_name] = module
        exec(compile(FILES['project/src/modular_validation/' + name + '.py'], module.__file__, 'exec'), module.__dict__)
        setattr(package, name, module)
    numeric, evaluation, evidence_policy = package.numeric, package.evaluation, package.evidence_policy
    design = read_json(PREFIX + 'design_freeze.json')
    params = read_json(PARAMETER_PATH)
    seal = read_json(PREFIX + 'evaluation/all_rankings_freeze.json')
    for name, expected in seal['ranking_inputs'].items():
        assert hashlib.sha256(FILES[PREFIX + name.replace('\\', '/')]).hexdigest() == expected
    proof_current={'ranking_inputs':{name:hashlib.sha256(FILES[PREFIX+name.replace('\\','/')]).hexdigest()
                    for name in seal['ranking_inputs']},
        'design_sha256':hashlib.sha256(FILES[PREFIX+'design_freeze.json']).hexdigest(),
        'parameter_sha256':hashlib.sha256(FILES[PARAMETER_PATH]).hexdigest(),
        'evaluation_script_sha256':hashlib.sha256(FILES['project/scripts/evaluate_modular_validation.py']).hexdigest(),
        'direct_valuation_script_sha256':hashlib.sha256(FILES['project/scripts/run_direct_valuation.py']).hexdigest(),
        'module_sha256':{name.rsplit('/',1)[-1]:hashlib.sha256(data).hexdigest() for name,data in FILES.items()
            if name.startswith('project/src/modular_validation/') and name.endswith('.py')
            and '/' not in name.removeprefix('project/src/modular_validation/')}}
    seal_verification=evaluation.verify_experiment_seal(seal,proof_current)
    targets = pd.DataFrame(design['targets'])
    candidate_pool = read_json(PREFIX+'candidate_pool_freeze.json',{})
    if candidate_pool:
        assert hashlib.sha256(FILES[PREFIX+'candidate_pool_freeze.json']).hexdigest()==design['candidate_pool_sha256']
        assert set(candidate_pool['company_ids'])==set(design['pilot_company_ids'])
    snapshot = read_csv('team/data-local/snapshots/company_list_v3_websites_fixed.csv', dtype=str)
    snapshot['IQ_COMPANY_ID'] = snapshot['IQ_COMPANY_ID'].astype(str)
    F = snapshot.set_index('IQ_COMPANY_ID')
    assert F.index.is_unique, 'Snapshot company IDs must be unique'
    pieces = [read_csv(PREFIX + name.replace('\\', '/')) for name in seal['ranking_inputs']]
    rankings = pd.concat(pieces, ignore_index=True)
    assert not rankings.duplicated(['target_id', 'candidate_id', 'method']).any()
    assert (rankings.target_id != rankings.candidate_id).all()
    rankings['rank'] = pd.to_numeric(rankings['rank'], errors='coerce')
    rankings['score'] = pd.to_numeric(rankings['score'], errors='coerce')
    rankings['available'] = as_bool(rankings['available']) & np.isfinite(rankings.score) & rankings['rank'].notna()
    methods = sorted(rankings.method.unique())
    role_by_id = targets.set_index('IQ_COMPANY_ID').role.to_dict()
    target_ids = targets.IQ_COMPANY_ID.tolist()
    coverage = read_csv(PREFIX + 'core/text_coverage.csv', dtype={'IQ_COMPANY_ID': str})
    identifiers = read_csv(PREFIX + 'core/company_identifiers.csv', dtype=str)
    global_text_coverage=read_csv(PREFIX+'global-controls/core/text_coverage.csv',dtype={'IQ_COMPANY_ID':str})
    eligible_ids = (global_text_coverage if not global_text_coverage.empty else coverage).IQ_COMPANY_ID.tolist()
    comparison_ids = candidate_pool.get('company_ids',eligible_ids)
    for (target,method),frame in rankings.groupby(['target_id','method']):
        assert set(frame.candidate_id)==set(comparison_ids)-{target}, (target,method,'candidate ledger differs')
    global_control_path=PREFIX+'global-controls/core/rankings.csv'
    global_controls=read_csv(global_control_path)
    if candidate_pool:
        assert not global_controls.empty, 'Original full-universe controls must be retained'
        assert hashlib.sha256(FILES[global_control_path]).hexdigest()==candidate_pool['original_core_rankings_sha256']
    source_records = [read_json(name) for name in FILES if name.startswith('team/outputs-local/website_scrape/page_text/') and name.endswith('.json')]
    source_index = {}
    for record in source_records:
        for page in record.get('pages', []):
            source_index[str(record.get('IQ_COMPANY_ID')) + ':' + str(page.get('page_id'))] = page
    status = read_json(PREFIX + 'evaluation/evaluation_status.json', {})
    human_labels_new = int(status.get('independent_human_labels_new', 0))
    plt.rcParams.update({'figure.dpi': 125, 'axes.spines.top': False, 'axes.spines.right': False,
                         'font.size': 10, 'axes.titlesize': 12, 'figure.facecolor': 'white'})
    display(Markdown(f'**Integrity check passed:** {len(FILES):,} embedded files; '
        f'{len(snapshot):,} snapshot companies; {len(eligible_ids):,} website-eligible companies; '
        f'{len(comparison_ids):,} companies in the active comparison pool; '
        f'{len(methods)} methods with ranking rows; {len(targets)} frozen targets.'))
    ''')
    code(r'''
    requirement_status = pd.DataFrame([
        ('Current company data and provenance', f'{len(snapshot)} records; {len(source_records)} source JSON records; embedded hashes'),
        ('Ten targets / two sector extensions', f'{len(targets)} targets across {targets.target_sic4_code.nunique()} supplied SIC4 categories'),
        ('Active candidate scope', f'{len(comparison_ids)} fixed companies; {len(comparison_ids)-1} candidate ledger rows per target/method; original global controls kept separately'),
        ('Purpose of the comparison', 'Defensible whole-business peers and an indicative enterprise value'),
        ('Executed method coverage (supporting evidence)', str(len(methods))+' ranking methods; count is not validation'),
        ('Independent new human labels', str(human_labels_new)),
        ('Valuation evidence', 'Exploratory snapshot calculations; strict indications withheld while dates/definitions remain unresolved'),
        ('Growth forecasts and 80% interval validation', 'Not available: dated predictor/outcome panel not established'),
        ('Default Run All', 'Offline metrics, aggregation, tables and figures recomputed; inference outputs embedded'),
    ], columns=['Requirement', 'Actual status'])
    table(requirement_status)
    latest_team=read_json(PREFIX+'team_latest_readonly_update.json',{})
    if latest_team:
        display(Markdown('**Latest team-state check:** '+str(latest_team.get('observed_commit_time',''))+
            '; repository commit [`'+str(latest_team.get('github_head',''))[:7]+'`]('+str(latest_team.get('commit_url',''))+'). '+
            str(latest_team.get('effect_on_current_experiment',''))))
        display(Markdown('**Growth provenance:** '+str(latest_team.get('growth_note',''))))
    result_interpretation=read_json(PREFIX+'comparison/result_interpretation.json',{})
    if result_interpretation:
        display(Markdown('### Principal findings and practical contribution'))
        if result_interpretation.get('headline'):display(Markdown(result_interpretation['headline']))
        interpretation_findings=pd.DataFrame(result_interpretation.get('findings',[]))
        if not interpretation_findings.empty:table(interpretation_findings,rows=8)
        if result_interpretation.get('recommendation'):display(Markdown('**Current recommendation:** '+result_interpretation['recommendation']))
    ''')
    md("""
    ## 1. Research questions and proposal traceability

    Aziz's direct project instructions take priority over conflicting teammate interpretations
    or stale state documents: build an efficient, defensible valuation workflow; explain why
    the proposed comparables fit the whole business; reuse established tools where appropriate;
    and consider substantively different routes. The later permission for basic financial
    matching inputs supersedes an earlier blanket ban. Method counts are not a success criterion.

    **RQ1.** Can we provide an indicative enterprise value and explain why each proposed
    comparable belongs, using the permitted private-target information? Independent human
    review must assess business fit and material differences; ranking agreement alone cannot.

    **RQ2.** Does permitted financial information change peer selection and the supplied-snapshot
    valuation proxy? This is distinct from whether two firms operate the same business.

    **RQ3.** How do candidate constraints, fixed 3/5/10 peer sets, evidence abstention, and
    median/harmonic/rank-weighted aggregation change coverage and observed errors?

    **RQ4.** Which data and validation dependencies remain before the longer proposal's dated
    three-year growth prediction and calibrated 80% intervals can be evaluated?

    | Proposal / Monday requirement | This notebook's location | Acceptance boundary |
    |---|---|---|
    | General company comparison and two SIC extensions | Methods, ranking outputs, top-five tables | Full observed company scope, explicit missing evidence |
    | Ten targets, with the team's five-per-sector operational split | Frozen design and sample table | The split is a team design choice; PCTY is development and fresh pilot cases are separate |
    | Same-SIC benchmark | Methods and paired comparisons | Stable-ID ties; dense-within-SIC is a separate hybrid |
    | Explained top-five peers | Source-linked tables and whole-company case records | Model explanations are not independent human truth |
    | Named human verification | Blind review packet and label-status table | Blank fields remain blank; no fabricated relevance accuracy |
    | Peer-median EV/EBITDA | Recomputed valuation section | Positive usable rows, actual counts, no refill, declared date limitations |
    | Reproducible data, code and figures | Embedded payload and source appendix | Default offline reanalysis; heavy inference explicitly separate |
    | Three-year growth and 80% intervals | Growth preparation section | No forecast/calibration claim without dated historical data |
    """)
    md("""
    ## 2. Data, source boundaries and frozen sample

    The design was frozen before inspecting new company rankings and held-out target valuation
    outcomes. Targets were not replaced after source, model or financial failures. The two most
    populated supplied SIC4 groups form an intentionally restricted pilot, not a representative
    sample of all companies. The documented seed and inclusion probabilities are retained.

    All ten cases now serve as development evidence because the expanded factor choices were
    informed by their source-based case audits. The stored role `fresh_pilot` distinguishes
    nine newly selected cases from historical PCTY development; it does not mean an untouched
    end-to-end test set. Their target valuation outcomes were held back during choice design,
    but that does not erase source-informed adaptation. Lock choices before evaluating a new
    ten-company batch.

    Website-only controls remain separate from permitted financial augmentation. Target 10-Ks
    are excluded. Candidate-only filing enrichment requires its own declared information arm.
    The current snapshot's financial fields are disclosed here only after the all-ranking seal.
    Website evidence and local model outputs can omit activities; an unavailable statement does
    not establish that an activity is absent. No website frequency is treated as revenue share.

    The later pilot amendment retains the ten targets and reduces the expensive candidate
    comparison to a frozen common pool. The pool contains all website-eligible members of the
    two supplied SIC groups, the union of four independent retrievers' top-five results and
    seeded random controls. It was not selected by profile-cache availability or target values.
    Representation fitting and financial percentile references may still use the original
    eligible website corpus. A smaller ranking pool does not establish full-universe retrieval
    recall, and the original global controls are kept separate.
    """)
    code(r'''
    show_targets = targets.rename(columns={'IQ_COMPANY_ID':'Company ID', 'target_company_name':'Company',
        'target_ciq_ticker':'Ticker', 'target_sic4_code':'SIC4', 'role':'Evaluation role',
        'target_ciq_website':'Website', 'inclusion_probability':'Inclusion probability'})
    links_table(show_targets[['Company ID','Company','Ticker','SIC4','Evaluation role','Inclusion probability','Website']], ['Website'])
    table(pd.DataFrame([{'Team revision':design['team_revision'], 'Snapshot SHA-256':design['snapshot_sha256'],
        'Target freeze UTC':design['frozen_at_utc'], 'Ranking freeze UTC':seal.get('frozen_at_utc'),
        'Snapshot companies':len(snapshot), 'Website eligible':len(eligible_ids),
        'Active comparison companies':len(comparison_ids),'Candidates per target':len(comparison_ids)-1,
        'Excluded from website control':len(snapshot)-len(eligible_ids), 'Website pages':len(source_index)}]))
    display(Markdown('**Selection rule:** ' + design['selection_rule']))
    if candidate_pool:
        table(pd.DataFrame([{'Pool version':candidate_pool['version'],
            'Pool SHA-256':design['candidate_pool_sha256'],
            'Same-SIC eligible members':len(candidate_pool.get('same_sic4_all_eligible',[])),
            'Retrieved union members':len(candidate_pool.get('retrieved_union',[])),
            'Seeded random controls':len(candidate_pool.get('random_control_ids',[])),
            'Global control rows':len(global_controls)}]))
        display(Markdown('**Pool boundary:** '+candidate_pool.get('evaluation_scope','Restricted common pool.')))
        pool_retention=read_csv(PREFIX+'candidate_pool_retention.csv')
        if not pool_retention.empty:
            retention_recomputed=[]
            for (cid,method),rows in global_controls.groupby(['target_id','method']):
                original=rows[as_bool(rows.available)].sort_values(['rank','candidate_id']).candidate_id.tolist()
                for k in (3,5,10):
                    chosen=original[:k];retained=sum(peer in set(comparison_ids) for peer in chosen)
                    retention_recomputed.append({'target_id':cid,'method':method,'k':k,'original_returned':len(chosen),
                        'retained_in_common_pilot':retained,'ranked_candidate_retention':retained/len(chosen) if chosen else np.nan})
            retention_recomputed=pd.DataFrame(retention_recomputed)
            checked_retention=retention_recomputed.merge(pool_retention,on=['target_id','method','k'],suffixes=('_recomputed','_saved'),validate='one_to_one')
            assert len(checked_retention)==len(retention_recomputed)==len(pool_retention)
            for col in ['original_returned','retained_in_common_pilot','ranked_candidate_retention']:
                np.testing.assert_allclose(checked_retention[col+'_recomputed'],checked_retention[col+'_saved'],rtol=1e-10,equal_nan=True)
            pool_retention=retention_recomputed
            retention_summary=pool_retention.groupby(['method','k']).agg(mean_ranking_retention=('ranked_candidate_retention','mean'),
                minimum_ranking_retention=('ranked_candidate_retention','min')).reset_index()
            table(retention_summary[retention_summary.k.eq(10)],rows=30)
            display(Markdown('**Original-ranking retention, not relevance recall:** the pool was selected partly from four retrievers. '
                'Their original top-five peers are retained by design; omitted companies could matter to other methods, including activity transport.'))
    ''')
    md("""
    ### 2.1 Input attribution and bounded cleaning diagnostics

    Identity checks and text availability are examined before treating model output as evidence.
    Shared domains and cross-host pages are attribution flags, not automatic proof of a wrong
    entity. The separate live cleaning probe uses current captures and deliberately selected
    phrases; it neither reconstructs the original capture nor estimates population accuracy.
    A blocked page remains missing. Its retained-anchor fraction is not complete business recall.
    """)
    code(r'''
    input_audit=read_json(PREFIX+'input_quality_audit.json',{})
    if input_audit:
        audit_summary={k:input_audit.get(k) for k in [
            'duplicate_company_ids','ebitda_margin_consistency','valuation_dates',
            'financial_definitions','listing_status','notes']}
        audit_summary.update(shared_website_host_rows=len(input_audit.get('shared_website_hosts',[])),
                             cross_host_source_flags=len(input_audit.get('cross_host_sources',[])),
                             duplicate_exchange_ticker_rows=len(input_audit.get('duplicate_exchange_tickers',[])))
        display(HTML('<details><summary>Input audit and financial-definition limitations</summary><pre>'+
                     html.escape(json.dumps(audit_summary,indent=2))+'</pre></details>'))
        audit_targets=pd.DataFrame(input_audit.get('targets',[]))
        cols=[c for c in ['target_ciq_ticker','baseline_eligible','baseline_clean_words','source_pages',
                         'empty_raw_pages','economic_business_weights','valuation_date'] if c in audit_targets]
        if cols: table(audit_targets[cols],rows=20)
    cleaning=read_json(PREFIX+'live-cleaning-diagnostic/results.json',{})
    if cleaning:
        display(Markdown(f"**Separate current-capture probe:** {cleaning.get('captured_cases',0)} of "
                         f"{cleaning.get('attempted_cases',0)} selected pages captured. "+cleaning.get('interpretation','')))
        table(pd.DataFrame([{'Ticker':c.get('ticker'),'Status':c.get('status'),'URL':c.get('url')}
                            for c in cleaning.get('cases',[])]))
        table(read_csv(PREFIX+'live-cleaning-diagnostic/comparison.csv'),rows=30)
    else:
        display(Markdown('*No completed live-cleaning diagnostic is embedded.*'))
    ''')
    md("""
    ## 3. Methods and evidence-based hypotheses

    Method names are not evidence of superiority. The executed ledger below identifies which
    proposed arms produced company outputs. The research review in Appendix B provides source
    details and separates company-peer evidence from transfers out of other tasks.

    | Family / module | Mechanism and factor interpretation | Evidence and limits |
    |---|---|---|
    | Lexical / LSA / MPNet controls | Frozen business text; lexical or semantic representation; declared cosine geometry | [Hoberg–Phillips](https://doi.org/10.1086/688176) shows representation/filtering sensitivity; the [MPNet model card](https://huggingface.co/sentence-transformers/all-mpnet-base-v2) supports its encoder geometry, not whole-company validity |
    | Corpus-trained Doc2Vec; pooling/cleaning variants | Change representation or evidence weighting with the same source universe | [Website competitor study](https://facultynew.tuck.dartmouth.edu/uploads/gordonPhillips/publications/BOKN_Journal___INFORMS_MnSc.pdf) directly studies websites; its large corpus, global networks and financial proxies differ from this pilot |
    | Structured activities and sector facets | Product, buyer, operating role, delivery/revenue model, and all supported activities; unknown remains unknown | Enterprise taxonomies and the source-grounded extraction literature motivate the representation; literal quote checks do not prove complete or correct scope |
    | Balanced / unbalanced activity transport | Uniform textual activity mass; 1-cosine ground cost; exact EMD or explicitly regularized UOT | [WMD](https://proceedings.mlr.press/v37/kusnerb15.pdf), [Sinkhorn](https://papers.nips.cc/paper_files/paper/2013/file/af21d0c97db2e27e13572cbf59eb343d-Paper.pdf) and [UOT](https://arxiv.org/pdf/1607.05816) supply mechanisms, not company-task wins; discarded activity mass remains a company difference |
    | Financial rank distance / fusion | Mean absolute percentile-rank differences of permitted revenue, margin and debt/revenue; RRF combines independent ranks | [SARD evidence](https://research-api.cbs.dk/ws/portalfiles/portal/57344051/thomas_plenborg_et_al_multiv_rdians_ttelse_publishersversion.pdf) motivates characteristic ranks; these features are an adaptation, with date/definition issues |
    | Local LLM comparison | Source packets and a whole-company criterion; logged outputs and order tests | [Cao et al.](https://link.springer.com/article/10.1007/s11142-025-09892-6) provides company-peer evidence; this smaller local model and grounded workflow require their own evaluation |
    | Peer policy and aggregation | Fixed 3/5/10, evidence-coverage abstention; identical positive rows for median/harmonic/rank weights | [SelectiveNet](https://proceedings.mlr.press/v97/geifman19a/geifman19a.pdf) motivates coverage/error accounting; [Liu et al.](https://business.columbia.edu/sites/default/files-efs/imce-uploads/dnissim/publications/Equity%20Valuation%20Using%20Multiples.pdf) motivates a harmonic ablation, not universal superiority |
    | Direct supervised valuation, if executed | Frozen Ridge/boosting challengers with all ten targets excluded from fit | [Geertsema–Lu](https://onlinelibrary.wiley.com/doi/full/10.1111/1475-679X.12464) supports a different predictive family; a local undated cross-section is not its replication or a peer explanation |

    Actual weights, penalties, seeds, model revisions and factor definitions are embedded below.
    Equal weights are transparent declared choices, not learned economic materiality.
    """)
    code(r'''
    ledger_records = []
    for name in sorted(FILES):
        if name.startswith(PREFIX) and not name.startswith(PREFIX+'global-controls/') and name.endswith('method_ledger.json'):
            value = read_json(name)
            rows = value if isinstance(value, list) else value.get('methods', value.get('ledger', []))
            if isinstance(rows, list):
                ledger_records.extend([{**row, 'ledger_source':name.removeprefix(PREFIX)} for row in rows if isinstance(row, dict)])
    ledger = pd.DataFrame(ledger_records)
    method_counts = rankings.groupby('method').agg(targets=('target_id','nunique'), rows=('candidate_id','size'),
                      available_rows=('available','sum')).reset_index()
    table(method_counts, rows=100)
    ledger_status={}
    if not ledger.empty and 'method' in ledger:
        for row in ledger.to_dict('records'): ledger_status[str(row['method'])]=row.get('status','unspecified')
    coverage_ledger=pd.DataFrame([{'Method':method,
        'Ranking output present':method in methods,
        'Recorded status':ledger_status.get(method,'ranking_rows_present' if method in methods else 'no_saved_run_record'),
        'Interpretation':'Inspect actual coverage and validation below' if method in methods else 'No completed ranking claim; dependency/failure must remain explicit'}
        for method in sorted(set(design.get('methods_predeclared',[]))|set(design.get('additional_factor_methods',[]))|set(methods)|set(ledger_status))])
    table(coverage_ledger,rows=100)
    if not ledger.empty:
        cols = [c for c in ['method','status','reason','seconds','derivation','ledger_source'] if c in ledger]
        table(ledger[cols], rows=100)
    unavailable = pd.DataFrame([{'Comparison':key, 'Prerequisite / limitation':value}
        for key,value in params.get('blocked_comparisons',{}).items()])
    table(unavailable, rows=100)
    display(HTML('<details><summary>Exact frozen parameters</summary><pre>' +
                 html.escape(json.dumps(params, indent=2)) + '</pre></details>'))
    ''')
    md("""
    ### 3.1 Factor choice: business identity, economic exposure and financial comparability

    Product/function, customer/payer, operating role, distribution channel and the complete
    activity portfolio describe the business being compared. Monetization, geography,
    commercialization stage and capital needs describe economic exposure. Revenue, EBITDA
    margin and leverage are permitted financial descriptors. Investment quality and expected
    stock returns are separate objectives; a highly profitable firm is not automatically a
    close business comparable.

    The factor arms hold the comparison mechanism fixed where feasible and vary predeclared
    factor groups. Website statements support activity presence, not revenue weights. EBITDA
    margin cannot substitute for ROE, ROIC, gross margin or retention; one LTM observation
    cannot establish growth. Debt/EBITDA is a transformation of debt/revenue and EBITDA/revenue,
    so including all three as independent equal-weight factors would double-count information.
    Sector economics are conditional on actual activities: the supplied 7370 group is not
    uniformly SaaS, and the 2834 group includes food/animal testing and cannabis retail.
    """)
    code(r'''
    FACTOR_RESEARCH_PREFIX='project/data-local/sources/factor-research-2026-10-18/'
    factor_research_files=sorted(n for n in FILES if n.startswith(FACTOR_RESEARCH_PREFIX) and n.endswith('.json'))
    comparability_research=read_json(FACTOR_RESEARCH_PREFIX+'comparability.json',{})
    if comparability_research:
        factor_definitions=pd.DataFrame(comparability_research.get('factor_catalogue',[]))
        factor_columns=[c for c in ['id','layer','operational_definition','availability_under_current_target_regime','limitation'] if c in factor_definitions]
        display(HTML('<details><summary>Research catalogue: operational definitions and actual availability</summary>'+factor_definitions[factor_columns].to_html(index=False,escape=True)+'</details>'))
        target_factor_maps=pd.DataFrame(comparability_research.get('target_operational_maps',[]))
        if not target_factor_maps.empty:
            table(target_factor_maps[['ticker','scope_to_preserve','avoid']],rows=20)
    factor_specification=read_json(PREFIX+'factors/factor_specification.json',{})
    if factor_specification:
        display(HTML('<details><summary>Executed factor specification</summary><pre>'+html.escape(json.dumps(factor_specification,indent=2))+'</pre></details>'))
    factor_metadata=read_json(PREFIX+'factors/method_metadata.json',{})
    if factor_metadata:
        display(HTML('<details><summary>Factor method acquisition, representation and comparison contracts</summary><pre>'+html.escape(json.dumps(factor_metadata,indent=2))+'</pre></details>'))
    ''')
    md(r"""
    ### 3.2 Core comparison and valuation equations

    For company vectors $x_i,x_j$, the dense control uses

    $$s_{ij}=\frac{x_i^\top x_j}{\lVert x_i\rVert\lVert x_j\rVert}.$$

    The financial arm changes the information and comparison rule. Given a declared, fully
    observed factor set $F$ and percentile ranks $r_f$ from the frozen reference population,

    $$d_F(i,j)=\frac{1}{|F|}\sum_{f\in F}|r_f(i)-r_f(j)|,\qquad s_F(i,j)=-d_F(i,j).$$

    Missing required factors make that pair unavailable. Business-group comparisons report
    which groups are jointly known rather than interpreting missing evidence as a mismatch.

    With eligible peers $E_{i,k}$ from the original selected $k$ (without replacement of invalid
    financial rows), the primary arithmetic is

    $$\widehat{EV}_i=\operatorname{median}_{j\in E_{i,k}}(EV_j/EBITDA_j)\,EBITDA_i.$$

    At least three valid peers and positive target EBITDA are required. The harmonic ablation
    substitutes $|E_{i,k}|/\sum_{j\in E_{i,k}}(EV_j/EBITDA_j)^{-1}$ on the same positive peer rows.
    The calculation is enterprise value in the supplied units; financial alignment and
    comparable approval are separately reported gates.
    """)
    md("""
    ## 4. Experimental design and evaluation boundaries

    Method comparisons use the frozen candidate universe and target split. Source expansion,
    candidate restriction and financial augmentation change the information set and are named
    explicitly. No method must first pass through a cosine shortlist unless it is declared a
    conditional reranker; retrieval-pool losses then remain part of its limitation. The common
    pilot pool is partly retrieved by existing methods, so all pilot claims are conditional on
    that pool. Independent methods can rank every member, but cannot recover a firm outside it.

    Relevance uses a common pooled human review design. Grades distinguish incompatible business,
    partial topical overlap, defensible whole-company comparability, strong comparability and
    unknown evidence. Precision is bounded when top-five judgments are unknown. Ideal DCG must
    use the same judged pool for every method; historical PCTY labels are development evidence.
    Agreement, same-SIC share and text-length association are diagnostics, not relevance accuracy.

    Financial evaluation is performed after rankings are sealed. The same positive eligible
    peer rows are used across aggregation rules, and missing peers are not replaced. Fresh pilot
    and PCTY historical development cases are reported separately. The nine newly selected
    cases also became development cases when source audits informed factor design. These
    comparisons cannot establish general superiority or reliable interval calibration; a new
    batch is needed after locking the choices.
    """)
    code(r'''
    ordered = {}
    diagnostic_rows = []
    lengths = coverage.set_index('IQ_COMPANY_ID').clean_words.to_dict()
    sic_map = F.target_sic4_code.to_dict()
    for (target, method), group in rankings.groupby(['target_id','method'], sort=True):
        ranked = group[group.available].sort_values(['rank','candidate_id'], kind='stable')
        peers = ranked.candidate_id.astype(str).tolist()
        ordered[(str(target),method)] = peers
        proxy = evaluation.ranking_proxy_diagnostics(peers, text_lengths=lengths,
            candidate_sic=sic_map, target_sic=F.loc[target,'target_sic4_code'],
            scores=dict(zip(ranked.candidate_id,ranked.score)), k=5)
        diagnostic_rows.append({'target_id':target,'ticker':F.loc[target,'target_ciq_ticker'],
            'role':role_by_id.get(target), 'method':method, 'candidate_rows':len(group),
            'available_candidates':len(peers), 'available_fraction':len(peers)/len(group) if len(group) else np.nan,
            'returned_top5':min(5,len(peers)), 'same_sic_proxy':proxy['same_sic_fraction_known'],
            'score_textlength_spearman':proxy['score_length_spearman']})
    diagnostics = pd.DataFrame(diagnostic_rows)
    availability = diagnostics.groupby('method').agg(mean_fraction=('available_fraction','mean'),
        minimum_fraction=('available_fraction','min'), targets=('target_id','nunique'),
        mean_returned_top5=('returned_top5','mean')).reset_index()
    fig, ax = plt.subplots(figsize=(10, max(4, .32*len(availability))))
    plotted = availability.sort_values('mean_fraction')
    ax.barh(plotted.method, plotted.mean_fraction, color='#356b8c')
    ax.scatter(plotted.minimum_fraction, plotted.method, marker='|', color='#9e3d35', label='Minimum target coverage', zorder=3)
    ax.set(xlim=(0,1.03), xlabel='Fraction of candidate rows scored', title='Figure 1. Method availability on the frozen candidate universe')
    ax.legend(loc='lower right'); fig.tight_layout(); plt.show()
    display(Markdown('Candidate restrictions deliberately lower this fraction. Availability does not measure relevance.'))
    table(availability, rows=100)
    ''')
    md("## 5. Ranking results, agreement and source-linked top-five peers")
    code(r'''
    agreement = np.full((len(methods),len(methods)),np.nan)
    agreement_n = np.zeros_like(agreement,dtype=int)
    for i,a in enumerate(methods):
        for j,b in enumerate(methods):
            values=[]
            for target in target_ids:
                if (target,a) in ordered and (target,b) in ordered:
                    score=evaluation.ranking_agreement(ordered[(target,a)],ordered[(target,b)],k=5)['topk_jaccard']
                    if score is not None: values.append(score)
            if values: agreement[i,j]=np.mean(values); agreement_n[i,j]=len(values)
    fig,ax=plt.subplots(figsize=(max(8,.5*len(methods)),max(7,.46*len(methods))))
    im=ax.imshow(agreement,vmin=0,vmax=1,cmap='Blues')
    ax.set_xticks(range(len(methods)),methods,rotation=60,ha='right',fontsize=8)
    ax.set_yticks(range(len(methods)),methods,fontsize=8)
    ax.set_title('Figure 2. Mean top-five Jaccard agreement across available target pairs')
    fig.colorbar(im,ax=ax,shrink=.75,label='Agreement; not accuracy'); fig.tight_layout(); plt.show()
    top5_rows=[]
    for (target,method), peers in ordered.items():
        for rank,peer in enumerate(peers[:5],1):
            top5_rows.append({'target_id':target,'Target':F.loc[target,'target_ciq_ticker'],'Method':method,
                'Rank':rank,'Peer':F.loc[peer,'target_company_name'],'Ticker':F.loc[peer,'target_ciq_ticker'],
                'Peer ID':peer,'Website':F.loc[peer,'target_ciq_website']})
    top5 = pd.DataFrame(top5_rows)
    baseline='team_mpnet_cosine'
    if not top5.empty:
        display(Markdown('### Required baseline top-five table for all frozen targets'))
        links_table(top5[top5.Method.eq(baseline)].drop(columns='target_id'), ['Website'])
        display(Markdown('### Method-specific previews'))
        display(Markdown('The complete target–method top-five table is available as `top5` and in the embedded rankings. '
            'Each folded preview below shows at most ten rows; filter `top5` by `Target` and `Method` for a case.'))
        for method in methods:
            rows=top5[top5.Method.eq(method)].drop(columns='target_id')
            text=rows.head(10).to_html(index=False,escape=True)
            display(HTML('<details><summary>'+html.escape(method)+f' (preview of {min(10,len(rows))}/{len(rows)} returned peers)</summary>'+text+'</details>'))
    ''')
    md("""
    ### 5.1 Source perturbations and mechanism checks

    The perturbations test whether an identified source change survives preprocessing and
    changes the representation or ranking, with candidate matrices frozen. Their cases were
    selected after source inspection. Stability or movement is diagnostic: neither proves
    that the resulting company ranking is correct. The acquisition probe is separate.
    """)
    code(r'''
    perturbation=read_json(PREFIX+'perturbation_results.json',{})
    perturbation_rows=[]
    for row in perturbation.get('results',[]):
        a={p['company_id'] for p in row['top5_original']}
        b={p['company_id'] for p in row['top5_variant']}
        jaccard=len(a&b)/len(a|b) if a|b else np.nan
        np.testing.assert_allclose(jaccard,row['top5_jaccard'],equal_nan=True)
        perturbation_rows.append({'Target':row['ticker'],'Method':row['method'],
            'Fixture':row['fixture_id'],'Text changed':row['target_text_changed'],
            'Query cosine':row['original_variant_vector_cosine'],'Recomputed top5 Jaccard':jaccard,
            'Original top5':', '.join(p['ticker'] for p in row['top5_original']),
            'Variant top5':', '.join(p['ticker'] for p in row['top5_variant']),
            'Mean absolute rank shift':row['mean_absolute_rank_shift']})
    if perturbation_rows:
        table(pd.DataFrame(perturbation_rows),rows=30)
        display(Markdown('**Diagnostic limitations:** '+' '.join(perturbation.get('caveats',[]))))
    else:
        display(Markdown('*No completed source-perturbation result is embedded.*'))
    ''')
    md("""
    ## 6. Whole-company evidence, extraction failures and comparison cases

    Accepted model activities mean that a quoted source span passed a literal support check.
    They do not prove that the activity, role or all material businesses were correctly captured.
    Truncation, rejected outputs, unknown facets and incomplete scope remain visible. Company
    profiles below preserve every accepted activity instead of selecting one convenient business.
    Case selection is diagnostic and is not an independent accuracy test.
    """)
    code(r'''
    profile_candidates={}
    def consider_profile(record,path):
        if isinstance(record,dict) and record.get('company_id') and isinstance(record.get('known_activities'),list):
            cid=str(record['company_id'])
            profile_candidates.setdefault(cid,[]).append((path,record))
    profile_freeze=read_json(PREFIX+'profiles/run_freeze.json',{})
    expected_profile_hash=profile_freeze.get('profile_map_sha256')
    profile_maps=[name for name in sorted(FILES) if name.startswith(PREFIX+'profile-cache/')
                  and name.rsplit('/',1)[-1] in {'all_profiles.json','profiles.json','all_profiles_validated.json'}]
    if expected_profile_hash:
        profile_maps=[name for name in profile_maps if hashlib.sha256(FILES[name]).hexdigest()==expected_profile_hash]
        if not profile_maps:
            raise ValueError('The exact profile map used by the ranking run is missing from the payload')
    # Matching byte-identical maps are equivalent copies; distinct maps are not silently mixed.
    profile_maps_by_hash={hashlib.sha256(FILES[name]).hexdigest():name for name in profile_maps}
    if len(profile_maps_by_hash)==1:
        profile_map_path=next(iter(profile_maps_by_hash.values()))
        value=read_json(profile_map_path)
        for record in value.values(): consider_profile(record,profile_map_path)
        profile_note='Matched to the ranking-run hash.' if expected_profile_hash else 'No ranking-run profile hash was supplied.'
        display(Markdown('**Profile version:** '+profile_map_path.removeprefix(PREFIX)+'. '+profile_note))
    elif len(profile_maps_by_hash)>1:
        raise ValueError('Multiple profile maps exist without a unique ranking-run match')
    # Multiple copies of one extraction are deduplicated by configuration identity.
    profiles={}; profile_conflicts=[]
    for cid, records in profile_candidates.items():
        by_config={}
        for path,record in records:
            key=record.get('config_hash') or record.get('prompt_version') or path
            by_config[key]=(path,record)
        if len(by_config)==1:
            path,record=next(iter(by_config.values())); profiles[cid]=record
        else:
            profile_conflicts.append({'company_id':cid,'configurations':len(by_config),
                                      'status':'ambiguous_profile_version_not_silently_selected'})
    if expected_profile_hash:
        assert set(profiles)==set(comparison_ids), 'Canonical profiles must exactly cover the active comparison pool'
    profile_audit=pd.DataFrame([{'company_id':cid,'activities':len(record.get('known_activities',[])),
        'rejected':len(record.get('rejected_activities',[])), 'status':record.get('status'),
        'input_truncated':record.get('generation',{}).get('input_truncated'),
        'output_hit_limit':record.get('generation',{}).get('output_hit_limit'),
        'scope_complete':record.get('scope_complete',False),
        'human_scope_reviewed':record.get('human_scope_reviewed',False)} for cid,record in profiles.items()])
    if not profile_audit.empty:
        table(profile_audit.groupby('status',dropna=False).agg(companies=('company_id','size'),
            median_activities=('activities','median'), rejected_items=('rejected','sum')).reset_index())
    technical_retry_scope=read_json(PREFIX+'repair_scope_freeze.json',{})
    if technical_retry_scope:
        display(Markdown(f"**Uniform technical retry:** {technical_retry_scope['repair_company_count']} first-pass outputs "
            'qualified through an output limit or invalid JSON. Each received exactly one larger 4,096-token output budget, '
            'with the same model, prompt and full input. Retries replace their first pass regardless of apparent quality. '
            'Valid JSON with unsupported or missing facts was not retried; remaining failures still abstain.'))
    raw_profile_index=read_json('project/raw-profile-inputs/index.json',{})
    if raw_profile_index:
        for cid,record in profiles.items():
            lineage=record.get('technical_repair_lineage',{})
            for label,key in [('first_pass','first_pass_sha256'),('selected','selected_source_sha256')]:
                entry=raw_profile_index[label][cid]
                assert hashlib.sha256(FILES[entry['path']]).hexdigest()==entry['sha256']==lineage[key]
        display(Markdown(f'**Raw profile lineage checked:** exact first-pass and selected generation bytes for {len(profiles)} companies are embedded.'))
    if profile_conflicts: table(pd.DataFrame(profile_conflicts))
    source_support={cid:evidence_policy.profile_eligibility(record)[0] for cid,record in profiles.items()}
    profile_eligibility_ledger=pd.DataFrame([{'company_id':cid,'eligible':source_support[cid],
        'reason':evidence_policy.profile_eligibility(record)[1]} for cid,record in profiles.items()])
    if not profile_eligibility_ledger.empty:
        table(profile_eligibility_ledger.groupby(['eligible','reason']).size().reset_index(name='companies'))
    policy_rows=[]
    for (target,method),peers in ordered.items():
        result=evaluation.evidence_coverage_abstention(peers,source_support,
                    target_supported=source_support.get(target),k=5)
        policy_rows.append({'target_id':target,'method':method,'accepted':result['accepted'],
                           'selected_count':result['selected_count'],'reasons':result['reasons']})
    policy_results=pd.DataFrame(policy_rows)
    table(policy_results.groupby('method').agg(accepted_targets=('accepted','sum'),
         evaluated_targets=('target_id','size')).reset_index(),rows=100)
    display(Markdown('This uniform pre-outcome guard abstains on missing activities or explicitly truncated profiles. '
        'Literal evidence availability is not calibrated relevance, semantic correctness or human approval.'))
    for target in target_ids:
        record=profiles.get(target)
        title=html.escape(str(F.loc[target,'target_company_name']))
        if record is None:
            display(HTML('<details><summary>'+title+'</summary><p>No unambiguous accepted profile is available.</p></details>'))
            continue
        rows=[]
        for activity in record.get('known_activities',[]):
            source=source_index.get(str(activity.get('source_id')), {})
            rows.append({'Activity':activity.get('activity'),'Role':activity.get('role'),
                'Facets':json.dumps(activity.get('facets',{})), 'Source ID':activity.get('source_id'),
                'Evidence excerpt':' '.join(str(activity.get('quote','')).split()[:22]),
                'URL':source.get('url','')})
        rendered=pd.DataFrame(rows).to_html(index=False,escape=True) if rows else '<p>No accepted activities.</p>'
        rendered+=('<p>Extraction status: '+html.escape(str(record.get('status')))+
                   '; complete company scope is not established.</p>')
        display(HTML('<details><summary>'+title+f' ({len(rows)} supported-span activities)</summary>'+rendered+'</details>'))
    # Deterministically expose disagreement cases without calling either answer correct.
    case_rows=[]
    preferred=[m for m in ['sector_activity_profile','balanced_activity_ot','financial_rank_adapted'] if m in methods]
    for target in target_ids:
        for method in preferred:
            if (target,baseline) in ordered and (target,method) in ordered:
                result=evaluation.ranking_agreement(ordered[(target,baseline)],ordered[(target,method)],k=5)
                case_rows.append({'Target ID':target,'Target':F.loc[target,'target_ciq_ticker'],'Alternative':method,
                    'Top5 Jaccard':result['topk_jaccard'],
                    'Baseline peers':', '.join(str(F.loc[c,'target_ciq_ticker']) for c in ordered[(target,baseline)][:5]),
                    'Alternative peers':', '.join(str(F.loc[c,'target_ciq_ticker']) for c in ordered[(target,method)][:5])})
    if case_rows:
        case_table=pd.DataFrame(case_rows).sort_values(['Top5 Jaccard','Target','Alternative'])
        display(Markdown('### Largest observed disagreements (illustrative selection rule, not validated successes)'))
        table(case_table,rows=6)
        for case in case_table.head(2).to_dict('records'):
            target=case['Target ID']; method=case['Alternative']
            peers=list(dict.fromkeys([target]+ordered[(target,baseline)][:5]+ordered[(target,method)][:5]))
            case_profiles=[]
            for peer in peers:
                record=profiles.get(peer,{})
                activities=record.get('known_activities',[])
                case_profiles.append({'Company':F.loc[peer,'target_company_name'],
                    'Ticker':F.loc[peer,'target_ciq_ticker'],
                    'All accepted activity descriptions':' | '.join(str(a.get('activity','')) for a in activities),
                    'Roles':' | '.join(str(a.get('role','unknown')) for a in activities),
                    'Source IDs':' | '.join(str(a.get('source_id','')) for a in activities),
                    'Status':record.get('status','profile_unavailable'),
                    'Website':F.loc[peer,'target_ciq_website']})
            display(HTML('<details><summary>Whole-company inspection packet: '+html.escape(case['Target'])+
                ' / '+html.escape(method)+'</summary><p>All accepted activities retained; no human relevance conclusion asserted.</p>'+
                pd.DataFrame(case_profiles).to_html(index=False,escape=True)+'</details>'))
    ''')
    md("""
    ### 6.1 Local comparison protocols: schema reliability and ordering sensitivity

    The original model-authored matched/unmatched ledger is preserved as an experimental arm.
    A separately frozen, pre-outcome amendment clarifies that scope sufficiency permits a
    provisional comparison of observed activities and derives unmatched lists from valid model
    matches. Every supplied activity remains visible. Derived bookkeeping does not establish
    that the model correctly weighed each business; malformed matches are never repaired.
    Both arms use the same candidate shortlists, profiles, model revision and token limits.
    Before any amended-protocol inference, grades 2–3 were required for candidate proposals;
    grades 0–1 remain visible in its judgments but cannot supply valuation peers. The original
    ordinal arm is retained as a diagnostic control, not an approved peer proposal policy.
    Their output availability, invalid-output reasons and reversed-order agreement are separate
    from relevance accuracy. A usable JSON response is not a validated company peer.
    Responses are cached by exact ordered evidence, so an identical reverse-test prompt or
    empty dossier can reuse a response. Each task retains its own company identities; reuse
    requires identical reconstructed messages and a matching raw prompt, with origin lineage.
    The original response files remain unchanged.
    """)
    code(r'''
    protocol_rows=[]; protocol_errors=[]; protocol_examples=[]
    replay_raw_record=package.judgment_protocol.replay_raw_record if hasattr(package,'judgment_protocol') else None
    for folder,label in [('llm','Original model-authored ledger'),('llm-protocol-v2','Derived ledger diagnostic')]:
        records=read_json(PREFIX+folder+'/judgments.json',[])
        if not records:continue
        for record in records:
            left,right=(record['candidate_id'],record['target_id']) if record.get('reverse') else (record['target_id'],record['candidate_id'])
            replay=replay_raw_record(record,profile_a=profiles.get(left),profile_b=profiles.get(right),derived_ledger=folder=='llm-protocol-v2')
            assert replay['grade']==record.get('grade')
        forward=[r for r in records if not r.get('reverse')]
        usable=[r for r in forward if r.get('grade') is not None]
        reversal=read_csv(PREFIX+folder+'/order_reversal.csv')
        paired=reversal.dropna(subset=['forward','reverse']) if not reversal.empty else reversal
        protocol_rows.append({'Protocol':label,'Forward candidate pairs':len(forward),'Usable provisional grades':len(usable),
            'Forward grades 2 or 3':sum(r['grade']>=2 for r in usable),
            'Unique prompt keys':len({r['key'] for r in records}),
            'Usable reversed pairs':len(paired),'Same grade both orders':int(paired.forward.eq(paired.reverse).sum()) if len(paired) else 0,
            'Independent human labels':0})
        counts=pd.Series([r.get('error') or ('model_null_grade' if r.get('grade') is None else 'usable_provisional') for r in records]).value_counts()
        protocol_errors.extend({'Protocol':label,'Status':k,'Comparisons including reverse tests':int(v)} for k,v in counts.items())
    if protocol_rows:
        table(pd.DataFrame(protocol_rows),rows=10)
        table(pd.DataFrame(protocol_errors),rows=40)
        display(HTML('<details><summary>Pre-outcome protocol amendment</summary><pre>'+html.escape(json.dumps(read_json(PREFIX+'llm_protocol_amendment.json',{}),indent=2))+'</pre></details>'))
    ''')
    md("""
    ## 7. Recomputed peer valuation and paired snapshot comparisons

    This section recomputes each aggregation from the embedded full ranking and financial
    snapshot. A peer must have positive finite EBITDA and EV/EBITDA. The selected peer set
    remains fixed; fewer than three valid peers yields an unavailable estimate, with no refill.
    Median, positive harmonic mean and reciprocal-original-rank weighted mean use the same
    eligible rows. Negative or missing target EBITDA/multiple prevents a valid proxy error.

    The reported error compares implied and supplied multiples, equivalent to relative EV
    error when the same positive target EBITDA is used on both sides. **It is an exploratory
    snapshot proxy:** observation dates, EBITDA adjustments and EV construction are not fully
    aligned. Neither low proxy error nor a same-SIC match proves business comparability.
    """)
    code(r'''
    finance=F[['target_ebitda','target_ev_to_ebitda']].apply(pd.to_numeric,errors='coerce').replace([np.inf,-np.inf],np.nan)
    valid_peer_multiple=finance.target_ev_to_ebitda.where(finance.target_ebitda.gt(0)).to_dict()
    valuation_rows=[]; contribution_records=[]
    agg_names={'median':'median','positive_harmonic':'harmonic','reciprocal_rank_weighted_mean':'weighted'}
    for (target,method),peers in ordered.items():
        observed=finance.loc[target,'target_ev_to_ebitda']; ebitda=finance.loc[target,'target_ebitda']
        outcome_valid=np.isfinite(observed) and observed>0 and np.isfinite(ebitda) and ebitda>0
        for k in [3,5,10]:
            guard=evaluation.evidence_coverage_abstention(peers,source_support,
                target_supported=source_support.get(target),k=k)
            comparison=evaluation.fixed_peer_aggregations(peers[:k],valid_peer_multiple,minimum_valid_peers=3)
            contribution_records.append({'target_id':target,'method':method,'k':k,**comparison})
            for name,result in comparison['aggregations'].items():
                estimate=result['estimate']; valid=estimate is not None and outcome_valid
                estimate_valid=estimate is not None and np.isfinite(ebitda) and ebitda>0
                strict=evaluation.strict_valuation_indication(guard,estimate_multiple=estimate,
                    target_ebitda=ebitda,valid_peer_count=comparison['valid_count'],
                    dates_and_definitions_confirmed=False)
                valuation_rows.append({'target_id':target,'target_ticker':F.loc[target,'target_ciq_ticker'],
                    'role':role_by_id.get(target),'method':method,'k':k,'aggregation':agg_names[name],
                    'estimate_multiple':estimate,'observed_multiple':observed if np.isfinite(observed) else np.nan,
                    'supplied_target_ebitda':ebitda,
                    'estimated_ev_supplied_millions':estimate*ebitda if estimate_valid else np.nan,
                    'selected_peers':comparison['selected_count'],'valid_peers':comparison['valid_count'],
                    'snapshot_ape':abs(estimate-observed)/observed if valid else np.nan,
                    'snapshot_signed_error':(estimate-observed)/observed if valid else np.nan,
                    'snapshot_absolute_log_error':abs(np.log(estimate/observed)) if valid else np.nan,
                    'exploratory_estimate_policy':'unguarded_fixed_rank_snapshot_diagnostic',
                    'evidence_guard_accepted':guard['accepted'],'evidence_guard_reasons':guard['reasons'],
                    **strict,
                    'status':'exploratory_snapshot_proxy' if valid else
                        'indicative_value_available_without_observed_proxy' if estimate_valid else 'unavailable'})
    valuation=pd.DataFrame(valuation_rows)
    # Cross-check cached evaluation; actual tables below use the fresh recomputation.
    cached=read_csv(PREFIX+'evaluation/valuation_results.csv')
    if not cached.empty:
        keys=['target_id','method','k','aggregation']
        check=valuation.merge(cached[keys+['estimate_multiple']],on=keys,suffixes=('_recomputed','_saved'),validate='one_to_one')
        assert len(check)==len(valuation)==len(cached), 'Cached/recomputed valuation row coverage differs'
        np.testing.assert_allclose(check.estimate_multiple_recomputed,check.estimate_multiple_saved,rtol=1e-10,atol=1e-10,equal_nan=True)
        if 'estimated_ev_supplied_millions' in cached:
            ev_check=valuation.merge(cached[keys+['estimated_ev_supplied_millions']],on=keys,
                                    suffixes=('_recomputed','_saved'),validate='one_to_one')
            np.testing.assert_allclose(ev_check.estimated_ev_supplied_millions_recomputed,
                                       ev_check.estimated_ev_supplied_millions_saved,
                                       rtol=1e-10,atol=1e-10,equal_nan=True)
        if 'strict_indication_status' in cached:
            strict_check=valuation.merge(cached[keys+['strict_indication_status','evidence_guard_accepted']],
                on=keys,suffixes=('_recomputed','_saved'),validate='one_to_one')
            assert strict_check.strict_indication_status_recomputed.eq(strict_check.strict_indication_status_saved).all()
            assert strict_check.evidence_guard_accepted_recomputed.eq(strict_check.evidence_guard_accepted_saved).all()
        display(Markdown(f'**Recalculation check:** {len(check):,} aggregation estimates match the saved evaluator.'))
    primary=valuation[(valuation.k==5)&valuation.aggregation.eq('median')]
    summary=primary.groupby(['role','method']).agg(valid_targets=('snapshot_ape','count'),
        median_snapshot_ape=('snapshot_ape','median'),mean_snapshot_ape=('snapshot_ape','mean')).reset_index()
    table(summary,rows=100)
    fresh=primary[primary.role.eq('fresh_pilot')]
    pivot=fresh.pivot(index='target_id',columns='method',values='snapshot_ape')
    paired=[]
    if baseline in pivot:
        for method in pivot:
            valid=pivot[[baseline]].dropna() if method==baseline else pivot[[baseline,method]].dropna()
            paired.append({'method':method,'common_targets':len(valid),
                'baseline_median_same_targets':valid[baseline].median() if len(valid) else np.nan,
                'method_median_same_targets':valid[method].median() if len(valid) else np.nan,
                'median_paired_difference':(valid[method]-valid[baseline]).median() if len(valid) else np.nan})
    paired=pd.DataFrame(paired)
    if not paired.empty:
        shown=paired.dropna(subset=['median_paired_difference']).sort_values('median_paired_difference')
        fig,ax=plt.subplots(figsize=(10,max(4,.34*len(shown))))
        ax.barh(shown.method,shown.median_paired_difference,
                color=['#356b8c' if v<=0 else '#b86c46' for v in shown.median_paired_difference])
        ax.axvline(0,color='black',lw=.8)
        ax.set(xlabel='Median paired APE difference from MPNet (negative = smaller proxy error)',
               title='Figure 3. Newly selected development cases: paired snapshot proxy differences')
        fig.tight_layout();plt.show();table(paired,rows=100)
    display(Markdown('Different rows can have different common subsets; compare counts and target-level errors before drawing conclusions.'))
    display(Markdown('The stored role **fresh_pilot** means newly selected relative to historical PCTY; '
        'all ten source-audited cases are now development evidence, not an untouched final test.'))
    target_error_matrix=primary.pivot(index='method',columns='target_ticker',values='snapshot_ape').sort_index()
    if not target_error_matrix.empty:
        cmap=plt.get_cmap('YlOrRd').copy();cmap.set_bad('#e2e6eb')
        fig,ax=plt.subplots(figsize=(12,max(5,.32*len(target_error_matrix))))
        im=ax.imshow(np.log1p(target_error_matrix.to_numpy(float)),aspect='auto',cmap=cmap)
        ax.set_xticks(range(len(target_error_matrix.columns)),target_error_matrix.columns)
        ax.set_yticks(range(len(target_error_matrix)),target_error_matrix.index)
        for i in range(len(target_error_matrix)):
            for j in range(len(target_error_matrix.columns)):
                value=target_error_matrix.iloc[i,j]
                ax.text(j,i,f'{value*100:.0f}%' if pd.notna(value) else 'NA',ha='center',va='center',fontsize=7)
        ax.set_title('Figure 4. All ten exploratory cases: k=5 median snapshot errors',loc='left')
        fig.colorbar(im,ax=ax,label='log(1 + APE); cell labels show raw percentage error',fraction=.025)
        fig.tight_layout();plt.show()
    aggregation_summary=valuation[valuation.role.eq('fresh_pilot')].groupby(['k','aggregation']).agg(
        available_estimates=('estimate_multiple','count'),proxy_error_rows=('snapshot_ape','count'),
        median_proxy_ape=('snapshot_ape','median')).reset_index()
    table(aggregation_summary)
    display(Markdown('This pooled aggregation table is descriptive across correlated method–target rows; it is not an independent-sample significance test.'))
    baseline_targets=primary[primary.method.eq(baseline)][['target_ticker','role','estimate_multiple',
        'supplied_target_ebitda','estimated_ev_supplied_millions',
        'observed_multiple','selected_peers','valid_peers','snapshot_ape','status',
        'evidence_guard_accepted','strict_indication_status','strict_indication_reasons']]
    table(baseline_targets,rows=20)
    display(Markdown('Exploratory enterprise-value arithmetic = eligible-peer multiple × supplied target EBITDA. '
        'Values are in supplied $ millions; currency is not independently confirmed. '
        'A strict eligible indication is separately withheld while evidence or date/definition checks fail. '
        'The arithmetic concerns enterprise value; no unsupported cash/debt bridge to equity price is added.'))
    ''')
    md("""
    ### Compatible module configurations and sensitivity

    The comparison enumerates implemented rankers × peer counts × aggregation rules and keeps
    direct predictive models in their separate model × information block. This is a compatible
    cross of dependent method bundles, not an orthogonal factorial experiment. Factor ablations
    isolate selected choices; arbitrary post-hoc combinations or weights are not promoted.

    Each comparison uses the dense baseline at the same peer count and aggregation, and reports
    the exact common target subset alongside each method's own coverage. Deleting one target
    from a descriptive summary tests sensitivity; it does not retrain a model and is not cross-
    validation. No winner or significance claim is selected from the current development cases.
    """)
    code(r'''
    saved_configuration_results=read_csv(PREFIX+'comparison/configuration_results.csv')
    comparison_status=read_json(PREFIX+'comparison/comparison_status.json',{})
    configuration_results=pd.DataFrame();configuration_sensitivity=pd.DataFrame()
    if hasattr(package,'experiment_comparison'):
        comparison=package.experiment_comparison
        newly_selected_ids=targets.loc[targets.role.eq('fresh_pilot'),'IQ_COMPANY_ID'].tolist()
        configuration_records=[];sensitivity_records=[]
        for method in methods:
            for k in (3,5,10):
                for aggregation in ('median','harmonic','weighted'):
                    subset=valuation[(valuation.method.eq(method))&(valuation.k.eq(k))&valuation.aggregation.eq(aggregation)].to_dict('records')
                    reference=valuation[(valuation.method.eq(baseline))&(valuation.k.eq(k))&valuation.aggregation.eq(aggregation)].to_dict('records')
                    key={'configuration_id':f'{method}__k{k}__{aggregation}','method':method,'k':k,'aggregation':aggregation}
                    configuration_records.append({**key,**comparison.summarize_configuration(subset,reference,fresh_ids=newly_selected_ids)})
                    sensitivity_records.extend({**key,**row} for row in comparison.leave_one_target_out(subset,reference,fresh_ids=newly_selected_ids))
        configuration_results=pd.DataFrame(configuration_records)
        configuration_sensitivity=pd.DataFrame(sensitivity_records)
        keys=['method','k','aggregation']
        if not saved_configuration_results.empty:
            checks=configuration_results.merge(saved_configuration_results,on=keys,suffixes=('_recomputed','_saved'),validate='one_to_one')
            assert len(checks)==len(configuration_results)==len(saved_configuration_results), 'Configuration coverage differs'
            for column in ['own_available_targets','own_median_ape','own_median_absolute_log_error','common_paired_targets',
                           'median_paired_ape_difference','evidence_guard_accepted_targets','strict_indication_available_targets']:
                np.testing.assert_allclose(pd.to_numeric(checks[column+'_recomputed'],errors='coerce'),
                    pd.to_numeric(checks[column+'_saved'],errors='coerce'),rtol=1e-10,atol=1e-10,equal_nan=True)
            metadata_columns=[c for c in ['acquisition','cleaning','representation','similarity','factor_family','candidate_policy','information_regime','source_family','configuration_status'] if c in saved_configuration_results]
            configuration_results=configuration_results.merge(saved_configuration_results[keys+metadata_columns],on=keys,validate='one_to_one')
        display(Markdown(f'**Recomputed compatible configurations:** {len(configuration_results):,}; '
            f'{len(configuration_sensitivity):,} descriptive target-deletion rows. '
            'These summaries use the newly selected development subset and preserve common-target counts.'))
        shown_columns=['method','k','aggregation','own_available_targets','own_median_ape','common_paired_targets',
                       'median_paired_ape_difference','evidence_guard_accepted_targets','strict_indication_available_targets']
        table(configuration_results[(configuration_results.k.eq(5))&configuration_results.aggregation.eq('median')][shown_columns],rows=100)
        display(HTML('<details><summary>Configuration definitions — bounded preview</summary>'+configuration_results.head(12).to_html(index=False,escape=True)+'</details>'))
        display(Markdown('All compatible rows remain in `configuration_results`; exact target-level calculations remain in `valuation`. '
            'These complete dataframes and their embedded CSVs are available without rendering hundreds of wide rows.'))
        if not configuration_sensitivity.empty:
            sensitivity_summary=configuration_sensitivity.groupby(['method','k','aggregation']).agg(
                minimum_common_targets=('common_paired_targets','min'),
                minimum_paired_APE_difference=('median_paired_ape_difference','min'),
                maximum_paired_APE_difference=('median_paired_ape_difference','max')).reset_index()
            display(HTML('<details><summary>Target-deletion sensitivity: k=5 median (no retraining)</summary>'+sensitivity_summary[(sensitivity_summary.k.eq(5))&sensitivity_summary.aggregation.eq('median')].to_html(index=False,escape=True)+'</details>'))
    elif not saved_configuration_results.empty:
        raise ValueError('Configuration results require their embedded pure comparison helper')
    if comparison_status:
        display(HTML('<details><summary>Comparison completion and provenance record</summary><pre>'+html.escape(json.dumps(comparison_status,indent=2))+'</pre></details>'))
    ''')
    md("""
    ### 7.1 Investment-committee review sheets: proposed peers and scope questions

    Each sheet begins with the exploratory baseline calculation and makes the proposed peer rationale
    inspectable. The baseline is an anchor for comparison, not a declared winner. Every accepted
    activity is shown; economic materiality remains unknown unless separately sourced.
    Provisional model reasons account for supplied activities but are not semantic verification.
    Alternatives show whether the conclusion depends on the comparison rule. No sheet is
    approved until an independent reviewer checks the original evidence and material differences.
    """)
    code(r'''
    llm_records=read_json(PREFIX+'llm/judgments.json',[])
    forward_judgments={(r.get('target_id'),r.get('candidate_id')):r for r in llm_records if not r.get('reverse')}
    ic_reviews={}; ic_companies={}
    ic_literal_quote_checks=0
    for name in ['ic_case_reviews_health.json','ic_case_reviews_software.json']:
        audit=read_json(PREFIX+name,{})
        if not audit: continue
        assert audit.get('independent_human_labels')==0
        audit_ranking_path=global_control_path if candidate_pool else PREFIX+'core/rankings.csv'
        assert audit.get('ranking_sha256')==hashlib.sha256(FILES[audit_ranking_path]).hexdigest()
        for cid,company in audit.get('companies',{}).items():
            source_path='team/outputs-local/website_scrape/page_text/'+cid+'.json'
            source_bytes=FILES[source_path];pages={p['page_id']:p for p in read_json(source_path)['pages']}
            for evidence in company['source_records']:
                assert hashlib.sha256(source_bytes).hexdigest()==evidence['source_json_sha256']
                page=pages[evidence['page_id']];field=evidence['source_field']
                index=evidence.get('raw_block_index',evidence.get('block_index'))
                literal=page[field][index] if isinstance(page[field],list) else page[field]
                assert evidence['quote']==literal
                assert evidence.get('url',evidence.get('page_url'))==page['url']
                assert evidence.get('fetched_at')==page.get('fetched_at')
                ic_literal_quote_checks+=1
            ic_companies[cid]=company
        for pair in audit.get('pairs',[]):
            key=(pair['target_id'],pair['candidate_id'])
            if key in ic_reviews: raise ValueError('Duplicate IC evidence review')
            assert pair.get('agent_provisional') is True and pair.get('human_approved') is False
            assert ordered.get((key[0],baseline),[])[pair['baseline_rank']-1]==key[1]
            for claim in pair.get('overlap_claims',[]):
                for side,cid in [('target',key[0]),('candidate',key[1])]:
                    allowed={e['evidence_id'] for e in audit['companies'][cid]['source_records']}
                    assert claim[side+'_evidence_ids'] and set(claim[side+'_evidence_ids'])<=allowed
            ic_reviews[key]=pair
    def agent_scope_text(cid):
        scope=ic_companies.get(cid,{}).get('observed_business_scope',[])
        return ' | '.join(str(a.get('activity','')) if isinstance(a,dict) else str(a) for a in scope)
    def activity_text(cid):
        return ' | '.join(str(a.get('activity','')) for a in profiles.get(cid,{}).get('known_activities',[])) or 'Unknown: no accepted activities'
    def role_text(cid):
        return ' | '.join(dict.fromkeys(str(a.get('role','unknown')) for a in profiles.get(cid,{}).get('known_activities',[]))) or 'Unknown'
    ic_rows=[]
    for target in target_ids:
        estimate=primary[(primary.target_id.eq(target)) & primary.method.eq(baseline)]
        row=estimate.iloc[0].to_dict() if len(estimate) else {}
        ic_rows.append({'Target':F.loc[target,'target_ciq_ticker'],'Baseline':baseline,
            'Peer multiple':row.get('estimate_multiple'),
            'Supplied EBITDA ($ millions)':row.get('supplied_target_ebitda'),
            'Exploratory EV arithmetic (supplied $ millions)':row.get('estimated_ev_supplied_millions'),
            'Strict indication':row.get('strict_indication_status','withheld'),
            'Strict gate reasons':' | '.join(row.get('strict_indication_reasons',[])),
            'Eligible financial peers':row.get('valid_peers'),
            'Source-based AGENT peer reviews':sum((target,c) in ic_reviews for c in ordered.get((target,baseline),[])[:5]),
            'Independent approval':'Pending','Scope completeness':'Not established'})
    table(pd.DataFrame(ic_rows),rows=20)
    display(Markdown('Currency is not independently confirmed. These are exploratory enterprise-value calculations from '
                     'an undated supplied snapshot. Strict eligible indications and independent approval remain separate gates.'))
    for target in target_ids:
        title=str(F.loc[target,'target_ciq_ticker'])+' — '+str(F.loc[target,'target_company_name'])
        packet=[]
        for rank,peer in enumerate(ordered.get((target,baseline),[])[:5],1):
            judgment=forward_judgments.get((target,peer),{})
            parsed=judgment.get('parsed',{})
            usable=judgment.get('grade') is not None and not judgment.get('error')
            review=ic_reviews.get((target,peer),{})
            packet.append({'Rank':rank,'Proposed peer':F.loc[peer,'target_company_name'],
                'Observed full-scope inventory (AGENT)':agent_scope_text(peer) or 'No separate evidence audit',
                'All accepted model activities':activity_text(peer),'Extracted roles':role_text(peer),
                'Source-based AGENT committee rationale':review.get('committee_rationale','No separate evidence audit'),
                'Material differences (AGENT)':' | '.join(c['claim'] for c in review.get('material_mismatches',[])),
                'Provisional model reason':parsed.get('reason','') if usable else 'No usable whole-company model rationale',
                'Unmatched target activities':json.dumps(parsed.get('unmatched_A',[])) if usable else 'Unknown',
                'Unmatched peer activities':json.dumps(parsed.get('unmatched_B',[])) if usable else 'Unknown',
                'Source IDs':' | '.join(str(a.get('source_id','')) for a in profiles.get(peer,{}).get('known_activities',[])),
                'Website':F.loc[peer,'target_ciq_website'],
                'Approval':'Pending independent whole-business review'})
        alternatives=[]
        for method in ['financial_rank_adapted','balanced_activity_ot','sector_activity_profile',
                       'source_grounded_local_llm_rerank','local_llm_derived_activity_ledger']:
            if (target,method) not in ordered: continue
            peers=ordered[(target,method)][:5]
            est=primary[(primary.target_id.eq(target)) & primary.method.eq(method)]
            alternatives.append({'Comparison':method,
                'Proposed peers':', '.join(str(F.loc[c,'target_ciq_ticker']) for c in peers),
                'Exploratory EV arithmetic (supplied $ millions)':est.estimated_ev_supplied_millions.iloc[0] if len(est) else None,
                'Strict indication':est.strict_indication_status.iloc[0] if len(est) else 'withheld',
                'Review implication':'Inspect the changed peers and material differences; not an automatic improvement'})
        markup='<p><b>Full accepted target activity list:</b> '+html.escape(activity_text(target))+'</p>'
        markup+='<p><b>Extracted target roles:</b> '+html.escape(role_text(target))+'</p>'
        markup+='<p>Unknowns: omitted activities, legal/consolidation boundaries, activity materiality, '
        markup+='financial date/currency/definitions and independent peer approval.</p>'
        markup+=pd.DataFrame(packet).to_html(index=False,escape=True) if packet else '<p>No proposed baseline peers.</p>'
        if alternatives: markup+='<p><b>Rule sensitivity:</b></p>'+pd.DataFrame(alternatives).to_html(index=False,escape=True)
        display(HTML('<details><summary>'+html.escape(title)+'</summary>'+markup+'</details>'))
    display(Markdown(f'**Completed provisional evidence reviews:** {len(ic_reviews)} baseline target–peer pairs. '
        f'{ic_literal_quote_checks} literal quotation/hash checks were recalculated. '
        'These are source-based AGENT interpretations, not independent labels or approved comparable sets.'))
    if candidate_pool:
        display(Markdown('**Review provenance:** audits retain the original full-universe MPNet ranking hash. '
            'The notebook separately confirms each reviewed pair occupies the same baseline rank in the active pilot; '
            'the source audit is not relabeled as a new extraction.'))
    for target in target_ids:
        body=''
        for peer in ordered.get((target,baseline),[])[:5]:
            review=ic_reviews.get((target,peer))
            if not review: continue
            title=str(F.loc[target,'target_ciq_ticker'])+' / '+str(F.loc[peer,'target_ciq_ticker'])
            body+='<h4>'+html.escape(title)+'</h4><p>'+html.escape(review['committee_rationale'])+'</p>'
            for label,claims in [('Supported overlap',review.get('overlap_claims',[])),
                                 ('Material difference or scope concern',review.get('material_mismatches',[]))]:
                body+='<p><b>'+label+'</b></p><ul>'+''.join('<li>'+html.escape(c['claim'])+'</li>' for c in claims)+'</ul>'
            for cid in (target,peer):
                company=ic_companies[cid]
                body+='<p><b>'+html.escape(company['name'])+' — observed full scope:</b> '+html.escape(agent_scope_text(cid))+'</p>'
                body+='<p>Scope unknowns: '+html.escape(' | '.join(company.get('scope_unknowns',[])))+'</p>'
                source_rows=[{'Evidence ID':s['evidence_id'],'Exact source statement':s['quote'],
                    'URL':s.get('url',s.get('page_url')),'Fetched at':s.get('fetched_at'),
                    'Page':s.get('page_id'),'Raw block':s.get('raw_block_index',s.get('block_index')),
                    'Source JSON SHA-256':s.get('source_json_sha256')} for s in company['source_records']]
                body+='<details><summary>Exact frozen-source evidence</summary>'+pd.DataFrame(source_rows).to_html(index=False,escape=True)+'</details>'
            body+='<p><b>Unresolved:</b> '+html.escape(' | '.join(review.get('unknowns',[])))+'</p>'
            body+='<p><b>Independent reviewer questions:</b> '+html.escape(' | '.join(review.get('review_questions',[])))+'</p>'
        if body:
            display(HTML('<details><summary>Full source-based AGENT audit — '+html.escape(str(F.loc[target,'target_ciq_ticker']))+
                         ' (all five baseline proposals; unapproved)</summary>'+body+'</details>'))
    ''')
    md("""
    ### 7.2 Source-based assessment of changed candidates

    A separate AI/source review examines the first proposed candidate from fixed activity,
    sector-facet, business-factor and financial routes. This exposes concrete successes,
    differences and failure mechanisms; the purposive top-candidate selection cannot estimate
    population accuracy. It does not create independent human grades.
    """)
    code(r'''
    new_candidate_reviews=[];new_quote_checks=0
    for filename in ['new_candidates_health.json','new_candidates_software.json','post_result_tradeoff_cases.json']:
        review=read_json(PREFIX+'agent-assessment/'+filename,{})
        if not review:continue
        assert review.get('actor_type')=='ai' and review.get('human_approved') is False
        for case in review.get('cases',[]):
            for evidence in case.get('source_evidence',[]):
                source_path='team/outputs-local/website_scrape/page_text/'+evidence['company_id']+'.json'
                assert hashlib.sha256(FILES[source_path]).hexdigest()==evidence['source_json_sha256']
                pages={p['page_id']:p for p in read_json(source_path)['pages']}
                page=pages[evidence['page_id']];literal=page[evidence['source_field']]
                if isinstance(literal,list):literal=literal[evidence['raw_block_index']]
                assert ' '.join(evidence['quote'].split()) in ' '.join(str(literal).split())
                assert evidence['url']==page['url']
                new_quote_checks+=1
            new_candidate_reviews.append(case)
    if new_candidate_reviews:
        def as_prose(value):return ' | '.join(map(str,value)) if isinstance(value,list) else str(value or '')
        summaries=[]
        for case in new_candidate_reviews:
            summaries.append({'Target':case['target_ticker'],'Candidate':case['candidate_ticker'],
                'Methods':as_prose(case['methods']),
                'Selection phase':case.get('selection_phase','pre-outcome source audit'),
                'AI/source assessment':case['verdict_text']})
            body=''
            if case.get('selection_phase'):body+='<p><b>Selection phase:</b> '+html.escape(case['selection_phase'])+'</p>'
            for key,label in [('supported_overlap','Supported overlap'),('material_differences','Material differences'),('unknowns','Unknowns')]:
                body+='<p><b>'+label+':</b> '+html.escape(as_prose(case.get(key)))+'</p>'
            body+=pd.DataFrame(case['source_evidence']).to_html(index=False,escape=True)
            display(HTML('<details><summary>New candidate audit: '+html.escape(case['target_ticker']+' / '+case['candidate_ticker'])+
                '</summary><p>'+html.escape(case['verdict_text'])+'</p>'+body+'</details>'))
        table(pd.DataFrame(summaries),rows=12)
        display(Markdown(f'**Additional source checks:** {len(new_candidate_reviews)} purposive candidate reviews; {new_quote_checks} exact source-span/hash checks. No human labels created.'))
    challenges=read_csv(PREFIX+'agent-assessment/challenge_case_tracking.csv')
    if not challenges.empty:
        display(Markdown('**Preselected challenge cases:** the complete method-by-case rank table is available as `challenges`. Missing ranks mean unavailable, not rejection. Avoiding a selected baseline failure does not prove overall accuracy.'))
        table(challenges[challenges.method.isin([baseline,'balanced_activity_ot','business_multifacet_equal','source_grounded_local_llm_rerank'])],rows=20)
    ''')
    md("""
    ### 7.3 Direct valuation challengers, if available

    These models predict a financial outcome rather than providing a comparable-company set.
    Their cached predictions are kept distinct from rerunning inference. The cell recomputes
    prediction errors against the embedded outcomes, checks target exclusion in the training
    manifest, and retains the undated-cross-section limitation.
    """)
    code(r'''
    direct=read_csv(PREFIX+'evaluation/direct_valuation_results.csv')
    direct_manifest=read_json(PREFIX+'evaluation/direct_valuation_manifest.json',{})
    if direct.empty:
        display(Markdown('*No completed direct-valuation output is embedded.*'))
    else:
        assert not(set(direct_manifest.get('train_ids',[])) & set(target_ids))
        direct=direct.copy(); actual=finance.loc[direct.target_id,'target_ev_to_ebitda'].to_numpy()
        target_ebitda=finance.loc[direct.target_id,'target_ebitda'].to_numpy()
        pred=pd.to_numeric(direct.prediction,errors='coerce').to_numpy()
        valid=np.isfinite(pred)&(pred>0)&np.isfinite(actual)&(actual>0)&np.isfinite(target_ebitda)&(target_ebitda>0)
        direct['recomputed_snapshot_ape']=np.where(valid,np.abs(pred-actual)/np.where(actual>0,actual,np.nan),np.nan)
        if 'snapshot_ape' in direct:
            np.testing.assert_allclose(direct.recomputed_snapshot_ape,direct.snapshot_ape,rtol=1e-10,equal_nan=True)
        direct['snapshot_ape']=direct.recomputed_snapshot_ape
        ratio=np.full(len(direct),np.nan);np.divide(pred,actual,out=ratio,where=valid)
        direct['snapshot_absolute_log_error']=np.abs(np.log(ratio))
        table(direct.groupby(['role','model','information']).agg(valid_targets=('recomputed_snapshot_ape','count'),
            median_snapshot_ape=('recomputed_snapshot_ape','median')).reset_index(),rows=100)
        missing_columns=[c for c in ['ticker','model','information','finite_prediction',
            'financial_missing_count','financial_missing_fields','financial_missing_policy'] if c in direct]
        if missing_columns: table(direct[missing_columns],rows=50)
        if hasattr(package,'experiment_comparison'):
            direct_configuration_rows=[]
            reference=valuation[(valuation.method.eq(baseline))&(valuation.k.eq(5))&valuation.aggregation.eq('median')].to_dict('records')
            for model in ('ridge','hist_gradient_boosting'):
                for information in ('financial_only','financial_plus_website'):
                    records=direct[direct.model.eq(model)&direct.information.eq(information)].to_dict('records')
                    records=[{**row,'estimate_multiple':row.get('prediction')} for row in records]
                    direct_configuration_rows.append({'model':model,'information':information,
                        **package.experiment_comparison.summarize_configuration(records,reference,fresh_ids=targets.loc[targets.role.eq('fresh_pilot'),'IQ_COMPANY_ID'].tolist())})
            direct_configuration_results=pd.DataFrame(direct_configuration_rows)
            saved_direct_configurations=read_csv(PREFIX+'comparison/direct_configuration_results.csv')
            if not saved_direct_configurations.empty:
                checks=direct_configuration_results.merge(saved_direct_configurations,on=['model','information'],suffixes=('_recomputed','_saved'),validate='one_to_one')
                assert len(checks)==len(direct_configuration_results)==len(saved_direct_configurations)
                for column in ['own_available_targets','own_median_ape','common_paired_targets','median_paired_ape_difference','own_median_absolute_log_error']:
                    np.testing.assert_allclose(pd.to_numeric(checks[column+'_recomputed'],errors='coerce'),pd.to_numeric(checks[column+'_saved'],errors='coerce'),rtol=1e-10,equal_nan=True)
            table(direct_configuration_results[['model','information','own_available_targets','own_median_ape','common_paired_targets','median_paired_ape_difference']],rows=20)
            display(Markdown('Direct models are compared with dense k=5 median arithmetic; their training universe may be broader than the active retrieval pool. All ten target IDs are excluded from fit. This does not validate business-peer relevance.'))
        display(HTML('<details><summary>Direct-model training manifest</summary><pre>'+html.escape(json.dumps(direct_manifest,indent=2))+'</pre></details>'))
    ''')
    md("""
    ## 8. Independent human review and incomplete judgment accounting

    The review packet contains method-pooled candidates and deterministic controls, with method
    identities and scores hidden from reviewers. Reviewers should independently nominate peers
    before inspecting the pool, then assess the same source packets. Empty judgment fields are
    unknown. Model-generated profiles, source quotation checks and provisional LLM scores are
    not independent human labels. Historical PCTY evaluation, if present, remains development.
    """)
    code(r'''
    review=read_csv(PREFIX+'evaluation/blind_human_review.csv',dtype=str,keep_default_na=False)
    review_metrics=[]
    validation_stages=pd.DataFrame([
        {'Stage':'Deterministic source checks','Observed evidence':f'{ic_literal_quote_checks} exact IC quotation/hash checks; profile eligibility safeguards',
         'What it establishes':'Saved text/provenance consistency; not scope completeness or semantic truth'},
        {'Stage':'Agent source-based case review','Observed evidence':f'{len(ic_reviews)} provisional baseline pair rationales',
         'What it establishes':'Inspectible overlap, material differences and unknowns; not independent labels'},
        {'Stage':'Local model comparison','Observed evidence':f'{len(forward_judgments)} distinct forward pair records',
         'What it establishes':'Provisional model output with logged failures; not independent relevance accuracy'},
        {'Stage':'Independent human review','Observed evidence':f'{human_labels_new} new labels recorded',
         'What it establishes':'Only named, separately supplied judgments count; unfinished fields remain unknown'},
        {'Stage':'New locked-design batch','Observed evidence':'Not yet evaluated',
         'What it establishes':'Required after current source-informed development before generalization claims'},
    ])
    table(validation_stages)
    if not review.empty:
        for target in target_ids:
            target_review=review[review.target_id.eq(target)]
            if target_review.candidate_id.duplicated().any():
                raise ValueError('Multiple reviewer rows require an explicit adjudication table; do not silently take the last grade')
            # Legacy pooled CSV is a template, never an independent-label submission path.
            labels={row.candidate_id:None for row in target_review.itertuples()}
            pool=list(labels)
            for method in methods:
                peers=ordered.get((target,method),[])
                # Every top-10 must enter the common pool before method comparison.
                if not set(peers[:10]).issubset(set(pool)):
                    review_metrics.append({'target_id':target,'method':method,'status':'review_pool_missing_returned_peers'})
                    continue
                metric=evaluation.common_pool_metrics(peers,labels,pool_ids=pool,k=5)
                metric10=evaluation.common_pool_metrics(peers,labels,pool_ids=pool,k=10)
                review_metrics.append({'target_id':target,'method':method,'human_precision_at5':None,'missing_output_slots':metric['missing_output_slots'],
                    'precision_lower':metric['precision_lower'],'precision_upper':metric['precision_upper'],
                    'judgment_coverage':metric['judgment_coverage_at_k'],
                    'human_pooled_ndcg_at10':None,'status':'awaiting_validated_independent_adjudication'})
        named=review.reviewer_name.astype(str).str.strip().ne('')
        graded=review.whole_company_grade.astype(str).str.strip().ne('')
        display(Markdown(f'**Human review status:** {len(review):,} pooled pairs; '
            f'{int((named & graded).sum()):,} legacy template rows contain a name and grade; these are not accepted metric labels. '
            f'The experiment status records {human_labels_new} new independent labels.'))
        table(review[['pair_id','target','candidate','target_url','candidate_url','reviewer_name','whole_company_grade']],rows=12)
    human_metrics=pd.DataFrame(review_metrics)
    if not human_metrics.empty: table(human_metrics,rows=15)
    review_template_paths=[PREFIX+f'comparison/reviewer_{i}_template.csv' for i in (1,2)]
    if hasattr(package,'experiment_comparison') and any(name in FILES for name in review_template_paths):
        independent_records=[]
        for name in review_template_paths:
            if name in FILES:independent_records+=read_csv(name,dtype=str,keep_default_na=False).to_dict('records')
        expected_pairs=review.pair_id.tolist()
        validated_human=package.experiment_comparison.validate_reviews(independent_records,actor_type='human',allowed_pair_ids=expected_pairs)
        actual_roster=read_json(PREFIX+'comparison/reviewer_roster.json',{}).get('reviewer_names',[])
        valid_names=len(actual_roster)==2 and all(actual_roster) and len(set(actual_roster))==2
        agreement_recomputed=package.experiment_comparison.weighted_cohen_kappa(independent_records,reviewer_names=actual_roster,
            expected_pair_ids=expected_pairs) if valid_names else {'status':'awaiting_two_actual_named_independent_reviewers','kappa':None}
        table(pd.DataFrame([{'Review records':len(validated_human),'Pending':sum(r['pending'] for r in validated_human),
            'Submitted unknown':sum(not r['pending'] and r['grade'] is None for r in validated_human),
            'Known unadjudicated grades':sum(r['grade'] is not None for r in validated_human),
            'Agreement status':agreement_recomputed['status'],'Quadratic Cohen kappa':agreement_recomputed['kappa']}]))
        if valid_names:
            reviewer_maps=[{r['pair_id']:r['grade'] for r in validated_human
                if r['reviewer_name']==name and not r['pending']} for name in actual_roster]
            agreed={pair:reviewer_maps[0][pair] for pair in expected_pairs
                if reviewer_maps[0].get(pair) is not None and reviewer_maps[0].get(pair)==reviewer_maps[1].get(pair)}
            agreed_metrics=[]
            for target in target_ids:
                pool_rows=review[review.target_id.eq(target)]
                labels={r.candidate_id:agreed.get(r.pair_id) for r in pool_rows.itertuples()}
                for method in methods:
                    peers=ordered.get((target,method),[])
                    metrics=evaluation.common_pool_metrics(peers,labels,pool_ids=list(labels),k=5)
                    ndcg=evaluation.common_pool_metrics(peers,labels,pool_ids=list(labels),k=10)
                    agreed_metrics.append({'target_id':target,'method':method,
                        'independent_agreed_precision_at5':metrics['precision_at_k'] if metrics['judged_top_count'] else None,
                        'independent_agreed_pooled_ndcg_at10':ndcg['pooled_ndcg'],
                        'judged_returned_count':metrics['judged_top_count'],'missing_output_slots':metrics['missing_output_slots'],
                        'status':metrics['status']})
            table(pd.DataFrame(agreed_metrics),rows=15)
            display(Markdown('Only two independently submitted, structurally validated, identical known grades enter this agreement-only analysis. Disagreements and unknowns await explicit reconciliation; the common pool remains the denominator. No-return cases do not receive a human precision score.'))
        rubric=FILES.get(PREFIX+'comparison/HUMAN_REVIEW_RUBRIC.txt')
        if rubric:display(HTML('<details><summary>Independent reviewer instructions and frozen rubric</summary><pre style="white-space:pre-wrap">'+html.escape(rubric.decode('utf-8-sig'))+'</pre></details>'))
        display(Markdown('Human initials must be independently submitted before reconciliation. These unadjudicated records are separate from model scores and purposive agent challenges; agreement is not correctness.'))
    for report in ['agent_review_stage.json','ai_review_validation.json']:
        value=read_json(PREFIX+'comparison/'+report,{})
        if value:display(HTML('<details><summary>'+html.escape(report)+' — separate provisional assessment stage</summary><pre>'+html.escape(json.dumps(value,indent=2))+'</pre></details>'))
    historical_labels=read_csv('team/scraps/comps_first_pass/peer_labels.csv',dtype=str,comment='#')
    historical_recomputed=[]
    if not historical_labels.empty:
        display(Markdown('### Historical PCTY development labels and legacy reproduction'))
        table(historical_labels,rows=30)
        for target_ticker, group in historical_labels.groupby('target'):
            target_matches=[cid for cid in target_ids if str(F.loc[cid,'target_ciq_ticker'])==str(target_ticker)]
            if len(target_matches)!=1: continue
            target=target_matches[0]
            if group.peer.duplicated().any(): raise ValueError('Duplicate historical peer labels require adjudication')
            grades=dict(zip(group.peer.astype(str),pd.to_numeric(group.grade,errors='raise').astype(int)))
            # Reproduce comps_similarity.ndcg_at_k exactly: unlabeled=0, gain=2**grade-1,
            # and one ideal denominator from all historical labels (including unavailable peers).
            for method in methods:
                peers=ordered.get((target,method),[])
                ticker_order=[str(F.loc[cid,'target_ciq_ticker']) for cid in peers]
                legacy={}
                for k in (10,20):
                    dcg=sum((2**grades.get(t,0)-1)/np.log2(r+2) for r,t in enumerate(ticker_order[:k]))
                    ideal=sum((2**g-1)/np.log2(r+2) for r,g in enumerate(sorted(grades.values(),reverse=True)[:k]))
                    legacy['legacy_closed_world_ndcg_at'+str(k)]=dcg/ideal if ideal else np.nan
                for k in (10,25):
                    legacy['historical_list_recall_at'+str(k)]=len(set(ticker_order[:k])&set(grades))/len(grades)
                common_pool=list(dict.fromkeys([str(F.loc[cid,'target_ciq_ticker'])
                    for cid in rankings.loc[rankings.target_id.eq(target),'candidate_id'].unique()]+list(grades)))
                if len(ticker_order)!=len(set(ticker_order)):
                    raise ValueError('Historical ticker mapping is ambiguous; do not silently merge company identities')
                unknown=evaluation.common_pool_metrics(ticker_order,grades,pool_ids=common_pool,k=5,max_grade=2)
                historical_recomputed.append({'target':target_ticker,'method':method,**legacy,
                    'unknown_default_precision_at5':unknown['precision_at_k'],
                    'unknown_default_precision_lower':unknown['precision_lower'],
                    'unknown_default_precision_upper':unknown['precision_upper'],
                    'historical_judgment_coverage_at5':unknown['judgment_coverage_at_k'],
                    'status':'historical_development_only'})
        historical_recomputed=pd.DataFrame(historical_recomputed)
        table(historical_recomputed,rows=100)
        historical_global_recomputed=[]
        if candidate_pool and not global_controls.empty:
            for target_ticker,group in historical_labels.groupby('target'):
                matching=[cid for cid in target_ids if str(F.loc[cid,'target_ciq_ticker'])==str(target_ticker)]
                if len(matching)!=1:continue
                grades=dict(zip(group.peer.astype(str),pd.to_numeric(group.grade,errors='raise').astype(int)))
                for method,rows in global_controls[global_controls.target_id.eq(matching[0])].groupby('method'):
                    rows=rows[as_bool(rows.available)].sort_values(['rank','candidate_id'])
                    ticker_order=[str(F.loc[cid,'target_ciq_ticker']) for cid in rows.candidate_id]
                    record={'target':target_ticker,'method':method,'scope':'original_global_control'}
                    for k in (10,20):
                        dcg=sum((2**grades.get(t,0)-1)/np.log2(r+2) for r,t in enumerate(ticker_order[:k]))
                        ideal=sum((2**g-1)/np.log2(r+2) for r,g in enumerate(sorted(grades.values(),reverse=True)[:k]))
                        record['legacy_closed_world_ndcg_at'+str(k)]=dcg/ideal if ideal else np.nan
                    for k in (10,25):record['historical_list_recall_at'+str(k)]=len(set(ticker_order[:k])&set(grades))/len(grades)
                    historical_global_recomputed.append(record)
            historical_global_recomputed=pd.DataFrame(historical_global_recomputed)
            display(Markdown('**Original full-universe historical reproduction, kept separate from active-pilot ranks:**'))
            table(historical_global_recomputed,rows=100)
        saved_development=read_csv(PREFIX+('global-controls/core/' if candidate_pool else 'core/')+'pcty_development_metrics.csv')
        comparison_history=historical_global_recomputed if candidate_pool else historical_recomputed
        if not saved_development.empty and len(comparison_history):
            matched=comparison_history.merge(saved_development,on='method',validate='one_to_one')
            for generated,saved in [
                ('legacy_closed_world_ndcg_at10','NDCG@10'),
                ('legacy_closed_world_ndcg_at20','NDCG@20'),
                ('historical_list_recall_at10','Recall@10'),
                ('historical_list_recall_at25','Recall@25')]:
                if saved in matched:
                    np.testing.assert_allclose(matched[generated],matched[saved],rtol=1e-10,atol=1e-10,equal_nan=True)
            display(Markdown(f'**Historical reproduction check:** {len(matched)} method rows matched '
                             'the saved development metrics under the team convention.'))
        display(Markdown('The legacy nDCG columns deliberately reproduce the team convention that unlabeled '
            'companies receive zero relevance. That closed-world assumption is not an exhaustive ground truth. '
            'The separate unknown-default bounds retain missing judgments. Recall here means recovery of the '
            'historical list, not recovery of every real peer. None of these labels is a new independent test.'))
    historical_paths=[name for name in FILES if name.startswith(PREFIX) and
        ('pcty' in name.lower() or 'historical' in name.lower()) and name.endswith(('.csv','.json'))]
    if historical_paths:
        display(Markdown('**Embedded historical development artifacts:** '+', '.join(name.removeprefix(PREFIX) for name in historical_paths)))
        for name in historical_paths:
            display(Markdown('**Saved artifact:** `'+name.removeprefix(PREFIX)+'`'))
            value=read_csv(name) if name.endswith('.csv') else pd.DataFrame([read_json(name)])
            table(value,rows=20)
        display(Markdown('These historical summaries are saved development diagnostics, not newly created independent labels.'))
    ''')
    md("""
    ## 9. Growth preparation and remaining dependencies

    The longer proposal requires dated qualitative signals, observable subsequent three-year
    outcomes, time-aware validation, benchmark comparisons and empirical coverage of 80%
    intervals. Current website captures cannot reconstruct the historical information set.
    Hiring, capacity, acquisitions and market-expansion statements require source dates,
    entity attribution and an explicit mechanism; marketing optimism is not a numeric forecast.

    A future controlled design can compare peer growth, own historical growth, financial-only
    regularized prediction, the same learner plus dated qualitative signals, and nonlinear
    challengers. Acquisition-adjusted and reported growth require separate definitions. Rolling
    forecast origins must include only outcomes already observable at each training origin.
    [Conformalized quantile regression](https://proceedings.neurips.cc/paper_files/paper/2019/file/5103c3584b063c431bd1268e9b5e76fb-Paper.pdf)
    supplies an interval method under exchangeability; that assumption cannot be silently carried
    into dependent or shifting company histories. No such forecast or calibrated interval is
    manufactured in this matching/valuation pilot.
    """)
    code(r'''
    growth_contract=read_json(PREFIX+'growth-readiness/contract.json',{})
    growth_synthetic=read_json(PREFIX+'growth-readiness/synthetic_validation.json',{})
    growth_artifacts=sorted(name for name in FILES if name.startswith(PREFIX+'growth-integration/'))
    if growth_contract:
        display(Markdown('**Readiness contract:** source/date/attribution checks and outcome interfaces; '
                         'software safeguards, not measured growth predictability.'))
        table(pd.DataFrame(growth_contract.get('interfaces',[])),rows=20)
        if growth_synthetic:
            table(pd.DataFrame([{k:growth_synthetic.get(k) for k in
                ['data_class','tests_run','failures','errors','passed']}]))
        if not growth_artifacts:
            table(pd.DataFrame(growth_contract.get('missing_inputs',[])),rows=20)
    if growth_artifacts:
        display(Markdown('**Latest team-growth integration artifacts are embedded.** '
            'The earlier readiness contract predates this integration; its adapter-status notes '
            'must not be treated as the latest execution status.'))
        status=read_json(PREFIX+'growth-integration/integration_status.json',{})
        table(pd.DataFrame([{key:status.get(key) for key in ['team_revision','selected_articles',
            'usable_articles','original_rule_event_records','current_strict_event_records',
            'integration_validation_passed','forecasts_produced','forecast_status']}]))
        growth_scope=read_json(PREFIX+'growth-integration/source_scope_audit.json',{})
        for case in growth_scope.get('cases',[]):
            display(Markdown('**'+case['case_id']+' — provisional source review.** '+case['assessment']+
                '\n\n'+case.get('future_or_historical_limit',case.get('scope_distinction',''))+
                '\n\n[Official source]('+case['source_url']+').'))
        if growth_scope.get('blocked_cases'): table(pd.DataFrame(growth_scope['blocked_cases']))
        for name in ['integration_status.json','integration_validation.json','event_validation.json',
                     'extraction_audits.json','required_source_manifest.json']:
            value=read_json(PREFIX+'growth-integration/'+name,{})
            display(HTML('<details><summary>'+html.escape(name)+'</summary><pre>'+
                         html.escape(json.dumps(value,indent=2))+'</pre></details>'))
        display(Markdown('Event extraction and feature assembly are separate from dated outcome validation. '
                         'No historical forecast accuracy or calibrated company interval is inferred from a successful pipeline run.'))
    ''')
    code(r'''
    # Recompute original and evidence-gated event features in memory, without network or writes.
    growth_recomputed=[]
    if PREFIX+'growth-integration/mapped_events.json' in FILES:
        from datetime import datetime
        from urllib.parse import urlsplit
        def load_growth_source(module_name,source_name):
            module=types.ModuleType(module_name);module.__file__='embedded://'+source_name
            sys.modules[module_name]=module
            exec(compile(FILES[source_name],module.__file__,'exec'),module.__dict__)
            return module
        growth_schema=load_growth_source('embedded_growth_schema','team-growth/growth_signals/schema.py')
        previous_schema=sys.modules.get('schema')
        try:
            sys.modules['schema']=growth_schema
            growth_features=load_growth_source('embedded_growth_features','team-growth/growth_signals/build_features.py')
        finally:
            if previous_schema is None: sys.modules.pop('schema',None)
            else: sys.modules['schema']=previous_schema
        growth_gates=load_growth_source('embedded_growth_gates','project/src/modular_validation/growth_readiness.py')
        capture=read_json(PREFIX+'growth-integration/capture_manifest.json')
        growth_freeze=read_json(PREFIX+'growth-integration/config_freeze.json')
        mapped=read_json(PREFIX+'growth-integration/mapped_events.json')
        original_events=[growth_schema.Event.from_dict(e) for e in read_json(PREFIX+'growth-integration/original_events.json')]
        texts={}
        for case in capture['cases']:
            if case['status']!='usable': continue
            page=read_json(PREFIX+'growth-integration/captures/'+case['case_id']+'/page_record.json')['pages'][0]
            texts['source:'+case['case_id']]='\n'.join([page['raw_title'],page['raw_meta'],*page['raw_blocks']])
        domains=sorted({urlsplit(c['url']).hostname for c in capture['cases']})
        recomputed_feature_snapshots=[]
        for arm,cutoff in [('retrospective_without_archive_proof',growth_freeze['retrospective_cutoff']),
                           ('current_capture',capture['captured_at_utc'])]:
            cutoff_time=datetime.fromisoformat(cutoff.replace('Z','+00:00'));cutoff_day=cutoff_time.date()
            control=growth_features.build_company_features(original_events,cutoff_day)
            checked=growth_gates.validate_event_batch(mapped,cutoff=cutoff,company_role='target',
                regime='website_only',allowed_domains=domains,evidence_texts=texts)
            included=set(checked['included_event_ids']);adjusted=[]
            for event in mapped:
                if event['event_id'] in included:
                    row=dict(event['original_event']);row['signal_duration']=event['signal_duration']
                    adjusted.append(growth_schema.Event.from_dict(row))
            strict=growth_features.build_company_features(adjusted,cutoff_day)
            recomputed_feature_snapshots.append({'arm':arm,'cutoff':cutoff,'team_features':control,'strict_features':strict})
            control_by={r['IQ_COMPANY_ID']:r for r in control};strict_by={r['IQ_COMPANY_ID']:r for r in strict}
            for cid in sorted({c['company_id'] for c in capture['cases']}):
                cases=[c for c in capture['cases'] if c['company_id']==cid]
                available=sum(c['status']=='usable' and datetime.fromisoformat(c['capture']['completed_at_utc'])<=cutoff_time for c in cases)
                growth_recomputed.append({'arm':arm,'cutoff':cutoff,'company_id':cid,'ticker':cases[0]['ticker'],
                    'attempted_articles':len(cases),'usable_current_articles':sum(c['status']=='usable' for c in cases),
                    'proven_available_articles_at_cutoff':available,
                    'coverage_status':'purposive_partial_coverage' if available else 'no_proven_available_sources',
                    'team_feature_row_emitted':cid in control_by,
                    'team_rule_events_365d':control_by.get(cid,{}).get('evidence_365d_count'),
                    'strict_supported_events_365d':strict_by.get(cid,{}).get('evidence_365d_count',0) if available else None,
                    'strict_temporary_launches_365d':strict_by.get(cid,{}).get('product_launch_temporary_365d_count',0) if available else None,
                    'strict_durable_launches_365d':strict_by.get(cid,{}).get('product_launch_durable_365d_count',0) if available else None,
                    'strict_unknown_duration_launches_365d':strict_by.get(cid,{}).get('product_launch_unknown_duration_365d_count',0) if available else None,
                    'zero_definition':'No eligible extracted event in these selected available pages, never evidence of no company growth.'})
        assert recomputed_feature_snapshots==read_json(PREFIX+'growth-integration/feature_outputs.json'), 'Growth feature replay differs'
        assert growth_recomputed==read_json(PREFIX+'growth-integration/feature_comparison.json'), 'Growth availability replay differs'
        growth_comparison=pd.DataFrame(growth_recomputed)
        table(growth_comparison[['arm','ticker','usable_current_articles','proven_available_articles_at_cutoff',
            'team_rule_events_365d','strict_supported_events_365d','coverage_status']],rows=20)
        display(Markdown('**Offline recalculation passed:** original and strict event features match the recorded outputs. '
            'Null means unavailable evidence; zero, where permitted, means no eligible extracted event in these selected pages. '
            'Neither means zero company growth. A rule confidence of 0.80 is a constant score, not a calibrated probability.'))
    ''')
    md("""

    ## 10. Conclusions and integration checklist

    The experiment supports inspection of actual method outputs, availability, disagreements,
    activity evidence and paired snapshot financial comparisons. It does not turn agreement or
    a low financial proxy error into validated whole-company accuracy. The required independent
    human review and date/definition alignment remain explicit gates. Methods with unavailable
    prerequisites remain in the ledger rather than disappearing from the scope of work.

    Before promotion into the team pipeline, retain the frozen design, source hashes, method
    versions, intermediate outputs and failure states; complete named human review; resolve
    financial definitions/dates; and evaluate subsequent changes on unused targets. Keep the
    public API modules reusable and this notebook as the reader-facing report. No push, upload,
    external message or new model-service call is performed by default execution.
    """)
    code(r'''
    conclusion_status=pd.DataFrame([
        ('Methods with saved company ranking rows',len(methods)),
        ('Frozen target cases',len(target_ids)),
        ('Newly selected cases (also development)',int(targets.role.eq('fresh_pilot').sum())),
        ('Untouched end-to-end test cases',0),
        ('Recomputed valuation rows',len(valuation)),
        ('Strict eligible indications',int(valuation.strict_indication_status.eq('eligible_unreviewed').sum())),
        ('New independent human labels reported',human_labels_new),
        ('Completed aligned-date valuation backtest',False),
        ('Completed historical growth/interval validation',False),
        ('Default inference mode','Saved model outputs, explicitly identified'),
        ('Default reanalysis','Metrics and peer aggregation recomputed from embedded inputs'),
    ],columns=['Audit item','Actual status'])
    table(conclusion_status)
    stage_records=[read_json(name) for name in sorted(FILES)
                   if name.startswith(PREFIX+'stage-execution/') and name.endswith('.json')]
    if stage_records:
        stage_runtime=pd.DataFrame(stage_records)
        table(stage_runtime[['stage','elapsed_seconds','exit_code','runtime_scope']],rows=20)
        display(Markdown('Recorded wall times include stage loading and reflect this machine and cache state. '
            'Shared extraction is not assigned repeatedly to each ranker, and these are not production per-query latency estimates.'))
    if result_interpretation.get('next_steps'):
        display(Markdown('**Next actions:**\n\n'+'\n'.join('- '+str(x) for x in result_interpretation['next_steps'])))
    ''')
    md("""
    ## Appendix A. Full implementation and one-file reproducibility

    The archive contains the implementation, frozen configuration, source snapshot, website
    JSON evidence, cached model outputs and active-pilot feature arrays, and synthetic safeguard tests.
    The recomputable original full-universe feature arrays are omitted to keep the single file
    practical; their metadata, source inputs and complete original rankings remain embedded.
    The complete source is readable below. Model weights are deliberately not embedded; heavy
    inference additionally requires the pinned models and suitable hardware. Default Run All
    neither downloads models nor repeats inference.

    The optional exporter below writes a new workspace only when explicitly enabled and refuses
    an existing destination. It preserves the original archive and creates a separate
    `rerun-project` with a rebased `team_root`, fresh output directory, and a command runner.
    This reruns matching and valuation from the embedded source snapshot; it does not recrawl
    websites or turn the original capture into a new historical observation. The runner prints
    its plan unless called with `--run`.

    To repeat heavy inference, install the recorded dependencies and make the pinned MPNet and
    Qwen model files available in the local Hugging Face cache. The recorded inference code
    expects a compatible CUDA runtime. Then run
    `python rerun-project/rerun_workflow.py --run` from the exported directory. No model download,
    service API call or full inference happens during standard notebook Run All. A rerun records
    a new design hash and execution manifests; numerical/environment differences are not hidden.
    """)
    code(r'''
    source_names=sorted(name for name in FILES if name.startswith(('project/','team/','team-growth/')) and name.endswith('.py'))
    for name in source_names:
        source=FILES[name].decode('utf-8-sig')
        display(HTML('<details><summary>'+html.escape(name.removeprefix('project/'))+
                     '</summary><pre style="white-space:pre-wrap">'+html.escape(source)+'</pre></details>'))
    display(HTML('<details><summary>Recorded dependency versions</summary><pre>'+html.escape(FILES['requirements-embedded.txt'].decode())+'</pre></details>'))
    display(Markdown(f'**Embedded archive SHA-256:** `{PAYLOAD_SHA256}`. '
        'Each member also has an independently checked SHA-256 in `payload_manifest`.'))
    ''')
    code(r'''
    EXPORT_WORKSPACE = False  # Explicit opt-in only; default Run All creates no files.
    def export_workspace(directory):
        from pathlib import Path, PurePosixPath
        from datetime import datetime, timezone
        destination=Path(directory).resolve()
        if destination.exists(): raise FileExistsError('Choose a new empty workspace; existing files are never overwritten')
        for name in FILES:
            part=PurePosixPath(name)
            if part.is_absolute() or '..' in part.parts: raise ValueError('Unsafe archive member')
        destination.mkdir()
        for name,data in FILES.items():
            path=destination.joinpath(*PurePosixPath(name).parts)
            path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
        rerun=destination/'rerun-project'
        for name,data in FILES.items():
            if name.startswith(('project/src/','project/scripts/','project/tests/','project/config/')):
                path=rerun.joinpath(*PurePosixPath(name.removeprefix('project/')).parts)
                path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
        rerun_out=rerun/'outputs-local/modular-validation'
        rerun_out.mkdir(parents=True,exist_ok=False)
        relocated=json.loads(json.dumps(design))
        relocated.update(team_root=str(destination/'team'),
            rerun_parent_design_sha256=hashlib.sha256(FILES[PREFIX+'design_freeze.json']).hexdigest(),
            rerun_parent_payload_sha256=PAYLOAD_SHA256,
            relocation_note='Only source-root location changed; frozen target selection retained. Original output seals are preserved separately.',
            relocation_utc=datetime.now(timezone.utc).isoformat())
        (rerun_out/'design_freeze.json').write_text(json.dumps(relocated,indent=2),encoding='utf-8')
        (rerun_out/'parameters.json').write_bytes(FILES[PARAMETER_PATH])
        if candidate_pool:
            (rerun_out/'candidate_pool_freeze.json').write_bytes(FILES[PREFIX+'candidate_pool_freeze.json'])
        (rerun/'requirements-embedded.txt').write_bytes(FILES['requirements-embedded.txt'])
        runner="""\"\"\"Opt-in local re-execution from embedded, immutable source evidence.\"\"\"
        import argparse, hashlib, json, os, shutil, subprocess, sys
        from pathlib import Path
        
        ROOT=Path(__file__).resolve().parent
        OUT=ROOT/'outputs-local/modular-validation'
        
        def main():
            parser=argparse.ArgumentParser(description=__doc__)
            parser.add_argument('--run',action='store_true',help='Execute local CPU/GPU inference; requires pinned dependencies and cached model weights')
            args=parser.parse_args()
            steps=['core representations/rankings and explicit fixed-pool restriction',
                   'local profile extraction on the frozen comparison scope',
                   'canonical literal/source validation','profile/transport/sector rankings',
                   'declared factor-family arms',
                   'local whole-company pair comparisons','freeze rankings and evaluate','direct valuation challengers']
            print('Local rerun plan:',*steps,sep='\\n  ')
            if not args.run:
                print('Dry plan only. Add --run after installing requirements and caching the recorded model revisions.')
                return
            if (OUT/'evaluation/all_rankings_freeze.json').exists():
                raise FileExistsError('This rerun is already sealed; export into another fresh directory for another experiment.')
            env=os.environ.copy()
            env.update(PYTHONHASHSEED='4511',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',
                       QUAL2CAST_EXPERIMENT_DIR=str(OUT))
            def run(script,*arguments):
                subprocess.run([sys.executable,str(ROOT/'scripts'/script),*map(str,arguments)],
                               cwd=ROOT,env=env,check=True)
            run('run_modular_validation.py','core')
            design_path=OUT/'design_freeze.json'
            design=json.loads(design_path.read_text(encoding='utf-8'))
            scope=OUT/'candidate_pool_freeze.json'
            if scope.exists():
                import pandas as pd
                pool=json.loads(scope.read_text(encoding='utf-8'))
                ids=set(pool['company_ids'])
                if ids!=set(design['pilot_company_ids']):raise RuntimeError('Pool/design mismatch')
                full=OUT/'global-controls/core'
                shutil.copytree(OUT/'core',full)
                ranking_path=OUT/'core/rankings.csv'
                ranking=pd.read_csv(ranking_path)
                ranking=ranking[ranking.candidate_id.isin(ids)].copy()
                ranking['rank']=pd.NA
                for _,group in ranking.groupby(['target_id','method']):
                    valid=group[group.available.astype(str).str.lower().isin(['true','1'])].sort_values(['score','candidate_id'],ascending=[False,True],kind='stable')
                    ranking.loc[valid.index,'rank']=range(1,len(valid)+1)
                ranking.to_csv(ranking_path,index=False)
                for name in ['text_coverage.csv','company_identifiers.csv']:
                    frame=pd.read_csv(OUT/'core'/name,dtype=str)
                    frame[frame.IQ_COMPANY_ID.isin(ids)].to_csv(OUT/'core'/name,index=False)
                # Only provenance is rebased; the fixed candidate membership is never reselected.
                pool['rerun_parent_pool_sha256']=hashlib.sha256(scope.read_bytes()).hexdigest()
                pool['selection_reference_core_rankings_sha256']=pool['original_core_rankings_sha256']
                pool['original_core_rankings_sha256']=hashlib.sha256((full/'rankings.csv').read_bytes()).hexdigest()
                pool['rerun_membership_reselected']=False
                scope.write_text(json.dumps(pool,indent=2),encoding='utf-8')
                design['candidate_pool_sha256']=hashlib.sha256(scope.read_bytes()).hexdigest()
                design['rerun_scope_note']='Fixed original IDs retained; provenance rebased to rerun global controls, without target outcomes or candidate reselection.'
                design_path.write_text(json.dumps(design,indent=2),encoding='utf-8')
            extraction=['--design',design_path,'--output',OUT/'profile-cache','--execution-batch-size','8']
            if scope.exists():extraction+=['--scope-freeze',scope]
            run('build_local_profiles.py',*extraction)
            maps=list((OUT/'profile-cache').glob('*/all_profiles.json'))
            if len(maps)!=1: raise RuntimeError('Expected one completed profile-extraction map')
            cache=maps[0].parent
            validated=cache/'all_profiles_validated.json'
            validation=[cache]
            if scope.exists():validation+=['--scope-freeze',scope]
            if scope.exists() and (ROOT/'scripts/prepare_profile_repairs.py').exists():
                repair_scope=OUT/'repair_scope_freeze.json'
                run('prepare_profile_repairs.py',cache,'--scope-freeze',scope,'--output',repair_scope)
                repair_ids=json.loads(repair_scope.read_text(encoding='utf-8'))['company_ids']
                if repair_ids:
                    run('build_local_profiles.py','--design',design_path,'--output',OUT/'profile-repairs',
                        '--scope-freeze',repair_scope,'--max-new-tokens','4096','--execution-batch-size','8')
                    repair_maps=list((OUT/'profile-repairs').glob('*/all_profiles.json'))
                    if len(repair_maps)!=1:raise RuntimeError('Expected one uniform technical repair map')
                    validation+=['--repair-cache',repair_maps[0].parent]
            if not validated.exists(): run('validate_local_profiles.py',*validation)
            run('run_modular_validation.py','profiles','--profiles',validated)
            if design.get('additional_factor_methods'):run('run_factor_ablation.py',validated)
            run('run_local_peer_judgments.py',validated)
            if 'local_llm_derived_activity_ledger' in design.get('methods_predeclared',[]):run('run_local_peer_judgments_v2.py',validated)
            run('evaluate_modular_validation.py')
            run('run_direct_valuation.py')
            if (ROOT/'scripts/build_experiment_comparison.py').exists():run('build_experiment_comparison.py')
            print('Completed new local matching/valuation run:',OUT)
            print('Independent human approval and historical growth validation were not created by this execution.')
        
        if __name__=='__main__': main()
        """
        import textwrap
        first_line, remaining = runner.split("\n", 1)
        runner = first_line + "\n" + textwrap.dedent(remaining)
        (rerun/'rerun_workflow.py').write_text(runner,encoding='utf-8')
        (destination/'EXPORT_README.txt').write_text(
            'Original archive: project/ and team/. Fresh model rerun: rerun-project/.\\n'
            'Install rerun-project/requirements-embedded.txt and cache recorded model revisions locally.\\n'
            'Preview: python rerun-project/rerun_workflow.py\\n'
            'Run: python rerun-project/rerun_workflow.py --run\\n'
            'No original rankings, seals or financial outputs are copied into the new run directory.\\n'
            'A pilot rerun retains the fixed original candidate IDs; it recomputes global controls and explicitly restricts candidate rows.\\n'
            'Only provenance hashes are rebased after that stage; no candidate or factor choice is selected using target outcomes.\\n'
            'Optional offline growth replay (writes only integration diagnostics in the exported project):\\n'
            'python project/scripts/integrate_team_growth.py analyze --team-root team-growth\\n'
            'The team-growth source is separately versioned; it does not replace the frozen matching corpus.\\n'
            'Default notebook execution remains entirely in memory and offline.\\n',encoding='utf-8')
        return destination
    if EXPORT_WORKSPACE:
        print('Exported source/data workspace:',export_workspace('modular_validation_workspace'))
    ''')
    md("""
    ## Appendix B. Prior research evidence and source limitations

    These evidence cards are carried forward from the October 18 literature review. Their
    publication metrics describe the cited studies, not this pilot. “Grade A” denotes empirical
    company-peer research; B denotes a preprint/related-task precedent; C denotes official
    product documentation or a vendor case. None supplies independent labels for these ten
    targets. Historical or preliminary source status remains unchanged by our local runs.
    """)
    md(research_cards())
    md("""
    ## Appendix C. Factor and evaluation research contracts

    The following local research records define candidate factors, their source support,
    operational availability, and evaluation choices. A research-motivated factor is not a
    validated predictor. The experimental factor specification and observed outputs identify
    which proposals were actually run; the broader catalogue also records unavailable data.
    Academic, enterprise-vendor and investment-principle evidence retain their distinct limits.
    """)
    code(r'''
    for name in factor_research_files:
        record=read_json(name)
        title=name.removeprefix(FACTOR_RESEARCH_PREFIX)
        references=[]
        for source in record.get('sources',[]):
            url=safe_url(source.get('url'))
            label=source.get('title',source.get('citation',source.get('id','Primary source')))
            if url:references.append('<li><a href="'+html.escape(url,quote=True)+'">'+html.escape(str(label))+'</a></li>')
        if references:
            display(HTML('<details><summary>'+html.escape(title)+' — primary-source links</summary><ul>'+''.join(references)+'</ul></details>'))
        display(HTML('<details><summary>'+html.escape(title)+' — research evidence and limitations</summary><pre style="white-space:pre-wrap">'+
                     html.escape(json.dumps(record,ensure_ascii=False,indent=2))+'</pre></details>'))
    ''')
    md("""
    ## References for evaluation and data handling

    - [Statistics Canada: probability and stratified sampling](https://www150.statcan.gc.ca/n1/edu/power-pouvoir/ch13/prob/5214899-eng.htm).
    - [Cawley & Talbot (2010): selection overfitting and evaluation bias](https://jmlr.org/papers/v11/cawley10a.html).
    - [Geifman & El-Yaniv (2019): SelectiveNet and risk–coverage accounting](https://proceedings.mlr.press/v97/geifman19a.html).
    - [Liu, Nissim & Thomas (2002): Equity Valuation Using Multiples](https://business.columbia.edu/sites/default/files-efs/imce-uploads/dnissim/publications/Equity%20Valuation%20Using%20Multiples.pdf).
    - [SEC: EDGAR APIs and data structures](https://www.sec.gov/search-filings/edgar-application-programming-interfaces).
    - [Hyndman & Athanasopoulos: forecasting toolbox and time-series evaluation](https://otexts.com/fpp3/toolbox.html).

    Complete company-source URLs and retrieved source records are embedded in the payload;
    source links establish provenance, not endorsement or independent factual verification.
    """)
    nbformat.validate(nb)
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    nbformat.write(nb, destination)
    result={"notebook":str(destination),"cells":len(nb.cells),"bytes":destination.stat().st_size,
            "payload_files":len(manifest['files']),"payload_compressed_bytes":len(payload),
            "payload_sha256":sha(payload),"execution_status":"not_executed_by_builder"}
    print(json.dumps(result,indent=2))
    return result


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=DEFAULT_DESTINATION)
    parser.add_argument('--experiment-dir',type=Path,default=OUT,
                        help='Active sealed experiment; defaults to QUAL2CAST_EXPERIMENT_DIR or the legacy directory')
    args=parser.parse_args()
    build(args.output,experiment_dir=args.experiment_dir)
