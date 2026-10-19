"""Bounded live DOM diagnostic on three predetermined official company pages.

This is a current-capture extraction comparison, never an October 17 snapshot
reconstruction or a ranking experiment. No authentication or anti-bot bypass.
"""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
from importlib import metadata
import json
from pathlib import Path
import re
import time
import unicodedata
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'outputs-local/modular-validation/live-cleaning-diagnostic'
UA='Qual2CastAcademicDiagnostic/1.0'
SITES=[
 {'ticker':'GTII','company_id':'IQ560549330','url':'https://gtigrows.com/our-story/',
  'reason':'Audited combined CPG/retailer definition and branded/retail activities.',
  'anchors':[
   {'id':'cpg_and_retail','phrase':'national consumer packaged goods company and retailer','meaning':'Both CPG and retail roles'},
   {'id':'brand_portfolio','phrase':'expansive brand portfolio','meaning':'Branded product portfolio'},
   {'id':'rise_retail','phrase':'As RISE expands into new communities our retail team','meaning':'RISE retail operation'}]},
 {'ticker':'DOX','company_id':'IQ24686','url':'https://www.amdocs.com/products-services',
  'reason':'Audited varied product/service catalog, including a wrongly removed consulting sentence.',
  'anchors':[
   {'id':'telco_platform','phrase':'agentic operating system for telecommunications','meaning':'Telecom platform'},
   {'id':'network_automation','phrase':'Telco grade open automation','meaning':'Network lifecycle automation'},
   {'id':'cloud_advisory','phrase':'Define a cloud strategy that aligns business technology and operating models','meaning':'Cloud advisory/consulting'},
   {'id':'mobile_wallet','phrase':'complete mobile wallet platform','meaning':'Financial-service software'},
   {'id':'content_services','phrase':'content strategy licensing rights and entertainment','meaning':'Content/OTT services'}]},
 {'ticker':'RIGL','company_id':'IQ33851','url':'https://www.rigel.com/products',
  'reason':'Audited product names visible in image/link metadata but absent from captured body blocks.',
  'anchors':[
   {'id':'veppanu','phrase':'VEPPANU','meaning':'Commercial product identity; indication not inferred'},
   {'id':'tavalisse','phrase':'TAVALISSE','meaning':'Commercial product identity; indication not inferred'},
   {'id':'rezlidhia','phrase':'REZLIDHIA','meaning':'Commercial product identity; indication not inferred'},
   {'id':'gavreto','phrase':'GAVRETO','meaning':'Commercial product identity; indication not inferred'}]}
]
METHODS=['bs4_body_text','bs4_body_with_image_alt','trafilatura_precision','trafilatura_recall','readability_lxml']
MARKERS=['privacy policy','privacy notice','privacy statement','terms of use','terms of service',
         'all rights reserved','cookie preferences','cookies','copyright','sign up','log in','login',
         'contact us','subscribe','newsletter','share on facebook','share on twitter','enable javascript']

def now(): return datetime.now(timezone.utc).isoformat()
def sha(value): return hashlib.sha256(value).hexdigest()
def write(path,obj): Path(path).write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def norm(text):
    text=unicodedata.normalize('NFKC',text).casefold()
    return ' '.join(re.findall(r'\w+',text,flags=re.UNICODE))

def http_get(url,path,byte_limit):
    """One request attempt, redirects recorded, no retries, cookies or auth reuse."""
    import requests
    started=now(); tick=time.monotonic()
    log={'requested_url':url,'started_at_utc':started,'user_agent':UA,'attempts':1,
         'maximum_bytes':byte_limit,'timeout_connect_seconds':15,'timeout_read_seconds':30}
    try:
        with requests.Session() as s:
            s.max_redirects=5
            with s.get(url,headers={'User-Agent':UA,'Accept':'text/html,text/plain;q=0.9,*/*;q=0.1'},
                       timeout=(15,30),allow_redirects=True,stream=True) as r:
                log.update(status_code=r.status_code,final_url=r.url,content_type=r.headers.get('Content-Type'),
                  redirects=[{'url':h.url,'status_code':h.status_code,'location':h.headers.get('Location')} for h in r.history])
                chunks=[];size=0
                for block in r.iter_content(65536):
                    size+=len(block)
                    if size>byte_limit: raise ValueError('Response exceeded fixed byte limit')
                    if time.monotonic()-tick>50: raise TimeoutError('Fixed wall-clock body budget exceeded')
                    chunks.append(block)
                body=b''.join(chunks)
                path.write_bytes(body)
                encoding=r.encoding if r.encoding and r.encoding.lower()!='iso-8859-1' else 'utf-8'
                text=body.decode(encoding,errors='replace')
                log.update(saved_path=str(path),body_sha256=sha(body),body_bytes=len(body),
                           decoding=encoding,completed_at_utc=now(),elapsed_seconds=time.monotonic()-tick,
                           body_definition='Requests-decoded HTTP entity bytes, not compressed wire bytes')
                return log,text
    except Exception as e:
        log.update(error=f'{type(e).__name__}: {e}',completed_at_utc=now(),elapsed_seconds=time.monotonic()-tick)
        return log,None

