"""Static reading aids for the completed exploratory pilot; no model selection."""
from pathlib import Path
import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(os.environ.get('QUAL2CAST_EXPERIMENT_DIR', ROOT / 'outputs-local/pilot-validation-2026-10-18'))
if not OUT.is_absolute():
    OUT = ROOT / OUT


def main():
    results = pd.read_csv(OUT / 'comparison/configuration_results.csv')
    targets = pd.read_csv(OUT / 'comparison/configuration_target_errors.csv')
    primary = results[(results.k == 5) & results.aggregation.eq('median')].sort_values('method')
    folder = OUT / 'delivery-figures'
    folder.mkdir(exist_ok=True)
    plt.rcParams.update({'font.size': 10, 'axes.spines.top': False,
                         'axes.spines.right': False, 'figure.facecolor': 'white',
                         'savefig.facecolor': 'white'})
    names = primary.method.tolist()
    y = np.arange(len(names))
    fig, ax = plt.subplots(figsize=(13, 12))
    ax.barh(y + .2, primary.own_available_targets, .35, label='Snapshot error available', color='#446D99')
    ax.barh(y - .2, primary.evidence_guard_accepted_targets, .35, label='Activity evidence guard passed', color='#40A58F')
    ax.set_yticks(y, names)
    ax.invert_yaxis()
    ax.set_xticks(range(10))
    ax.set_xlim(0, 10)
    ax.set_xlabel('Targets out of nine originally fresh cases (now exploratory development)')
    strict_max = int(primary.strict_indication_available_targets.max())
    ax.set_title(f'Coverage at k = 5, median aggregation\nEvidence support is not business approval; maximum strict aligned indications per method: {strict_max}', loc='left', pad=15)
    ax.legend(loc='lower right', frameon=False)
    fig.tight_layout()
    fig.savefig(folder / 'configuration_coverage.png', dpi=160)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(13, 12))
    for i, row in enumerate(primary.itertuples()):
        a, b = row.baseline_median_ape_common, row.method_median_ape_common
        if np.isfinite(a) and np.isfinite(b):
            ax.plot([a * 100, b * 100], [i, i], color='#C4C9D0', lw=2)
            ax.scatter(a * 100, i, marker='o', color='#446D99', s=24)
            ax.scatter(b * 100, i, marker='D', color='#AA5A25', s=24)
    labels = [f'{r.method}  (n={r.common_paired_targets})' for r in primary.itertuples()]
    ax.set_yticks(y, labels)
    ax.invert_yaxis()
    ax.scatter([], [], color='#446D99', label='Dense baseline on the same targets')
    ax.scatter([], [], marker='D', color='#AA5A25', label='Compared method')
    ax.set_xlabel('Median absolute percentage error (%) against supplied undated multiples')
    ax.set_title('Paired descriptive comparison: k = 5, median aggregation\nMatching coverage and errors are separate; no independent winner established', loc='left', pad=15)
    ax.legend(frameon=False, loc='lower right')
    ax.grid(axis='x', alpha=.2)
    fig.tight_layout()
    fig.savefig(folder / 'paired_snapshot_error.png', dpi=160)
    plt.close(fig)

    selected = targets[(targets.k == 5) & targets.aggregation.eq('median')]
    pivot = selected.pivot(index='method', columns='target_ticker', values='snapshot_ape').reindex(index=names)
    pivot = pivot.reindex(columns=[x for x in pivot if x != 'PCTY'] + ['PCTY'])
    cmap = plt.get_cmap('YlOrRd').copy()
    cmap.set_bad('#E2E6EB')
    fig, ax = plt.subplots(figsize=(13, 13))
    im = ax.imshow(np.log1p(pivot.to_numpy(float)), aspect='auto', cmap=cmap)
    ax.set_xticks(range(len(pivot.columns)), [c + '*' if c == 'PCTY' else c for c in pivot])
    ax.set_yticks(y, names)
    for i in range(len(pivot)):
        for j in range(len(pivot.columns)):
            v = pivot.iloc[i, j]
            ax.text(j, i, f'{v * 100:.0f}%' if pd.notna(v) else 'NA', ha='center', va='center', fontsize=8)
    ax.set_title('Company-level snapshot errors: k = 5, median aggregation\nAll ten are exploratory; *PCTY was also the legacy development case', loc='left', pad=15)
    fig.colorbar(im, ax=ax, fraction=.025, pad=.02, label='log(1 + absolute percentage error); cell labels show raw error')
    fig.tight_layout()
    fig.savefig(folder / 'target_sensitivity.png', dpi=160)
    plt.close(fig)
    print('DELIVERY_FIGURES_COMPLETE', len(list(folder.glob('*.png'))))


if __name__ == '__main__':
    main()
