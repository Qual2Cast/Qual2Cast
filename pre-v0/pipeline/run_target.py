"""Run one complete company analysis using existing cached inputs."""
import os
for key in ['OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS']:
    os.environ[key]='2'
import argparse,json
from datetime import datetime,timezone
from pathlib import Path
from pipeline.config import Configuration
from pipeline.workflow import CompanyWorkflow
from pipeline.company import analyze_company,report_html

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-root',type=Path,required=True)
    parser.add_argument('--target',default='PCTY')
    parser.add_argument('--config',type=Path)
    parser.add_argument('--output',type=Path,default=Path('outputs-local/company-workflow'))
    args=parser.parse_args()
    config=Configuration(**json.loads(args.config.read_text(encoding='utf-8'))) if args.config else Configuration()
    workflow,outcomes=CompanyWorkflow.from_snapshot(args.data_root)
    report=analyze_company(workflow,args.target,outcomes.set_index('IQ_COMPANY_ID').target_ev_to_ebitda,config)
    args.output.mkdir(parents=True,exist_ok=True)
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    safe_target=report.get('target','unresolved')
    path=args.output/(safe_target+'_'+config.key+'_'+stamp+'.json')
    path.write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
    print(path)
    path.with_suffix('.html').write_text(report_html(report),encoding='utf-8')
    print(json.dumps(report.get('assessment',report.get('identity')),indent=2))

if __name__=='__main__':main()