def dom_text(html,include_alt=False):
    from bs4 import BeautifulSoup,Comment
    soup=BeautifulSoup(html,'lxml')
    body=soup.body or soup
    for x in list(body.find_all(['script','style','noscript','template','svg'])): x.decompose()
    for x in list(body.find_all(string=lambda s:isinstance(s,Comment))): x.extract()
    for x in list(body.find_all(True)):
        if x.parent is None: continue
        st=re.sub(r'\s+','',x.get('style','').lower())
        if x.has_attr('hidden') or x.get('aria-hidden')=='true' or 'display:none' in st or 'visibility:hidden' in st:
            x.decompose()
    if include_alt:
        for img in list(body.find_all('img')):
            alt=img.get('alt','').strip()
            if alt: img.replace_with(' '+alt+' ')
    return '\n'.join(x.strip() for x in body.get_text('\n',strip=True).splitlines() if x.strip())

def extract(html,url,method):
    if method=='bs4_body_text': return dom_text(html)
    if method=='bs4_body_with_image_alt': return dom_text(html,True)
    if method.startswith('trafilatura_'):
        import trafilatura
        return trafilatura.extract(html,url=url,output_format='txt',include_tables=True,include_comments=False,
          include_links=False,include_images=False,deduplicate=False,
          favor_precision=method=='trafilatura_precision',favor_recall=method=='trafilatura_recall') or ''
    if method=='readability_lxml':
        from readability import Document
        return dom_text(Document(html,url=url).summary(html_partial=True))
    raise ValueError(method)

def measures(text,anchors,available):
    normalized=norm(text);tokens=normalized.split()
    findings=[]
    for a in anchors:
        pattern=norm(a['phrase'])
        hit=re.search(r'(?<!\w)'+re.escape(pattern)+r'(?!\w)',normalized) is not None
        findings.append({'anchor_id':a['id'],'present':hit,'available_in_reference_dom':available[a['id']]})
    marker_spans=[];marker_counts={}
    for marker in MARKERS:
        pattern=norm(marker)
        matches=list(re.finditer(r'(?<!\w)'+re.escape(pattern)+r'(?!\w)',normalized))
        if matches: marker_counts[marker]=len(matches)
        marker_spans += [(m.start(),m.end()) for m in matches]
    token_spans=list(re.finditer(r'\w+',normalized))
    marked=sum(any(a<t.end() and b>t.start() for a,b in marker_spans) for t in token_spans)
    grams=[tuple(tokens[i:i+5]) for i in range(max(0,len(tokens)-4))]
    available_n=sum(available.values())
    hits=sum(f['present'] and f['available_in_reference_dom'] for f in findings)
    return dict(word_count=len(tokens),characters=len(text),anchor_checks=findings,
        available_anchor_count=available_n,retained_available_anchor_count=hits,
        anchor_retention_fraction=hits/available_n if available_n else None,
        boilerplate_marker_counts=marker_counts,boilerplate_marker_token_count=marked,
        boilerplate_marker_token_ratio=marked/len(tokens) if tokens else None,
        repeated_5gram_fraction=1-len(set(grams))/len(grams) if grams else None,
        metric_limits='Anchors are agent-selected diagnostic phrases, not human gold or exhaustive recall. Boilerplate is a fixed lexical proxy; five-gram repetition is a textual redundancy proxy.')

