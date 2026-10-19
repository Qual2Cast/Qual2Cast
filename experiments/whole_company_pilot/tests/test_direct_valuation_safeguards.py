"""Synthetic only: import definitions without calling the outcome-loading runner."""
import importlib.util
import json
from pathlib import Path
import unittest

import numpy as np
import pandas as pd

SOURCE = Path(__file__).resolve().parents[1] / "scripts/run_direct_valuation.py"
SPEC = importlib.util.spec_from_file_location("direct_valuation_synthetic_test", SOURCE)
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


class DirectValuationSafeguards(unittest.TestCase):
    def test_declared_hyperparameter_mismatch_is_rejected(self):
        models = ['Ridge(alpha=10)', 'HistGradientBoostingRegressor(max_iter=100,max_leaf_nodes=15,l2_regularization=1,early_stopping=False)']
        value = {'direct_valuation_challengers': {'models': models, 'seed': 4511}}
        self.assertEqual(runner.frozen_model_configuration(value)['seed'], 4511)
        value['direct_valuation_challengers']['seed'] = 0
        with self.assertRaises(RuntimeError):
            runner.frozen_model_configuration(value)
        value['direct_valuation_challengers']['seed'] = 4511
        value['direct_valuation_challengers']['models'] = ['Ridge(alpha=1)']
        with self.assertRaises(RuntimeError):
            runner.frozen_model_configuration(value)

    def test_missing_financial_fields_are_visible_without_new_threshold(self):
        row = pd.Series([np.nan, np.nan, np.nan], index=['revenue', 'margin', 'leverage'])
        result = runner.prediction_diagnostics(12., 10., 2., row)
        self.assertEqual(result['financial_missing_count'], 3)
        self.assertEqual(json.loads(result['financial_missing_fields']), list(row.index))
        self.assertEqual(result['prediction'], 12.)
        self.assertAlmostEqual(result['snapshot_ape'], .2)

    def test_nonfinite_predictions_never_emit_errors_or_estimates(self):
        row = pd.Series([1.], index=['synthetic_predictor'])
        for prediction in [np.inf, -np.inf, np.nan]:
            with self.subTest(prediction=prediction):
                result = runner.prediction_diagnostics(prediction, 10., 2., row)
                self.assertFalse(result['finite_prediction'])
                self.assertIsNone(result['prediction'])
                self.assertIsNone(result['snapshot_ape'])
                self.assertIsNone(result['snapshot_absolute_log_error'])

    def test_missing_or_invalid_observed_values_do_not_create_accuracy(self):
        row = pd.Series([1.], index=['synthetic_predictor'])
        for observed, ebitda in [(np.nan, 2.), (0., 2.), (10., -2.)]:
            with self.subTest(observed=observed, ebitda=ebitda):
                result = runner.prediction_diagnostics(12., observed, ebitda, row)
                self.assertEqual(result['prediction'], 12.)
                self.assertIsNone(result['snapshot_ape'])
                self.assertIsNone(result['snapshot_absolute_log_error'])
