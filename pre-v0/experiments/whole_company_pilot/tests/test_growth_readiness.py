"""Entirely SYNTHETIC contract tests. No real company figures or forecasts."""
from copy import deepcopy
from datetime import date
import hashlib
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.modular_validation import growth_readiness as g

TEXT='Synthetic Company launched a new software platform on January 2, 2020.'
H=hashlib.sha256(TEXT.encode()).hexdigest()


def source():
    return dict(source_id='synthetic-source',company_id='SYNTH_A',source_url='https://issuer.example/news/launch',
      source_type='company_press',content_sha256='a'*64,evidence_text_sha256=H,
      captured_at='2020-01-03T12:00:00Z',published_at='2020-01-02T12:00:00Z',
      first_available_at='2020-01-03T12:00:00Z',availability_basis='first_observed_capture')


def event():
    return dict(event_id='synthetic-event',event_key='SYNTH_A|launch|software|2020-01-02',company_id='SYNTH_A',
      subject_company_id='SYNTH_A',subject_role='own_company',event_type='product_launch',
      event_status='completed',event_date='2020-01-02',signal_duration='unknown',
      evidence_quote=TEXT,source=source())


def options():
    return dict(cutoff='2020-01-04T23:59:59Z',company_role='target',regime='website_only',
                allowed_domains=['issuer.example'],evidence_texts={'synthetic-source':TEXT})


def revenue(year,value=100,company='SYNTH_A'):
    return dict(observation_id=f'{company}-{year}-v1',company_id=company,revision_id='v1',metric='revenue',
      frequency='annual',period_start=f'{year}-01-01',period_end=f'{year}-12-31',
      first_available_at=f'{year+1}-02-01T12:00:00Z',value=value,value_status='actual',
      currency='USD',unit='million',consolidation_scope='consolidated',accounting_basis='synthetic_GAAP',
      is_restated=False,sources=[{'url':f'https://issuer.example/data/{year}','sha256':'b'*64}])


def quarter(start,end,value=25):
    r=revenue(int(start[:4]),value)
    r.update(observation_id='synthetic-q-'+start,period_start=start,period_end=end,frequency='quarterly',
             first_available_at=str(date.fromisoformat(end).replace(day=28))+'T12:00:00Z')
    # Publication after the period: fixed synthetic timestamp for all four.
    r['first_available_at']='2021-02-01T12:00:00Z'
    return r


def fold_row(company,start_year,origin_year):
    return dict(row_id=f'{company}-{origin_year}',company_id=company,
      origin_at=f'{origin_year}-03-01T00:00:00Z',label_period_start=f'{start_year}-12-31',
      label_period_end=f'{start_year+3}-12-31',label_available_at=f'{start_year+4}-02-01T12:00:00Z',
      base_revenue_available_at=f'{start_year+1}-02-01T12:00:00Z',
      feature_sources=[{'source_id':'synthetic-feature-'+str(origin_year),
                       'first_available_at':f'{origin_year}-02-01T12:00:00Z'}])


