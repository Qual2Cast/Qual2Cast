"""Source-backed analyst review of the five fixed health-sector target lists.

These assessments are agent interpretations, not independent human labels.
The script attaches exact cached website evidence and never opens valuation data.
"""
from pathlib import Path
from datetime import datetime, timezone
import json, hashlib
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'outputs-local/modular-validation'

# The descriptions below are based on inspection of the captured official pages.
# Every material observed line is retained, and economic weights remain unknown.
SCOPES = {
 'HRMY': ('IQ679038073', [
  ('Sleep/wake drug development and commercial medicines; expansion into rare epilepsy.', [('P2',12),('P2',5),('P3',2)]),
  ('Acquired development businesses are part of the reported scope, not separate peers.', [('P2',9),('P2',10)])]),
 'SUPN': ('IQ422832', [
  ('CNS drug development and commercialization across neurology and psychiatry.', [('P2',30),('P3',1)]),
  ('Own US specialty sales and collaboration/licensing outside the US.', [('P2',32)]),
  ('Reported Sage acquisition and proposed Indivior merger require transaction-date review.', [('P1',1),('P1',3)])]),
 'XERS': ('IQ105901792', [
  ('Commercial therapies for severe hypoglycemia, periodic paralysis and Cushing syndrome.', [('P1',2),('P1',3),('P1',4)]),
  ('Own pipeline plus formulation technology licensing to other biopharmaceutical companies.', [('P1',6),('P1',10),('P1',18),('P1',19)])]),
 'AMRX': ('IQ38444119', [
  ('Generic medicines, biosimilars, hospital injectables and branded CNS/endocrine therapies.', [('P2',14),('P2',15),('P2',16),('P2',17)]),
  ('AvKARE distribution and global manufacturing/API operations.', [('P2',19),('P3',6),('P3',9)])]),
 'RMD': ('IQ340196', [
  ('Cloud-connected CPAP devices, masks, sleep testing and respiratory equipment.', [('P1',10),('P2',0),('P3',5),('P3',6)]),
  ('Out-of-hospital healthcare management software.', [('P3',7),('P3',1)])]),
 'BMRN': ('IQ25605', [
  ('Genetically defined rare-disease medicines with a commercial and developmental portfolio.', [('P1',7),('P1',8)]),
  ('Genetic-discovery strategy, enzyme-therapy history and international commercial footprint.', [('P2',2),('P2',10),('P2',13)])]),
 'NEOG': ('IQ339683', [
  ('Food/beverage pathogen, allergen and toxin testing products.', [('P1',7)]),
  ('Livestock equipment and genomics; companion-animal care tools and products.', [('P1',8),('P1',9)]),
  ('Life-science, toxicology and water-testing tools plus accredited laboratory services.', [('P1',10),('P3',1),('P3',2)])]),
 'WAT': ('IQ36475', [
  ('Analytical chromatography/mass-spectrometry systems, consumables, informatics and services.', [('P2',1),('P3',28),('P3',31)]),
  ('Diagnostics, biosciences and materials-testing applications broaden the company.', [('P3',0),('P3',23),('P3',43)])]),
 'SHC': ('IQ34781', [
  ('Sterigenics outsourced terminal sterilization and irradiation.', [('P1',10)]),
  ('Nordion gamma technologies and Nelson Labs testing/advisory services.', [('P1',8),('P1',5)])]),
 'MLAB': ('IQ287550', [
  ('Life-science and quality-control instruments, monitoring and calibration.', [('P1',0),('P1',5),('P2',2)]),
  ('Agena Bioscience, Gyros Protein Technologies and Mesa Labs brands across research and clinical markets.', [('P3',2)])]),
 'BCPC': ('IQ253076', [
  ('Human nutrition/health and animal nutrition products.', [('P1',8),('P1',9),('P1',10)]),
  ('Specialty gases packaging/distribution and plant-nutrition chelated minerals.', [('P1',11)])]),
 'BIO': ('IQ255743', [
  ('Research and clinical diagnostic instruments, reagents, controls and data tools.', [('P1',3),('P2',16),('P2',19)]),
  ('Food/beverage, water, animal testing and educational tools are additional applications.', [('P2',34),('P2',36),('P2',37),('P2',38)])]),
 'GTII': ('IQ560549330', [
  ('Cannabis consumer brands/production and RISE retail operations across multiple markets.', [('P2',1),('P2',6),('P2',7),('P3',1)])]),
 'VRNO': ('IQ322580786', [
  ('Cannabis cultivation/production and broad branded product formats.', [('P2',4),('P2',6),('P1',10),('P1',15)]),
  ('Zen Leaf and MUV dispensaries.', [('P3',2),('P3',4)])]),
 'CL': ('IQ273639073', [
  ('Cannabis cultivation/manufacturing, wholesale brands and owned retail.', [('P1',6),('P1',8)]),
  ('Sunnyside retail and related e-commerce; SEED is a social-equity initiative, not automatically a separate commercial segment.', [('P3',3),('P3',7),('P2',2)])]),
 'MRMD': ('IQ276645250', [
  ('Multi-state cannabis operator with cultivation, branded products and stores.', [('P2',5),('P3',6),('P1',6)]),
  ('Chews, baked products, drink mixes, flower and vapes are retained together.', [('P3',5),('P3',7),('P3',8),('P3',9)])]),
 'MAPS': ('IQ579310978', [
  ('Cannabis marketplace connecting consumers and third-party businesses.', [('P3',3),('P3',9)]),
  ('Business SaaS, marketing and advertising tools.', [('P3',5),('P3',6),('P3',7)])]),
 'TRUL': ('IQ53036657', [
  ('Controlled-environment cannabis cultivation and dispensary retail.', [('P2',1),('P2',3),('P1',1)]),
  ('Consumer/medical access and product promotions are visible; wholesale mix is not established by these pages.', [('P2',5),('P2',6)])]),
 'MNKD': ('IQ9282918', [
  ('Cardiometabolic and orphan-lung therapies, including diabetes and fluid overload.', [('P1',0),('P2',2)]),
  ('Inhalation technology partnerships and wholly owned scPharmaceuticals/Furoscix business.', [('P1',6),('P1',7),('P1',9)]),
  ('Pipeline spans insulin delivery patch, inhaled therapies and infusion products.', [('P3',4),('P3',5),('P3',8)])]),
 'AKBA': ('IQ36644983', [
  ('Renal-disease drug development and commercialization; two approved products.', [('P1',3),('P2',2),('P3',3)])]),
 'PCRX': ('IQ27508', [
  ('Commercial non-opioid pain therapies across surgical, chronic and musculoskeletal settings.', [('P1',3),('P2',1)]),
  ('Osteoarthritis gene-therapy pipeline and partnerships covering hospital/outpatient/specialty call points.', [('P1',8),('P3',3),('P3',4)])]),
 'RIGL': ('IQ33851', [
  ('Therapy discovery/development/provision focused on hematology and cancer.', [('P1',0),('P2',1)]),
  ('International partnerships and a clinical IRAK1/4 inhibitor program.', [('P2',2),('P2',3)]),
  ('Captured products page contains contact text and does not enumerate the actual commercial catalog.', [('P3',0)])]),
 'ADMA': ('IQ51119246', [
  ('Plasma-derived immune-globulin therapies and commercial specialty biologics.', [('P2',1),('P3',1)]),
  ('Plasma collection plus CDMO/CMO filling, packaging and testing services.', [('P2',6),('P2',3)])]),
 'ATRA': ('IQ248196818', [
  ('Allogeneic T-cell cancer/autoimmune immunotherapies, with approval and investigational programs described.', [('P1',2),('P1',7)]),
  ('Donor-derived cell platform, manufacturing and inventory-based delivery.', [('P2',3),('P3',7),('P3',11)])]),
}

