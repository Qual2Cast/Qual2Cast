"""Compare train-fitted industry regressions with public-peer multiples."""

from __future__ import annotations

import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd
from sklearn.linear_model import ElasticNetCV, LinearRegression, RidgeCV


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "v1/scripts"))
import sectors  # noqa: E402

V1 = ROOT / "outputs-local/v1"
OUT = V1 / "integration/regression"


def main() -> None:
    split = pd.read_csv(V1 / "split/20261027T204930Z/split.csv", dtype=str).set_index("IQ_COMPANY_ID")
    financials = pd.read_csv(V1 / "universe/20261025T060358Z/financials.csv",
                             dtype={"IQ_COMPANY_ID": str}).set_index("IQ_COMPANY_ID")
    universe = pd.read_csv(V1 / "universe/20261025T060358Z/universe.csv",
                           dtype=str).set_index("IQ_COMPANY_ID")
    ff49 = sectors.sector_table(universe)["ff49"]
    ids = split.index.tolist()
    data = financials.reindex(ids)
    numeric = pd.DataFrame({"log_revenue": np.log(data["target_revenue"].clip(lower=1)),
                            "margin": data["target_margin"],
                            "debt_to_revenue": data["target_debt_to_revenue"]}, index=ids)
    numeric = numeric.join(pd.get_dummies(ff49.reindex(ids), prefix="ff49", dtype=float))
    facets = pd.read_csv(V1 / "integration/sources/facets_sonnet_corrected.csv",
                         dtype=str).set_index("IQ_COMPANY_ID").reindex(ids)
    qualitative = []
    for field in ("customer_segment", "revenue_model", "value_chain_position",
                  "geography_served", "distribution_channels"):
        categories = facets[f"{field}_category"].where(facets[f"{field}_status"] == "filled", "")
        qualitative.append(categories.fillna("").str.get_dummies(sep=";").add_prefix(f"{field}_"))
    feature_sets = {"financial": numeric,
                    "financial + business facets": numeric.join(pd.concat(qualitative, axis=1))}
    train = split.index[split["sample"] == "training"]
    test = split.index[split["sample"] == "holdout"]
    y_train = np.log(data.loc[train, "target_ev_to_ebitda"].to_numpy())
    actual = data.loc[test, "target_ev_to_ebitda"]
    if not np.isfinite(y_train).all():
        raise ValueError("Regression targets have invalid values")
    rows = []
    industry_median = data.loc[train].groupby(ff49.reindex(train))["target_ev_to_ebitda"].median()
    fallback = data.loc[train, "target_ev_to_ebitda"].median()
    for target in test:
        rows.append({"target": target, "method": "FF49 training median",
                     "estimate": industry_median.get(ff49[target], fallback), "actual": actual[target]})
    model_settings = {}
    for feature_name, features in feature_sets.items():
        means = features.loc[train].median()
        features = features.fillna(means)
        center = features.loc[train].mean()
        scale = features.loc[train].std().replace(0, 1)
        X_train = ((features.loc[train] - center) / scale).to_numpy()
        X_test = ((features.loc[test] - center) / scale).to_numpy()
        if not np.isfinite(X_train).all() or not np.isfinite(X_test).all():
            raise ValueError(f"Invalid {feature_name} features")
        models = {
            "OLS": LinearRegression(),
            "Ridge": RidgeCV(alphas=np.logspace(-2, 3, 12), cv=5),
            "Elastic net": ElasticNetCV(alphas=np.logspace(-3, 0, 12),
                l1_ratio=[.1, .5, .9], cv=5, max_iter=10000, random_state=2026),
        }
        for short_name, model in models.items():
            name = f"{short_name}: {feature_name}"
            model.fit(X_train, y_train)
            estimate = np.exp(model.predict(X_test))
            model_settings[name] = {"alpha": getattr(model, "alpha_", None),
                                    "l1_ratio": getattr(model, "l1_ratio_", None)}
            rows.extend({"target": target, "method": name, "estimate": float(value),
                         "actual": actual[target]} for target, value in zip(test, estimate))
    peer = pd.read_csv(V1 / "integration/scope_eval/holdout_target_errors.csv")
    peer = peer[peer["method"] == "Sonnet dated corrections: top 10 weighted mean"]
    rows.extend({"target": row.target, "method": "B3 similarity-weighted peers",
                 "estimate": row.estimate, "actual": row.actual} for row in peer.itertuples())
    predictions = pd.DataFrame(rows)
    predictions["ape"] = abs(predictions["estimate"] / predictions["actual"] - 1) * 100
    summary = predictions.groupby("method", as_index=False).agg(
        targets=("target", "nunique"), median_ape=("ape", "median"), mean_ape=("ape", "mean"))
    OUT.mkdir(parents=True, exist_ok=True)
    predictions.to_csv(OUT / "predictions.csv", index=False)
    summary.to_csv(OUT / "summary.csv", index=False)
    (OUT / "run.json").write_text(json.dumps({"train": len(train), "test": len(test),
       "model_settings": model_settings,
       "features": {name: list(table.columns) for name, table in feature_sets.items()},
       "fit_metric": "log EV/EBITDA; alpha selected by five-fold training CV",
       "caution": "Public-as-private development targets; financial dates and units need confirmation"}, indent=2), encoding="utf-8")
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
