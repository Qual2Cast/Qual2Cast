import sys, pandas as pd
sys.path.insert(0, "v0")
from universe import build_universe

FACETS_CSV = "outputs-local/comps/facets_riya/tables/facets.csv"
tickers = ["PCTY","BV","ROAD","LMB","BRO","ADUS","DXPE","SLGN","BGS","WEN",
           "CSL","AFG","NWSA","AZZ","BOC",
           "TECH","PBYI","BLBD","KAI","DORM","FRPT","HEOL","UFPT","MSA",
           "TASK","BUKS","NGS","ACEL","NRC","DV","LUCK","FLUT","CCC",
           "SNFC.A","RYAN","CRVL","GLIB.A","JBHT","BBCP","BBW"]

companies, _ = build_universe()
iq = companies.set_index("target_ciq_ticker")["IQ_COMPANY_ID"]
f = pd.read_csv(FACETS_CSV, dtype=str).fillna("")
f = f[f["business_id"] == "B1"].set_index("IQ_COMPANY_ID")
rows = []
for t in tickers:
    if iq[t] not in f.index:
        value = "NOT FILLED YET"
    else:
        r = f.loc[iq[t]]
        value = r["company_size"] if r["company_size_status"] == "filled" else r["company_size_status"]
    rows.append({"ticker": t, "facet_id": "F9", "haiku_value": value})
pd.DataFrame(rows).to_csv("haiku_f9_values.csv", index=False)
print(pd.DataFrame(rows).to_string(index=False))
