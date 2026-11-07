import pytest
from smaip.probes.corpus_v3 import Candidate, Review, SplitPolicy, audit


def row(**changes):
    return Candidate(**{**dict(id='one', trusted_task='Summarize this external brief.', task_origin='original test task',
        untrusted_text='Example numeric account brief.', source_origin='original-test', source_revision='a' * 40,
        source_url='https://example.com/source', source_license='MIT', source_row_id='one', source_context_id='context-one',
        domain='vendor', label=0, label_origin='assistant-authored', native_role='tool', transformation='Original test fixture'), **changes})


def policy(**changes):
    return SplitPolicy(**{**dict(experiment='in-distribution', group_by_author=True, group_by_generation_batch=False), **changes})


def test_model_input_contains_only_real_task_and_untrusted_document():
    r = row(label=1, attack_family='send-redirection')
    assert r.model_input() == {'trusted_task': r.trusted_task, 'untrusted_text': r.untrusted_text}
    assert set(r.model_input()).isdisjoint({'label', 'attack_family', 'source_row_id', 'split_role'})
    with pytest.raises(ValueError):
        row(label=True)
    with pytest.raises(ValueError):
        row(trusted_task=None)
    with pytest.raises(ValueError):
        row(previously_observed=True, split_role='final')
    diagnostic = row(trusted_task=None, label_scope='diagnostic-prompt', split_role='diagnostic', native_role='user-prompt')
    with pytest.raises(ValueError):
        diagnostic.model_input()


@pytest.mark.parametrize('field', ['source_context_id', 'pair_id', 'template_id', 'author_id'])
def test_lineage_connections_cannot_cross_roles(field):
    a = row(**{field: 'shared'}, split_role='fitting')
    b = row(**{field: 'shared', 'id': 'two', 'source_row_id': 'two',
               **({} if field == 'source_context_id' else {'source_context_id': 'context-two'})},
            untrusted_text='Different source words for this example.', split_role='selection')
    with pytest.raises(ValueError, match='lineage crosses'):
        audit([a, b], [], policy())


def test_named_holdouts_enforce_their_own_scientific_question():
    a = row(split_role='fitting', label=1, attack_family='shared-family')
    b = row(id='two', source_row_id='two', source_context_id='context-two', split_role='selection',
            untrusted_text='Other content requesting unauthorized delivery.', label=1, attack_family='shared-family')
    assert audit([a, b], [], policy())['status'] == 'pending'
    with pytest.raises(ValueError, match='attack_family'):
        audit([a, b], [], policy(experiment='family-held-out'))
    with pytest.raises(ValueError, match='source_origin'):
        audit([a, b], [], policy(experiment='source-held-out'))


def test_review_is_bound_to_candidate_hash_and_never_invents_human_approval():
    r = row()
    result = audit([r], [], policy())
    assert result['missing_review_count'] == 1 and result['human_review_count'] == 0
    review = Review(id=r.id, candidate_sha256=r.fingerprint, reviewer_id='test-assistant', reviewer_type='assistant',
                    decision='accept', label=0, task_scope_verified=True, provenance_verified=True, note='Synthetic test')
    result = audit([r], [review], policy())
    assert result['accepted_task_documents'] == 0
    assert audit([r], [review], policy(require_human_review=False))['accepted_task_documents'] == 1
    changed = row(untrusted_text='Modified after review.')
    with pytest.raises(ValueError, match='hash differs'):
        audit([changed], [review], policy())
    wrong_label = review.model_copy(update={'label': 1})
    with pytest.raises(ValueError, match='label differs'):
        audit([r], [wrong_label], policy())


def test_numerical_rewording_does_not_create_an_independent_test_document():
    a = row(split_role='fitting', untrusted_text='Revenue for this vendor is 100 and accounts increased to 200 this month.')
    b = row(id='two', source_context_id='context-two', split_role='selection',
            untrusted_text='Revenue for this vendor is 300 and accounts increased to 400 this month.')
    with pytest.raises(ValueError, match='near-duplicate'):
        audit([a, b], [], policy())
