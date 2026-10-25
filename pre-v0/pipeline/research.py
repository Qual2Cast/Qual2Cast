"""Method decisions and source boundaries for the workflow report."""
SOURCES = {
 'sec_ebitda':('SEC, Non-GAAP Financial Measures, C&DIs 100 and 103',
      'https://www.sec.gov/rules-regulations/staff-guidance/corporation-finance-interpretations/non-gaap-financial-measures'),
 'baker':('Baker and Ruback (1999), Estimating Industry Multiples',
      'https://www.hbs.edu/ris/Publication%20Files/EstimatingIndustry_b4e64d71-c8fd-4a5e-b31a-623d3a7d02bc.pdf'),
 'ndcg':('Jarvelin and Kekalainen (2002), Cumulated Gain-Based Evaluation of IR Techniques',
      'https://faculty.cc.gatech.edu/~zha/CS8803WST/dcg.pdf'),
 'accuracy':('Hyndman and Athanasopoulos, Forecasting: Principles and Practice, accuracy measures',
      'https://otexts.com/fpp3/toolbox.html'),
 'financial_firms':('Damodaran (2009), Valuing Financial Service Firms',
      'https://people.stern.nyu.edu/adamodar/pdfiles/papers/finfirm09.pdf'),
 'brightview':('BrightView, FY2025 earnings release, reconciliation table (PDF p. 15)',
      'https://s22.q4cdn.com/142468460/files/doc_financials/2025/q4/BrightView-8K-Q4FY25-Vf.pdf'),
 'sard':('Knudsen, Kold and Plenborg (2017), Stick to the Fundamentals and Discover Your Peers',
         'https://research.cbs.dk/da/publications/stick-to-the-fundamentals-and-discover-your-peers/'),
 'ml':('Geertsema and Lu (2023), Relative Valuation with Machine Learning',
       'https://onlinelibrary.wiley.com/doi/10.1111/1475-679X.12464'),
 'ipev':('IPEV Valuation Guidelines (December 2025), sections 3.4 and 5.13',
         'https://www.privateequityvaluation.com/Portals/0/Documents/Guidelines/2025%20IPEV%20Valuation%20Guidelines.pdf'),
 'rbics':('FactSet, RBICS with Tradenames',
          'https://insight.factset.com/resources/at-a-glance-factset-rbics-with-tradenames-datafeed'),
 'rrf':('Cormack, Clarke and Buettcher (2009), Reciprocal Rank Fusion',
        'https://research.google/pubs/reciprocal-rank-fusion-outperforms-condorcet-and-individual-rank-learning-methods/'),
 'sbert':('Reimers and Gurevych (2019), Sentence-BERT','https://aclanthology.org/D19-1410/'),
 'llm_peers':('Cao et al. (2025), Can generative AI help identify peer firms?',
              'https://link.springer.com/article/10.1007/s11142-025-09892-6'),
 'ranking':('Qin et al. (2024), Large Language Models are Effective Text Rankers with Pairwise Ranking Prompting',
             'https://aclanthology.org/2024.findings-naacl.97/'),
 'selection':('Cawley and Talbot (2010), On Over-fitting in Model Selection',
              'https://www.jmlr.org/papers/v11/cawley10a.html'),
 'multiples':('Liu, Nissim and Thomas (2002), Equity Valuation Using Multiples',
              'https://business.columbia.edu/sites/default/files-efs/imce-uploads/dnissim/publications/Equity%20Valuation%20Using%20Multiples.pdf'),
}

FACTORS = [
 ('Products and services','Website activities and product functions','Primary business comparison','Preserve all observed lines; no assumed revenue shares','rbics'),
 ('Operating role','Manufacturer, distributor, platform, service operator','Compatibility review','Same vocabulary does not imply the same business','ipev'),
 ('Customers and end markets','Stated buyers, users and applications','Business comparison','Customer or supplier activities must not become company activities','rbics'),
 ('Revenue model','Explicit subscription, licensing, franchise or sales evidence','Conditional business facet','Unknown when unsupported; model-generated facets are unverified','ipev'),
 ('Scale','Permitted target revenue','Secondary rank-distance factor','Revenue currency, units and measurement date require verification','sard'),
 ('Profitability','EBITDA / revenue','Secondary rank-distance factor','Not ROIC, ROE, free cash flow or owner earnings','sard'),
 ('Leverage','Supplied debt / revenue','Secondary rank-distance factor','Not net debt, capital structure in full, or total risk','ipev'),
 ('Growth','Dated historical revenues and validated events','Unavailable for predictive fitting','Current news is not a historical growth label','ml'),
 ('Capital intensity and efficiency','Capex, working capital, asset turnover','Not currently available','Do not substitute marketing claims or EBITDA margin','ml'),
 ('Lifecycle and economic moat','Supported stage, retention, concentration, durable advantage','Evidence-led review only','No generic moat or maturity score from a short homepage','ipev'),
]

METHOD_NOTES = [
 ('Equal financial rank weights','Mean absolute percentile distance across permitted factors; rerank within a textual shortlist.','sard','Adaptation: our revenue, EBITDA margin and debt/revenue differ from the paper; equal weighting is a baseline.'),
 ('Factor ablation','Run all seven nonempty subsets of three financial factors and a business-only control.','selection','Diagnoses sensitivity; repeatedly inspecting 19 cases cannot certify an optimal subset.'),
 ('Training-selected weights','Five inner folds select among 15 nonnegative quarter-step weight triples; all 19 evaluation cases are excluded from fitting and peer pools.','ml','Inspired by supervised valuation; not a reproduction of GBM peer-weight decomposition. No genuine temporal backtest.'),
 ('Reciprocal rank fusion','Sum 1/(60+rank) over MPNet, TF-IDF and LSA lists; no addition of incompatible raw score scales.','rrf','Document-retrieval precedent; the constant 60 and company application are design choices.'),
 ('Source-bounded pair review','Judge observed business, role, customers and unmatched scope from explicit website passages; validate source quotations.','llm_peers','Local 3B-model diagnostic, not a replication of the paper and not independent human labels.'),
 ('Median multiple','Median positive selected public-peer EV/EBITDA.','ipev','Robust baseline; requires common EBITDA definitions and measurement periods for actual valuation.'),
 ('Harmonic multiple','n divided by the sum of reciprocal positive peer multiples.','multiples','Tests sensitivity to high multiples; the cited evidence does not guarantee performance on this sample.'),
 ('Geometric multiple','Exponential of mean log positive peer multiples.','ipev','Transparent log-scale sensitivity check; no claim that IPEV mandates it.'),
 ('Reciprocal-rank weighting','Weighted arithmetic mean with weights proportional to 1/selection rank.','rrf','Heuristic sensitivity arm; retrieval fusion research does not validate these valuation weights.'),
]

def source_links(keys):
    return '; '.join(f'[{SOURCES[k][0]}]({SOURCES[k][1]})' for k in keys)