def capture():
    BASE.mkdir(parents=True,exist_ok=True)
    if (BASE/'config_freeze.json').exists(): raise FileExistsError('Capture already frozen; do not refetch implicitly.')
    config={'frozen_at_utc':now(),'selection':'Exactly GTII story, DOX products-services, RIGL products in this order; no substitutions.',
       'sites':SITES,'methods':METHODS,'script_sha256':sha(Path(__file__).read_bytes()),
       'packages':{x:metadata.version(x) for x in ['requests','beautifulsoup4','lxml','trafilatura','readability-lxml']},
       'source_arm':'New current HTTP captures; not historical baseline material; no rank comparison.',
       'robots_policy':'One robots.txt attempt per origin; 2xx parsed for this user agent, 404 permits; all other errors/statuses stop that case.',
       'fetch_policy':'One HTML attempt if robots permits; ordinary TLS-verified public requests, max 5 redirects; no retries, proxy changes, login, captcha or browser fallback.',
       'limits':{'robots_bytes':524288,'html_bytes':5242880,'connect_seconds':15,'read_seconds':30,'body_wall_seconds':50},
       'conservative_dom':'Body text; omit script/style/noscript/template/SVG/comments and explicit hidden/aria-hidden/inline display:none; CSS is not executed. Alt variant adds img alt text at its DOM position.',
       'trafilatura':'Precision versus recall, tables retained, comments/images/links excluded, deduplication disabled; same HTML in both.',
       'readability':'Document.summary(html_partial=True), then same conservative body text conversion.',
       'reference':'Conservative body plus image alt provides source-availability probes; agreement is not truth or complete coverage.',
       'boilerplate_markers':MARKERS,'no_human_gold':True,'no_financial_outcomes':True,'no_rankings':True,
       'primary_sources':['https://aclanthology.org/2021.acl-demo.15.pdf','https://trafilatura.readthedocs.io/en/latest/corefunctions.html','https://github.com/buriy/python-readability']}
    write(BASE/'config_freeze.json',config)
    cases=[]; rows=[]
    for site in SITES:
        folder=BASE/site['ticker'];folder.mkdir(exist_ok=False)
        parts=urlsplit(site['url']);robots_url=f'{parts.scheme}://{parts.netloc}/robots.txt'
        robot_log,robot_text=http_get(robots_url,folder/'robots.txt',524288)
        case={'ticker':site['ticker'],'company_id':site['company_id'],'url':site['url'],'robots':robot_log}
        status=robot_log.get('status_code');allowed=False
        if status==404 and not robot_log.get('error'):
            allowed=True;reason='robots_missing_404'
        elif status and 200<=status<300 and robot_text is not None:
            if '<html' in robot_text[:500].lower(): reason='robots_response_is_html_unusable'
            else:
                rp=RobotFileParser();rp.set_url(robots_url);rp.parse(robot_text.splitlines())
                allowed=rp.can_fetch(UA,site['url']);reason='robots_allowed' if allowed else 'robots_disallowed'
        else: reason='robots_unavailable_no_bypass'
        case['robots_decision']={'allowed':allowed,'reason':reason}
        if not allowed:
            case['status']='not_fetched_robots';cases.append(case);write(folder/'capture.json',case)
            print(site['ticker'],case['status'],reason,flush=True);continue
        log,html=http_get(site['url'],folder/'source.html',5242880)
        case['capture']=log
        if html is None or log.get('status_code')!=200:
            case['status']='http_failed_or_blocked';cases.append(case);write(folder/'capture.json',case)
            print(site['ticker'],case['status'],log.get('status_code'),flush=True);continue
        title_match=re.search(r'<title[^>]*>(.*?)</title',html,re.I|re.S)
        title=norm(title_match.group(1)) if title_match else ''
        challenge=any(x in title for x in ['just a moment','access denied','attention required','verify you are human','robot check'])
        if challenge:
            case['status']='challenge_page_no_bypass';cases.append(case);write(folder/'capture.json',case)
            print(site['ticker'],case['status'],flush=True);continue
        if 'html' not in str(log.get('content_type','')).lower() and not re.search(r'<html|<!doctype',html,re.I):
            case['status']='non_html_response';cases.append(case);write(folder/'capture.json',case)
            print(site['ticker'],case['status'],flush=True);continue
        case['status']='captured';case['extractors']=[]
        reference=dom_text(html,True)
        available={a['id']:norm(a['phrase']) in norm(reference) for a in site['anchors']}
        case['anchor_availability']=available
        for method in METHODS:
            started=time.perf_counter()
            try:
                text=extract(html,site['url'],method)
                path=folder/f'{method}.txt';path.write_text(text,encoding='utf-8')
                metrics=measures(text,site['anchors'],available)
                entry={'method':method,'status':'extracted' if text else 'empty','text_path':str(path),
                       'text_sha256':sha(text.encode()),'elapsed_seconds':time.perf_counter()-started,**metrics}
            except Exception as e:
                entry={'method':method,'status':'extractor_error','error':f'{type(e).__name__}: {e}'}
            case['extractors'].append(entry)
            rows.append({'ticker':site['ticker'],'method':method,**{k:v for k,v in entry.items() if k not in ['anchor_checks','boilerplate_marker_counts','metric_limits','text_path','method']}})
        cases.append(case);write(folder/'capture.json',case)
        print(site['ticker'],'captured',log['body_bytes'],'bytes; anchors',sum(available.values()),'/',len(available),flush=True)
    report={'created_at_utc':now(),'config_sha256':sha((BASE/'config_freeze.json').read_bytes()),
            'cases':cases,'attempted_cases':len(SITES),'captured_cases':sum(c['status']=='captured' for c in cases),
            'interpretation':'Three deliberately diagnostic pages; no population accuracy, complete business recall or ranking improvement claim. Blocked cases remain missing.'}
    write(BASE/'results.json',report)
    import csv
    columns=['ticker','method','status','word_count','available_anchor_count','retained_available_anchor_count',
             'anchor_retention_fraction','boilerplate_marker_token_ratio','repeated_5gram_fraction','elapsed_seconds','text_sha256']
    with (BASE/'comparison.csv').open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=columns,extrasaction='ignore');w.writeheader();w.writerows(rows)
    summarize(report)
    print('LIVE_CLEANING_COMPLETE',report['captured_cases'],'of',len(SITES),'captured',flush=True)