class SyntheticGrowthContracts(unittest.TestCase):
    def test_supported_event_passes_without_predictive_weight(self):
        r=g.validate_event(event(),**options())
        self.assertTrue(r['valid']);self.assertIsNone(r['predictive_weight'])
        self.assertEqual(r['signal_duration'],'unknown')

    def test_publication_date_does_not_backdate_live_capture(self):
        e=event();e['source']['first_available_at']='2020-01-02T12:00:00Z'
        self.assertIn('live_capture_cannot_backdate_availability',g.validate_event(e,**options())['errors'])

    def test_retained_archive_proof_allows_earlier_availability(self):
        e=event();s=e['source'];s['first_available_at']='2020-01-02T13:00:00Z';s['availability_basis']='archived_capture'
        s['availability_proof']={'url':'https://archive.example/20200102','sha256':'c'*64,'observed_at':'2020-01-02T13:00:00Z'}
        self.assertTrue(g.validate_event(e,**options())['valid'])

    def test_future_availability_is_excluded(self):
        o=options();o['cutoff']='2020-01-03T11:59:59Z'
        self.assertIn('source_not_available_at_cutoff',g.validate_event(event(),**o)['errors'])

    def test_quote_and_source_hash_are_both_checked(self):
        e=event();e['evidence_quote']='Unsupported invented expansion.'
        self.assertIn('evidence_quote_not_literal',g.validate_event(e,**options())['errors'])
        e=event();e['source']['evidence_text_sha256']='0'*64
        self.assertIn('evidence_text_hash_mismatch',g.validate_event(e,**options())['errors'])

    def test_target_filing_always_rejected(self):
        s=source();s['source_type']='filing'
        r=g.validate_source(s,company_role='target',regime='candidate_filing_enriched',allowed_domains=['issuer.example'])
        self.assertIn('target_filing_prohibited',r['errors'])

    def test_candidate_filing_requires_declared_arm(self):
        s=source();s['source_type']='filing'
        self.assertFalse(g.validate_source(s,company_role='candidate',regime='website_only',allowed_domains=['issuer.example'])['valid'])
        self.assertTrue(g.validate_source(s,company_role='candidate',regime='candidate_filing_enriched',allowed_domains=['issuer.example'])['valid'])

    def test_financial_source_is_separate_and_url_spoof_fails(self):
        s=source();s['source_type']='approved_financial_data'
        self.assertFalse(g.validate_source(s,company_role='target',regime='website_only',allowed_domains=['issuer.example'])['valid'])
        self.assertTrue(g.validate_source(s,company_role='target',regime='mentor_permitted_financial',allowed_domains=['issuer.example'])['valid'])
        s['source_url']='https://issuer.example.attacker.example/news'
        self.assertFalse(g.validate_source(s,company_role='target',regime='mentor_permitted_financial',allowed_domains=['issuer.example'])['valid'])

    def test_customer_activity_not_own_company_event(self):
        e=event();e['subject_role']='customer'
        self.assertIn('customer_partner_or_executive_event_not_own_activity',g.validate_event(e,**options())['errors'])

    def test_planned_effective_date_not_completed_event(self):
        e=event();e['effective_date']='2021-01-01'
        self.assertFalse(g.validate_event(e,**options())['valid'])
        e['event_status']='announced'
        self.assertTrue(g.validate_event(e,**options())['valid'])

    def test_duplicate_publications_count_once(self):
        a,b=event(),event();b['event_id']='synthetic-event-copy'
        result=g.validate_event_batch([b,a],**options())
        self.assertEqual(len(result['included_event_ids']),1)
        self.assertEqual(sum(r['duplicate_event_key'] for r in result['rows']),1)

    def test_duplicate_event_ids_rejected(self):
        result=g.validate_event_batch([event(),event()],**options())
        self.assertEqual(result['included_event_ids'],[])

    def test_deduplication_uses_utc_availability_not_iso_text_order(self):
        a,b=event(),event();a['event_id']='later';b['event_id']='earlier'
        a['source']['captured_at']=a['source']['first_available_at']='2020-01-03T10:00:00-03:00'
        b['source']['captured_at']=b['source']['first_available_at']='2020-01-03T14:00:00+02:00'
        self.assertEqual(g.validate_event_batch([a,b],**options())['included_event_ids'],['earlier'])

    def test_empty_panel_and_malformed_lineage_are_not_ready(self):
        self.assertFalse(g.validate_revenue_panel([])['valid'])
        r=revenue(2020);r['sources']=[None]
        self.assertFalse(g.validate_revenue_panel([r])['valid'])

    def test_naive_timestamps_rejected(self):
        e=event();e['source']['first_available_at']='2020-01-03T12:00:00'
        self.assertIn('invalid_first_available_at',g.validate_event(e,**options())['errors'])
        with self.assertRaises(ValueError):g.validate_event(event(),**{**options(),'cutoff':'2020-01-04'})

    def test_repeated_firm_years_are_valid_but_duplicate_period_is_not(self):
        self.assertTrue(g.validate_revenue_panel([revenue(2020),revenue(2021)])['valid'])
        r=revenue(2020);other=deepcopy(r);other['observation_id']='duplicate-with-new-id'
        self.assertFalse(g.validate_revenue_panel([r,other])['valid'])

    def test_restatement_vintage_selected_as_of_date(self):
        first=revenue(2020,100);restated=deepcopy(first)
        restated.update(observation_id='restated-2020',revision_id='v2',value=110,is_restated=True,first_available_at='2022-02-01T00:00:00Z')
        panel=[first,restated]
        self.assertTrue(g.validate_revenue_panel(panel)['valid'])
        self.assertEqual(g.select_revenue_vintage(panel,cutoff='2021-12-31T00:00:00Z')[0]['value'],100)
        self.assertEqual(g.select_revenue_vintage(panel,cutoff='2022-12-31T00:00:00Z')[0]['value'],110)

    def test_restatement_cannot_silently_change_unit(self):
        a=revenue(2020);b=deepcopy(a)
        b.update(observation_id='restated',revision_id='v2',is_restated=True,unit='thousand',first_available_at='2022-02-01T00:00:00Z')
        self.assertFalse(g.validate_revenue_panel([a,b])['valid'])

    def test_three_year_cagr_is_realized_and_checks_horizon(self):
        r=g.revenue_cagr(revenue(2020,100),revenue(2023,133.1))
        self.assertEqual(r['status'],'available');self.assertAlmostEqual(r['realized_cagr'],.1)
        self.assertFalse(r['is_forecast']);self.assertIsNone(r['uncertainty_interval'])
        self.assertEqual(g.revenue_cagr(revenue(2020),revenue(2021))['reason'],'endpoint_horizon_mismatch')

    def test_cagr_units_and_zero_negative_values(self):
        a,b=revenue(2020),revenue(2023)
        b['currency']='EUR';self.assertEqual(g.revenue_cagr(a,b)['reason'],'incompatible_endpoint_definitions')
        self.assertEqual(g.revenue_cagr(revenue(2020,0),revenue(2023,100))['status'],'undefined')
        self.assertEqual(g.revenue_cagr(revenue(2020,100),revenue(2023,0))['realized_cagr'],-1)
        self.assertEqual(g.revenue_cagr(revenue(2020,-1),revenue(2023))['status'],'unavailable')

    def test_four_quarters_aggregate_with_latest_availability(self):
        qs=[quarter('2020-01-01','2020-03-31'),quarter('2020-04-01','2020-06-30'),
            quarter('2020-07-01','2020-09-30'),quarter('2020-10-01','2020-12-31')]
        r=g.trailing_twelve_month_revenue(qs)
        self.assertEqual(r['status'],'available');self.assertEqual(r['observation']['value'],100)
        self.assertEqual(len(r['lineage_observation_ids']),4)
        self.assertEqual(g.trailing_twelve_month_revenue(qs[:3])['status'],'unavailable')
        qs[1]['period_start']='2020-04-02'
        self.assertEqual(g.trailing_twelve_month_revenue(qs)['reason'],'quarter_gap_or_overlap')

    def test_quarterly_ytd_is_not_added_as_quarter(self):
        r=quarter('2020-01-01','2020-06-30')
        self.assertFalse(g.validate_revenue_panel([r])['valid'])

    def test_valid_rolling_origin_metadata(self):
        train=[fold_row('SYNTH_A',2016,2017)];test=[fold_row('SYNTH_A',2020,2021)]
        r=g.validate_rolling_origin_split(train,test,fit_at='2021-03-01T00:00:00Z',preprocessing_fit_row_ids=[train[0]['row_id']])
        self.assertTrue(r['valid']);self.assertFalse(r['is_model_evaluation'])

    def test_unobservable_training_label_and_feature_leakage(self):
        train=[fold_row('SYNTH_A',2018,2019)];test=[fold_row('SYNTH_A',2020,2021)]
        r=g.validate_rolling_origin_split(train,test,fit_at='2021-03-01T00:00:00Z',preprocessing_fit_row_ids=[])
        self.assertTrue(any('training_label_unavailable_at_fit' in x for x in r['errors']))
        train=[fold_row('SYNTH_A',2016,2017)]
        test[0]['feature_sources'][0]['first_available_at']='2022-01-01T00:00:00Z'
        r=g.validate_rolling_origin_split(train,test,fit_at='2021-03-01T00:00:00Z',preprocessing_fit_row_ids=[])
        self.assertTrue(any('feature_after_origin' in x for x in r['errors']))

    def test_preprocessing_test_rows_and_company_holdout_leakage(self):
        train=[fold_row('SYNTH_A',2016,2017)];test=[fold_row('SYNTH_A',2020,2021)]
        r=g.validate_rolling_origin_split(train,test,fit_at='2021-03-01T00:00:00Z',
            preprocessing_fit_row_ids=[test[0]['row_id']],company_holdout=True)
        self.assertIn('preprocessing_fit_includes_nontraining_rows',r['errors'])
        self.assertIn('company_holdout_overlap',r['errors'])

    def test_unobserved_test_label_cannot_be_scored_yet(self):
        train=[fold_row('SYNTH_A',2016,2017)];test=[fold_row('SYNTH_B',2020,2021)]
        r=g.validate_rolling_origin_split(train,test,fit_at='2021-03-01T00:00:00Z',
            preprocessing_fit_row_ids=[],evaluation_at='2023-12-31T23:59:59Z')
        self.assertTrue(any('label_unobserved_at_evaluation' in x for x in r['errors']))


if __name__=='__main__': unittest.main(verbosity=2)
