"""Reproduce a public issuer reconciliation as an isolated measurement example.

This evidence never enters the simulated private target or comp-selection data.
The parser is specific to the retained BrightView FY2025 reconciliation table.
"""
import re
from valuation.ebitda import from_net_income, adjust_ebitda

SOURCE='https://s22.q4cdn.com/142468460/files/doc_financials/2025/q4/BrightView-8K-Q4FY25-Vf.pdf'


def brightview_reconciliation(text):
    table=text.split('Adjusted Net Income')[0]
    def row(label):
        line=next((x for x in table.splitlines() if x.strip().startswith(label)),None)
        if line is None: raise ValueError('Missing reconciliation row: '+label)
        tokens=re.findall(r'\(\s*\d+\.\d+\s*\)|\d+\.\d+|—',line[len(line)-len(line.lstrip())+len(label):])
        if len(tokens)!=4: raise ValueError('Expected FY2025, FY2024, Q4 2025, Q4 2024')
        return [0. if t=='—' else -float(t.strip('() ')) if t.startswith('(') else float(t) for t in tokens]
    fields={'net_income':'Net income','interest':'Interest expense, net','tax':'Income tax expense',
            'depreciation':'Depreciation expense','amortization':'Amortization expense'}
    records=[]
    for col,year in enumerate((2025,2024)):
        components={k:row(label)[col] for k,label in fields.items()}
        base=from_net_income(components)
        ledger=[{'id':key,'amount':row(label)[col],'category':key,'source_url':SOURCE,
                 'decision':'pending','reviewer':None,'normal_recurring_cash_cost':None,
                 'rationale':'Issuer disclosure; appropriateness as maintainable earnings not independently reviewed'}
                for key,label in [('transformation','(a)'),('divestiture_gain','Gain on divestiture'),
                                  ('stock_compensation','Equity-based compensation'),('debt_extinguishment','Debt extinguishment')]]
        issuer=adjust_ebitda(base['value'],ledger,'issuer_reconciliation')
        # Find the numeric total, avoiding the preceding section heading.
        total=next(x for x in table.splitlines() if x.strip().startswith('Adjusted EBITDA') and re.search(r'\d',x))
        disclosed=float(re.findall(r'\d+\.\d+',total)[col])
        if abs(issuer['value']-disclosed)>.11: raise ValueError('Reconciliation does not tie within reported rounding')
        records.append({'year':year,'units':'USD million','period_end':f'{year}-09-30',
            'source_url':SOURCE,'pdf_page':15,'components':components,'base_ebitda':base['value'],
            'issuer_adjusted_ebitda':issuer['value'],'issuer_disclosed_total':disclosed,
            'adjustments':ledger,'reviewed_adjustment_result':adjust_ebitda(base['value'],ledger),
            'status':'isolated_public_measurement_example_not_target_input'})
    return records