def summarize(report):
    lines=['LIVE DOM CLEANING DIAGNOSTIC','Current captures only; separate from the October 17 corpus.',
           'Provisional AGENT diagnostic; no human gold labels, complete recall measure, ranking test or financial outcome.',
           'Config was frozen before HTTP attempts. Exactly three selected official pages; no blocked-case substitution.','']
    for c in report['cases']:
        lines += [c['ticker']+' — '+c['url'],'Status: '+c['status'],'Robots decision: '+c['robots_decision']['reason']]
        if c.get('capture'): lines += ['Capture: '+str(c['capture'].get('completed_at_utc'))+' | SHA256 '+str(c['capture'].get('body_sha256'))]
        for e in c.get('extractors',[]):
            if 'word_count' in e:
                ratio=e['boilerplate_marker_token_ratio']
                lines += [f"  {e['method']}: {e['word_count']} words; available anchor phrases {e['retained_available_anchor_count']}/{e['available_anchor_count']}; boilerplate-marker token fraction {ratio}; repeated 5-grams {e['repeated_5gram_fraction']}"]
            else: lines += ['  '+e['method']+': '+e['status']+' '+e.get('error','')]
        lines += ['']
    lines += ['METRIC LIMITS',
      'Anchor phrases are chosen from the previous audit before extraction. They test specific evidence survival, not exhaustive factual recall. A product name alone does not establish its indication, ownership, weight or stage.',
      'Reference availability uses conservative DOM text plus image alt. If an anchor is absent there, it is not counted as an extractor failure. CSS and JavaScript are not executed; this is a fetched-DOM diagnostic, not a rendered-page accessibility audit.',
      'Boilerplate-marker ratio counts only frozen marker tokens and can miss navigation/culture copy. It is not precision. Repeated five-grams detect surface redundancy, not semantic duplication.',
      'Raw HTML bytes, robots response, redirects, dates and checksums are retained. No historical HTML was reconstructed.',
      '', 'RESEARCH BASIS',
      'Barbaresi (2021): https://aclanthology.org/2021.acl-demo.15.pdf — evaluated text/boilerplate extraction on 500 pages; does not guarantee complete company or product-list capture.',
      'Trafilatura 2.3.1 API: https://trafilatura.readthedocs.io/en/latest/corefunctions.html — precision favors less text; recall prefers more when uncertain; table/image/link options are explicit.',
      'Readability implementation: https://github.com/buriy/python-readability — article-content extraction is an alternative to conservative DOM retention; product catalogs are a different input type.',
      '', 'DECISION RULE',
      'Use both a conservative evidence layer and a compact main-content layer. Route any lost predeclared material anchor to source review; retain product headings, lists/tables, link text and image alt with location/role metadata. Do not silently call empty extraction an absent business.',
      'These are diagnostic controls, not a globally validated production cleaner choice. A wider independent page sample and human coverage review remain necessary.']
    (BASE/'REPORT.txt').write_text('\n'.join(lines)+'\n',encoding='utf-8')