# overlap, difference, next discriminating check. These are hypotheses to review,
# rather than labels used to select or tune any ranking method.
PAIRS = {
 ('HRMY','SUPN'): ('Both develop and commercialize CNS medicines.', 'Supernus spans ADHD, epilepsy, Parkinson disease and migraine; Harmony emphasizes sleep/wake and rare epilepsy. The proposed merger and acquired Sage business also affect entity scope.', 'Compare product concentration, commercial versus pipeline contributions and transaction dates.'),
 ('HRMY','XERS'): ('Both combine commercial drug businesses and a development pipeline.', 'Xeris has diabetes/hypoglycemia, periodic-paralysis and Cushing therapies plus formulation licensing. Shared patient-focused wording is much broader than therapeutic and operating-model overlap.', 'Establish whether any commercial end market and licensing exposure are economically comparable.'),
 ('HRMY','AMRX'): ('Amneal has branded CNS therapies alongside commercial drug infrastructure.', 'Its generics, biosimilars, injectables, manufacturing and distribution cannot be discarded to isolate the CNS line. Harmony is not established as having that portfolio.', 'Measure all segment contributions before using a whole-company multiple.'),
 ('HRMY','RMD'): ('Both address aspects of sleep-related patient needs.', 'ResMed sells respiratory/sleep devices and care software; Harmony develops medicines for sleep/wake disorders. Similar vocabulary conceals product modality and revenue-model differences.', 'Require product/operating-role evidence before admitting this company as a peer.'),
 ('HRMY','BMRN'): ('Both develop and commercialize medicines for rare diseases.', 'BioMarin has a wider genetically defined disease portfolio, enzyme-therapy history and international footprint. Rare disease alone does not establish equivalent product concentration or development risk.', 'Compare modality, indications, geography and commercial/pipeline mix.'),
 ('NEOG','WAT'): ('Both supply analytical tools used in food/water safety and regulated testing.', 'Waters also spans pharmaceuticals, diagnostics, biosciences and physical-material testing. Neogen includes animal care, livestock genomics and testing services.', 'Quantify end-market and instruments/consumables/services mix on a consistent entity date.'),
 ('NEOG','SHC'): ('Laboratory testing and safety assurance overlap.', 'Sotera includes outsourced terminal sterilization, irradiation and gamma technologies. Neogen includes sold testing products, animal care and genomics; one laboratory line is not the whole business.', 'Separate operator/service economics from product economics and examine all three Sotera businesses.'),
 ('NEOG','MLAB'): ('Both provide testing/quality-control tools for regulated settings.', 'Mesa spans life-science brands, critical-environment monitoring, dialysate calibration and air sampling. The captured pages do not establish Neogen-like animal and food-chain exposure for the whole company.', 'Review brand-level end markets and recurring consumables versus instrument/service exposure.'),
 ('NEOG','BCPC'): ('Both serve food and animal-related markets.', 'Balchem supplies nutrition ingredients and has plant nutrition and specialty gases. Neogen primarily describes safety testing, animal-care tools and laboratory services. Shared customers do not establish the same product function.', 'Check functional substitutability and economics rather than relying on food/animal keywords.'),
 ('NEOG','BIO'): ('Bio-Rad explicitly offers food, water and animal testing, alongside research tools.', 'Bio-Rad also has broad clinical diagnostics, blood typing, bioprocessing and molecular research. Neogen has animal-care/livestock activities that cannot be assumed to match.', 'Compare the complete business mix; do not value all Bio-Rad as its food-testing line.'),
 ('GTII','VRNO'): ('Both combine cannabis cultivation/branded products with owned dispensaries.', 'Brand portfolios and state-level operating footprints differ; their economic materiality is not provided. The same broad vertical integration is a stronger operational link than cannabis vocabulary alone.', 'Verify licensed markets, cultivation/wholesale/retail shares and current corporate scope.'),
 ('GTII','CL'): ('Both have cannabis production, consumer brands and retail operations.', 'Cresco explicitly describes wholesale distribution and Sunnyside retail/e-commerce. Relative wholesale/retail importance and geographic exposure are not established as equal.', 'Compare market footprint and wholesale versus store economics; keep SEED separate from commercial operations.'),
 ('GTII','MRMD'): ('Both are multi-state cannabis operators with products and retail.', 'MariMed describes a different brand/format portfolio. The sources establish operating overlap but do not show that their scale, markets or business weights are comparable.', 'Obtain full market and channel mix without selecting only the most similar brand.'),
 ('GTII','MAPS'): ('Both participate in the cannabis ecosystem and consumer discovery.', 'Weedmaps describes a third-party marketplace, advertising and SaaS; Green Thumb describes production/brands and owned stores. Marketplace listings are not evidence that WM cultivates or owns each listed retailer.', 'Treat operating role as a required review criterion; investigate rather than approve from text similarity.'),
 ('GTII','TRUL'): ('Both describe cannabis cultivation and dispensary retail.', 'The Trulieve capture is thin on wholesale, product mix and geographic concentration. Operational overlap is plausible but whole-company equivalence remains unestablished.', 'Review all material brands, market exposures and channels before financial use.'),
 ('XERS','MNKD'): ('Both combine marketed therapies, drug-delivery technologies and partnerships; diabetes-related products provide a concrete overlap.', 'MannKind additionally describes orphan-lung disease, fluid overload and scPharmaceuticals, with inhalation/infusion/patch delivery. Xeris includes periodic paralysis, Cushing syndrome and nonaqueous formulation licensing.', 'Compare the full therapeutic and technology/licensing mix, including acquired subsidiaries.'),
 ('XERS','AMRX'): ('Both have commercial specialty medicines, including endocrine-related products.', 'Amneal also has generics, biosimilars, hospital injectables, API/manufacturing and AvKARE distribution. Selecting only specialty/endocrine activity would misrepresent the consolidated peer.', 'Require segment contribution data or explicitly retain a substantial portfolio mismatch.'),
 ('XERS','AKBA'): ('Both combine approved medicines and drug development.', 'Akebia is centered on kidney disease/nephrology. Xeris covers hypoglycemia, periodic paralysis, Cushing syndrome and a formulation licensing platform; this is a broad business-model analogy, not demonstrated end-market equivalence.', 'Check modality, customer call points, product concentration and technology licensing.'),
 ('XERS','SUPN'): ('Both commercialize specialty medicines and maintain clinical pipelines.', 'Supernus focuses on CNS/psychiatry and its own sales/licensing structure; Xeris has broader endocrine/metabolic and formulation-platform exposure. Merger-related scope also needs alignment.', 'Compare actual product/indication mix rather than executive biographies or generic innovation language.'),
 ('XERS','PCRX'): ('Both commercialize therapies and pursue development/partnership opportunities.', 'Pacira is concentrated in non-opioid pain with an osteoarthritis gene-therapy pipeline and surgical call points. Xeris describes different indications and formulation technology licensing.', 'Establish comparable commercial channels, modalities and revenue concentration.'),
 ('RIGL','XERS'): ('Both describe therapy development, provision and partnerships.', 'Rigel emphasizes hematology/cancer; Xeris describes endocrine/metabolic products and formulation technologies. The captured Rigel catalog is incomplete, so a strong whole-company conclusion is unsupported.', 'Recover Rigel product catalog and commercial mix before approving any comparator.'),
 ('RIGL','ADMA'): ('Both provide therapies to defined patient populations and have commercial activity described.', 'ADMA centers on plasma-derived immune globulins, plasma collection and CDMO services. These activities differ from Rigel’s captured oncology/hematology focus; shared biological terminology is insufficient.', 'Verify Rigel catalog and compare modality, manufacturing integration and service mix.'),
 ('RIGL','BMRN'): ('Both have development programs and medicines for specialized diseases.', 'BioMarin emphasizes genetically defined rare conditions and a broad international portfolio. Rigel’s captured focus is hematology/cancer, with insufficient catalog evidence to match modalities or product weights.', 'Obtain the missing Rigel catalog, then assess indication, modality and concentration differences.'),
 ('RIGL','SUPN'): ('Both describe drug-development and commercialization organizations.', 'Supernus focuses on CNS/psychiatry while Rigel focuses on hematology/cancer; the available catalog evidence cannot justify a close whole-company match.', 'Review complete commercial and pipeline exposure; generic biopharma similarity is not enough.'),
 ('RIGL','ATRA'): ('Cancer therapy development is a concrete area of overlap.', 'Atara describes allogeneic donor-derived T-cell therapies and cell manufacturing, plus autoimmune applications. Rigel’s captured IRAK inhibitor program is different, and its commercial catalog is missing.', 'Compare modality, approval/geographic status, manufacturing model and actual revenue mix.'),
}


