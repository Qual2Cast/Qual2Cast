"""A transparent deterministic ledger for a provisional model comparison.

Complements record unpaired activities; they do not imply that the model has
correctly considered their importance. Invalid model matches are never repaired.
"""
from copy import deepcopy
from .judgments import validate_judgment
from .judgments import revalidate_judgment_record
from .local_llm import _parse

VERSION = 'derived-unmatched-ledger-v1-2026-10-19'


def bind_content_cache(record, job, *, origin_messages):
    """Bind an exact content-addressed response to a requested pair, with lineage.

    The same ordered dossiers can occur in a reverse test or when evidence is
    empty. Company identity metadata is not part of the model's input hash.
    Reuse requires identical reconstructed messages; original bytes stay intact.
    """
    if record.get('key') != job.get('key') or origin_messages != job.get('messages'):
        raise ValueError('content_cache_evidence_or_key_mismatch')
    generation = record.get('generation')
    if isinstance(generation, dict):
        prompt = generation.get('prompt', '')
        if not all(message['content'] in prompt for message in origin_messages):
            raise ValueError('content_cache_raw_prompt_mismatch')
    result = deepcopy(record)
    identity = ('target_id', 'candidate_id', 'reverse')
    if any(record.get(field) != job[field] for field in identity):
        result['cache_origin_identity'] = {field: record.get(field) for field in identity}
        result['cache_binding_policy'] = 'identical_ordered_evidence_and_raw_prompt; identity_metadata_rebound'
    result.update({field: job[field] for field in identity})
    return result


def derive_ledger(parsed, *, activities_a, activities_b):
    if not isinstance(parsed, dict):
        raise ValueError('comparison_must_be_object')
    result = deepcopy(parsed)
    matched = result.get('matched_activity_ids')
    allowed_a = {f'A{i}' for i in range(activities_a)}
    allowed_b = {f'B{i}' for i in range(activities_b)}
    if not isinstance(matched, list):
        raise ValueError('missing_matched_activity_ids')
    for pair in matched:
        if (not isinstance(pair, list) or len(pair) != 2
                or not all(isinstance(v, str) for v in pair)
                or pair[0] not in allowed_a or pair[1] not in allowed_b):
            raise ValueError('invalid_matched_activity_ids')
    result['unmatched_A'] = [f'A{i}' for i in range(activities_a)
                             if f'A{i}' not in {p[0] for p in matched}]
    result['unmatched_B'] = [f'B{i}' for i in range(activities_b)
                             if f'B{i}' not in {p[1] for p in matched}]
    validate_judgment(result, activities_a=activities_a, activities_b=activities_b)
    return result


def replay_raw_record(record, *, profile_a, profile_b, derived_ledger=False):
    """Reparse model text; never trust a cached grade or derived ledger."""
    result = deepcopy(record)
    result['parsed'] = {}
    parse_error = None
    generation = result.get('generation')
    if isinstance(generation, dict) and isinstance(generation.get('text'), str):
        try:
            parsed = _parse(generation['text'])
            if derived_ledger:
                result['model_parsed'] = deepcopy(parsed)
                parsed = derive_ledger(parsed,
                    activities_a=len((profile_a or {}).get('known_activities', [])),
                    activities_b=len((profile_b or {}).get('known_activities', [])))
            result['parsed'] = parsed
        except (TypeError, ValueError) as exc:
            parse_error = str(exc)
    else:
        parse_error = 'missing_raw_generation_text'
    checked = revalidate_judgment_record(result, profile_a=profile_a, profile_b=profile_b)
    if parse_error and checked.get('error') not in {
            'missing_or_explicitly_truncated_company_activity_evidence',
            'unknown_generation_truncation_status', 'truncated_input_or_output'}:
        checked['grade'] = None
        checked['error'] = parse_error
    checked['replayed_from_raw_generation_text'] = True
    return checked