def validate_captures():
    """Post-capture challenge audit on saved bytes only; never refetch pages.

    A title-only gate missed an HTTP-200 Incapsula response. Preserve the initial
    result and record this general body-marker correction transparently.
    """
    report=json.loads((BASE/'results.json').read_text(encoding='utf-8'))
    initial=BASE/'results_initial_before_body_challenge_check.json'
    if initial.exists(): raise FileExistsError('Post-capture validation already recorded.')
    initial.write_bytes((BASE/'results.json').read_bytes())
    patterns=[r'Request unsuccessful\.\s*Incapsula incident ID',r'<iframe[^>]+src=["\'][^"\']*_Incapsula_Resource',
              r'Please enable JavaScript and cookies to continue',r'cf-chl-']
    changed=[]
    for case in report['cases']:
        if not case.get('capture',{}).get('saved_path'): continue
        path=Path(case['capture']['saved_path']);raw=path.read_bytes()
        assert sha(raw)==case['capture']['body_sha256']
        html=raw.decode(case['capture']['decoding'],errors='replace')
        hits=[p for p in patterns if re.search(p,html,re.I)]
        if hits:
            case['initial_status']=case['status'];case['status']='challenge_page_no_bypass'
            case['body_challenge_patterns']=hits
            case['eligible_for_content_comparison']=False
            for entry in case.get('extractors',[]):
                entry['interpretation_override']='Blocked-response text only; excluded from successful business-page comparisons.'
            changed.append(case['ticker'])
        else: case['eligible_for_content_comparison']=case['status']=='captured'
        write(BASE/case['ticker']/'capture.json',case)
    report['captured_cases']=sum(c['status']=='captured' for c in report['cases'])
    report['post_capture_validation']={'created_at_utc':now(),'scope':'Saved bytes only, all three cases; no retries or bypass.',
       'reason':'The initial title-only challenge gate missed an HTTP-200 Incapsula iframe response.',
       'patterns':patterns,'reclassified':changed,'initial_results_sha256':sha(initial.read_bytes()),
       'script_current_sha256':sha(Path(__file__).read_bytes()),'change_type':'Acquisition-status correction; extractor outputs and anchors unchanged.'}
    write(BASE/'results.json',report)
    rows=[]
    for c in report['cases']:
        for e in c.get('extractors',[]):
            rows.append({'ticker':c['ticker'],'capture_status':c['status'],
                         'eligible_for_content_comparison':c.get('eligible_for_content_comparison',False),**e})
    import csv
    columns=['ticker','capture_status','eligible_for_content_comparison','method','status','word_count',
       'available_anchor_count','retained_available_anchor_count','anchor_retention_fraction',
       'boilerplate_marker_token_ratio','repeated_5gram_fraction','elapsed_seconds','text_sha256']
    with (BASE/'comparison.csv').open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=columns,extrasaction='ignore');w.writeheader();w.writerows(rows)
    summarize(report)
    with (BASE/'REPORT.txt').open('a',encoding='utf-8') as f:
        f.write('\nPOST-CAPTURE STATUS CORRECTION\nThe initial title-only gate missed DOX\'s HTTP-200 Incapsula iframe response. Saved HTML was checked for explicit body challenge signatures across all three cases. DOX is blocked, its extractor outputs are excluded from business-page comparisons, and no retry or bypass occurred. Initial results are retained for audit. Two usable company pages remain.\n')
        f.write('\nOBSERVED CLEANING TRADEOFF\nGTII: both Trafilatura modes retained all three selected business anchors in 612 words, compared with 1,044 conservative DOM words; readability retained none in 310 words. RIGL: conservative body/link text retained four product names in 212 words; Trafilatura precision/recall and readability retained none in 90/93/92 words. Reduced boilerplate alone therefore cannot select a business evidence extractor. These results apply only to the two fetched pages and preselected anchors.\n')
    print(json.dumps({'status':'validated','usable_cases':report['captured_cases'],'reclassified':changed,'refetched':False},indent=2))