def main():
    d=json.loads((OUT/'design_freeze.json').read_text())
    base=Path(d['team_root'])/'outputs-local/website_scrape/page_text'
    rankings=pd.read_csv(OUT/'core/rankings.csv')
    companies={}; ticker_to_id={}
    for ticker,(cid,scope) in SCOPES.items():
        path=base/f'{cid}.json'; raw=json.loads(path.read_text(encoding='utf-8'))
        pages={p['page_id']:p for p in raw['pages']}; records={}; activities=[]
        for claim,locations in scope:
            refs=[]
            for page_id,index in locations:
                p=pages[page_id]; eid=f'{cid}:{page_id}:raw_blocks:{index}'
                records[eid]={'evidence_id':eid,'quote':p['raw_blocks'][index],
                    'page_url':p['url'],'fetched_at':p.get('fetched_at'),
                    'page_id':page_id,'block_index':index,'source_field':'raw_blocks',
                    'source_json_sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
                refs.append(eid)
            activities.append({'activity':claim,'role':'See source-specific operating role in statement',
                'customer':'Only as stated in the attached sources','monetization_status':'Economic contributions not measured',
                'evidence_ids':refs})
        companies[cid]={'name':raw['company_name'],'ticker':ticker,'observed_business_scope':activities,
            'scope_unknowns':['Complete current consolidated scope is not certified.','Revenue/profit weights of activities are unknown.','Website capture and supplied financial snapshot dates are not aligned.'],
            'source_records':list(records.values())}
        ticker_to_id[ticker]=cid
    pairs=[]
    for (target,peer),(overlap,difference,question) in PAIRS.items():
        cid,pid=ticker_to_id[target],ticker_to_id[peer]
        row=rankings[(rankings.target_id==cid)&(rankings.candidate_id==pid)&(rankings.method=='team_mpnet_cosine')].iloc[0]
        assert int(row['rank'])<=5
        refs=lambda x:[v['evidence_id'] for v in companies[x]['source_records']]
        pairs.append({'target_id':cid,'candidate_id':pid,'baseline_rank':int(row['rank']),
            'overlap_claims':[{'claim':overlap,'target_evidence_ids':refs(cid),'candidate_evidence_ids':refs(pid)}],
            'material_mismatches':[{'claim':difference,'evidence_ids':refs(cid)+refs(pid)}],
            'unknowns':['No independent human approval or complete economic business weights.','Dates, financial definitions and public-listing eligibility require verification.'],
            'committee_rationale':f'{overlap} {difference} This is a review candidate, not an approved comparable.',
            'review_questions':[question],'agent_provisional':True,'human_approved':False})
    assert len(pairs)==25
    result={'review_version':'2026-10-18-health-v1','created_at_utc':datetime.now(timezone.utc).isoformat(),
        'assessment_origin':'AGENT','independent_human_labels':0,'ranking_method':'team_mpnet_cosine',
        'ranking_sha256':hashlib.sha256((OUT/'core/rankings.csv').read_bytes()).hexdigest(),
        'source_policy':'Exact frozen captured official website blocks. These are source-backed agent interpretations; no independent relevance labels, no target financial outcomes, no post-hoc reranking.',
        'companies':companies,'pairs':pairs}
    path=OUT/'ic_case_reviews_health.json';path.write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8')
    print('HEALTH_IC_REVIEWS',len(companies),'companies',len(pairs),'pairs',path)

if __name__=='__main__':main()
