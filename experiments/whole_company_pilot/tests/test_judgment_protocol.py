import pytest
from modular_validation.judgment_protocol import derive_ledger
from modular_validation.judgments import validate_judgment
from modular_validation.judgment_protocol import replay_raw_record
import json


def test_ledger_retains_all_unmatched_businesses_without_mutating_model_output():
    raw = dict(grade=2, scope_adequate=True, matched_activity_ids=[['A0','B1']], reason='Overlap with differences')
    value = derive_ledger(raw, activities_a=3, activities_b=2)
    assert value['unmatched_A'] == ['A1','A2']
    assert value['unmatched_B'] == ['B0']
    assert 'unmatched_A' not in raw
    assert validate_judgment(value, activities_a=3, activities_b=2)['grade'] == 2


@pytest.mark.parametrize('matches', [[['B0','A0']], [['A9','B0']], [['A0']], [[]]])
def test_invalid_matches_are_not_silently_corrected(matches):
    with pytest.raises(ValueError, match='invalid_matched_activity_ids'):
        derive_ledger(dict(grade=2, scope_adequate=True, matched_activity_ids=matches, reason='Reason'),
                      activities_a=1, activities_b=1)


def test_valid_empty_match_can_be_mismatch_but_not_positive_and_can_abstain():
    base = dict(grade=0, scope_adequate=True, matched_activity_ids=[], reason='Different functions')
    result = derive_ledger(base, activities_a=2, activities_b=1)
    assert result['unmatched_A'] == ['A0','A1']
    with pytest.raises(ValueError, match='positive_grade_without_supported_activity_match'):
        derive_ledger({**base, 'grade':1}, activities_a=2, activities_b=1)
    result = derive_ledger({**base, 'scope_adequate':False}, activities_a=2, activities_b=1)
    assert validate_judgment(result, activities_a=2, activities_b=1)['grade'] is None


def test_raw_replay_rejects_tampered_cached_grade_and_ledger():
    raw = dict(grade=0, scope_adequate=True, matched_activity_ids=[], reason='Different businesses')
    profile = {'known_activities':[{'activity':'Supported activity'}]}
    record = {'grade':3, 'model_parsed':dict(raw, grade=3), 'parsed':dict(raw, grade=3),
              'generation':{'text':json.dumps(raw), 'input_truncated':False, 'output_hit_limit':False}}
    result = replay_raw_record(record, profile_a=profile, profile_b=profile, derived_ledger=True)
    assert result['grade'] == 0
    assert result['parsed']['unmatched_A'] == ['A0']
    assert result['model_parsed'] == raw
    record['generation']['text'] = '{bad JSON'
    assert replay_raw_record(record, profile_a=profile, profile_b=profile, derived_ledger=True)['grade'] is None


from modular_validation.judgment_protocol import bind_content_cache

def test_identical_ordered_evidence_can_bind_reverse_pair_with_lineage():
    messages=[{'role':'system','content':'SYSTEM'}, {'role':'user','content':'EXACT DOSSIERS'}]
    raw={'key':'same', 'target_id':'X', 'candidate_id':'H', 'reverse':False,
         'generation':{'prompt':'SYSTEM\nEXACT DOSSIERS', 'text':'unchanged'}}
    job={'key':'same', 'target_id':'H', 'candidate_id':'X', 'reverse':True,'messages':messages}
    bound=bind_content_cache(raw,job,origin_messages=messages)
    assert bound['target_id']=='H' and bound['cache_origin_identity']['target_id']=='X'
    assert bound['generation']==raw['generation'] and raw['target_id']=='X'

@pytest.mark.parametrize('change',['key','evidence','prompt'])
def test_cache_rebinding_never_accepts_changed_evidence(change):
    messages=[{'role':'user','content':'original'}]
    raw={'key':'same','target_id':'A','candidate_id':'B','reverse':False,'generation':{'prompt':'original'}}
    job={'key':'same','target_id':'C','candidate_id':'D','reverse':False,'messages':messages}
    if change=='key':job['key']='different'
    if change=='evidence':job['messages']=[{'role':'user','content':'different'}]
    if change=='prompt':raw['generation']['prompt']='different'
    with pytest.raises(ValueError,match='content_cache'):
        bind_content_cache(raw,job,origin_messages=messages)