def source_provenance():
    """Map predeclared anchors to actual DOM elements; check saved output hashes."""
    from lxml import html as lhtml
    report=json.loads((BASE/'results.json').read_text(encoding='utf-8'))
    sites={s['ticker']:s for s in SITES}; records=[]; output_hashes_verified=0
    for case in report['cases']:
        record={'ticker':case['ticker'],'capture_status':case['status'],'anchors':[]}
        if case['status']!='captured':
            record['evaluation_status']='unavailable; blocked case is not a company-content failure'
            records.append(record);continue
        raw=Path(case['capture']['saved_path']).read_bytes()
        assert sha(raw)==case['capture']['body_sha256']
        tree=lhtml.fromstring(raw);root=tree.getroottree()
        for anchor in sites[case['ticker']]['anchors']:
            hits=[]
            for node in tree.iter():
                if node.tag not in ('h1','h2','h3','h4','h5','h6','p','li','td','a','img'): continue
                text=node.get('alt','') if node.tag=='img' else ' '.join(node.itertext())
                if norm(anchor['phrase']) not in norm(text): continue
                ancestors=[a.tag for a in node.iterancestors()]
                excluded_context=any(a in ('script','style','template','noscript') for a in ancestors)
                if excluded_context: continue
                navigation_context=any(a in ('nav','header','footer') for a in ancestors)
                hits.append({'xpath':root.getpath(node),'tag':node.tag,'href':node.get('href'),
                  'attribute':'alt' if node.tag=='img' else 'element_text',
                  'navigation_or_footer_context':navigation_context,
                  'matched_anchor':anchor['phrase'],'element_word_count':len(text.split()),
                  'element_text_sha256':sha(text.encode('utf-8'))})
            hits.sort(key=lambda h:(h['navigation_or_footer_context'],h['element_word_count'],h['xpath']))
            record['anchors'].append({'anchor_id':anchor['id'],'source_occurrence_count':len(hits),
                 'non_navigation_occurrence_count':sum(not h['navigation_or_footer_context'] for h in hits),
                 'selected_source_locations':hits[:4]})
        for method in case['extractors']:
            if method.get('text_path'):
                output=Path(method['text_path'])
                assert sha(output.read_text(encoding='utf-8').encode('utf-8'))==method['text_sha256']
                method['text_hash_definition']='Canonical UTF-8 text with LF newlines; Windows file bytes may use CRLF.'
                method['text_file_sha256']=sha(output.read_bytes())
                output_hashes_verified+=1
        write(BASE/case['ticker']/'capture.json',case)
        records.append(record)
    assert sum(c['capture_status']=='captured' for c in records)==2
    assert all(a['non_navigation_occurrence_count']>0 for c in records if c['capture_status']=='captured' for a in c['anchors'])
    obj={'validated_at_utc':now(),'status':'passed','source_anchor_locations':records,
       'usable_pages':2,'extractor_output_hashes_verified':output_hashes_verified,
       'note':'Every counted anchor has at least one real non-navigation DOM occurrence. Output phrase presence still does not establish complete factual claims, ownership, indications or business weights. No human gold recall is estimated.'}
    report['text_hash_clarification']='text_sha256 hashes canonical extracted UTF-8 text; text_file_sha256 separately hashes on-disk bytes, including platform newlines.'
    write(BASE/'results.json',report)
    write(BASE/'source_validation.json',obj)
    print(json.dumps({'status':obj['status'],'usable_pages':2,'output_hashes_verified':output_hashes_verified,'real_dom_anchor_checks':7},indent=2))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['capture','summarize','validate','provenance']);args=parser.parse_args()
    if args.action=='capture': capture()
    elif args.action=='validate': validate_captures()
    elif args.action=='provenance': source_provenance()
    else: summarize(json.loads((BASE/'results.json').read_text(encoding='utf-8')))
