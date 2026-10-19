"""Run one explicit pilot stage and retain wall time, exit status and its log."""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import hashlib
import json
import os
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(os.environ.get('QUAL2CAST_EXPERIMENT_DIR', ROOT / 'outputs-local/pilot-validation-2026-10-18'))
if not OUT.is_absolute():
    OUT = ROOT / OUT


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=['profiles', 'factors', 'llm', 'llm-v2', 'agent', 'evaluation', 'direct', 'comparison', 'figures'])
    args = parser.parse_args()
    mapping = {'profiles': ['run_modular_validation.py', 'profiles'],
               'factors': ['run_factor_ablation.py'], 'llm': ['run_local_peer_judgments.py'], 'llm-v2': ['run_local_peer_judgments_v2.py'],
               'agent': ['run_agent_assessment.py'], 'evaluation': ['evaluate_modular_validation.py'],
               'direct': ['run_direct_valuation.py'], 'comparison': ['build_experiment_comparison.py'],
               'figures': ['build_delivery_figures.py']}
    parts = mapping[args.stage]
    command = [sys.executable, '-X', 'utf8', str(ROOT / 'scripts/gentle_process_start.py'),
               str(ROOT / 'scripts' / parts[0]), *parts[1:]]
    if args.stage in {'profiles', 'factors', 'llm', 'llm-v2'}:
        maps = list((OUT / 'profile-cache').glob('*/all_profiles_validated.json'))
        if len(maps) != 1:
            raise RuntimeError('Expected one exact canonical pilot map')
        command += (['--profiles'] if args.stage == 'profiles' else []) + [str(maps[0])]
    folder = OUT / 'stage-execution'
    folder.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    log = folder / f'{args.stage}_{stamp}.log'
    record = {'stage': args.stage, 'command': command, 'started_at_utc': stamp,
              'script_sha256': hashlib.sha256((ROOT / 'scripts' / parts[0]).read_bytes()).hexdigest(),
              'log': str(log), 'runtime_scope': 'Whole stage wall time including loading; hardware/cache-specific, not per-query latency.'}
    env = os.environ.copy()
    env.update(QUAL2CAST_EXPERIMENT_DIR=str(OUT), HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', PYTHONHASHSEED='4511')
    start = time.monotonic()
    with log.open('w', encoding='utf-8') as stream:
        result = subprocess.run(command, cwd=ROOT, env=env, stdout=stream, stderr=subprocess.STDOUT)
    record.update(elapsed_seconds=time.monotonic() - start, exit_code=result.returncode,
                  completed_at_utc=datetime.now(timezone.utc).isoformat())
    log.with_suffix('.json').write_text(json.dumps(record, indent=2), encoding='utf-8')
    print(json.dumps(record, indent=2), flush=True)
    raise SystemExit(result.returncode)


if __name__ == '__main__':
    main()
