"""Execute one completed notebook offline in an empty directory and save proof."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import sys
import time
import uuid


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('notebook', type=Path)
    parser.add_argument('--experiment-dir', type=Path, required=True)
    args = parser.parse_args()
    import nbformat
    from nbclient import NotebookClient
    from jupyter_client import KernelManager
    from jupyter_client.kernelspec import KernelSpecManager
    from nbconvert import HTMLExporter
    from bs4 import BeautifulSoup

    path = args.notebook.resolve()
    root = Path(__file__).resolve().parents[1]
    out = args.experiment_dir.resolve()
    work = path.parent / 'notebook-verification' / uuid.uuid4().hex[:10]
    empty = work / 'empty'
    kernel = work / 'kernels' / 'whole-company-local'
    empty.mkdir(parents=True)
    kernel.mkdir(parents=True)
    (kernel/'kernel.json').write_text(json.dumps({'argv':[sys.executable,'-m','ipykernel_launcher','-f','{connection_file}'],
        'display_name':'Whole company local validation','language':'python'}),encoding='utf-8')
    design=json.loads((out/'design_freeze.json').read_text())
    forbidden=[str(root/name) for name in ['src','scripts','data-local','outputs-local']]+[design['team_root']]
    original=nbformat.read(path,as_version=4)
    original_hash=hashlib.sha256(path.read_bytes()).hexdigest()
    guard=nbformat.v4.new_code_cell('''import sys, os
_blocked_project_roots = '''+repr(forbidden)+'''
_blocked_project_roots = [os.path.normcase(os.path.abspath(p)) for p in _blocked_project_roots]
_forbidden_accesses=[]
def _audit_default_replay(event,args):
    if event in ('socket.connect','socket.getaddrinfo'):
        _forbidden_accesses.append((event,str(args)))
        raise RuntimeError('Offline verification forbids network access')
    if event=='open' and args and isinstance(args[0],(str,bytes,os.PathLike)):
        p=os.path.normcase(os.path.abspath(os.fsdecode(args[0])))
        if any(p==r or p.startswith(r+os.sep) for r in _blocked_project_roots):
            _forbidden_accesses.append((event,p))
            raise RuntimeError('Verification forbids external project companion reads')
sys.addaudithook(_audit_default_replay)
''')
    book=nbformat.from_dict(original)
    book.cells.insert(0,guard)
    book.cells.append(nbformat.v4.new_code_cell("assert not _forbidden_accesses, _forbidden_accesses\nprint('OFFLINE_ISOLATION_VERIFIED')"))
    manager=KernelManager(kernel_name='whole-company-local',kernel_spec_manager=KernelSpecManager(kernel_dirs=[str(work/'kernels')]))
    env=os.environ.copy()
    env.pop('PYTHONPATH',None)
    env.update(IPYTHONDIR=str(work/'ipython'), MPLCONFIGDIR=str(work/'matplotlib'),
               HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', OMP_NUM_THREADS='2',
               MKL_NUM_THREADS='2', OPENBLAS_NUM_THREADS='2')
    started=time.monotonic()
    client=NotebookClient(book,km=manager,timeout=300,allow_errors=False,resources={'metadata':{'path':str(empty)}})
    try:
        executed=client.execute(env=env)
    except Exception:
        # Retain failed proof separately; do not replace the canonical notebook.
        nbformat.write(book,work/'failed_execution.ipynb')
        raise
    assert not list(empty.iterdir()), 'Default replay wrote companion files'
    executed.cells=executed.cells[1:-1]
    for i,cell in enumerate((c for c in executed.cells if c.cell_type=='code'),1):
        cell.execution_count=i
    errors=[o for c in executed.cells for o in c.get('outputs',[]) if o.output_type=='error']
    assert not errors
    nbformat.validate(executed)
    nbformat.write(executed,path)
    exporter=HTMLExporter()
    exporter.exclude_input=True
    exporter.exclude_input_prompt=True
    exporter.exclude_output_prompt=True
    body,_=exporter.from_notebook_node(executed)
    soup=BeautifulSoup(body,'html.parser')
    for script in soup.find_all('script'):
        script.decompose()
    for link in soup.find_all('link',href=True):
        if link['href'].startswith(('http:','https:','//')):
            link.decompose()
    style=soup.new_tag('style')
    style.string='body{background:#f5f6f8!important}.jp-Notebook{max-width:1200px;margin:24px auto;background:white;padding:32px}h1,h2,h3{color:#153e59}h2{margin-top:36px;border-bottom:1px solid #d8e2e8;padding-bottom:8px}p,li{line-height:1.65}table{font-size:12px}details{margin:12px 0;padding:8px;background:#f8fafb}summary{cursor:pointer;font-weight:600}img{max-width:100%;height:auto}.jp-RenderedHTMLCommon{overflow-x:auto}pre{white-space:pre-wrap}'
    soup.head.append(style)
    html_path=path.with_suffix('.html')
    html_path.write_text(str(soup),encoding='utf-8')
    result={'status':'passed','executed_code_cells':sum(c.cell_type=='code' for c in executed.cells),
            'execution_errors':0,'inline_png_figures':sum('image/png' in o.get('data',{}) for c in executed.cells for o in c.get('outputs',[])),
            'empty_directory_execution':True,'network_attempts':0,'external_project_companion_reads':0,
            'companion_files_written':0,'input_notebook_sha256':original_hash,
            'executed_notebook_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
            'executed_notebook_bytes':path.stat().st_size,'html_preview':str(html_path),
            'elapsed_seconds':time.monotonic()-started,'proof_scope':'Implementation and offline reproduction, not independent business relevance or financial-date validity.'}
    (path.parent/'notebook_validation.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2),flush=True)


if __name__=='__main__':
    main()
