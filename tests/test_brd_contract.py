import math
import pytest
from smaip.eval.contract import EvalConfig, contract_manifest, evaluation_matrix
from smaip.probes.low_fpr import calibrate, evaluate_frozen


def test_topology_and_detector_are_separate_and_legacy_labels_stay_explicit():
    matrix = {c.name: c for c in evaluation_matrix()}
    assert matrix['least-privilege-only'].topology == 'least-privilege'
    assert matrix['least-privilege-only'].detector == 'none'
    assert matrix['linear-probe-only'].topology == 'single-agent'
    assert matrix['linear-probe-only'].detector == 'linear'
    assert matrix['gateway-only'].gateway and matrix['gateway-only'].detector == 'none'
    assert not contract_manifest()['measured']
    assert 'not structural' in contract_manifest()['legacy_labels']['LP-only']
    with pytest.raises(ValueError):
        EvalConfig('bad', topology='LP-only')


def test_calibration_handles_tied_negatives_without_test_tuning():
    calibration = calibrate([0.9, 0.8, 0.8, 0.1], [1, 1, 0, 0], max_fpr=0.01)
    assert calibration['threshold'] > 0.8
    assert calibration['tp'] == 1 and calibration['fp'] == 0
    threshold = calibration['threshold']
    heldout = evaluate_frozen([0.7, 0.95, 0.93, 0.2], [1, 1, 0, 0], calibration)
    assert heldout['tpr'] == 0.5 and heldout['fpr'] == 0.5
    assert heldout['threshold'] == threshold == calibration['threshold']


def test_small_negative_sample_does_not_claim_one_percent_evidence():
    tiny = calibrate([0.9, 0.1, 0.2], [1, 0, 0])
    assert not tiny['low_fpr_evidence_sufficient']
    large = calibrate([0.9] * 10 + [0.1] * 299, [1] * 10 + [0] * 299)
    assert large['low_fpr_evidence_sufficient']
    assert large['zero_fp_one_sided_95_upper'] < 0.01


def test_all_one_scores_can_select_reject_all_without_inventing_recall():
    result = calibrate([1.0, 1.0], [1, 0], max_fpr=0)
    assert result['threshold'] == math.nextafter(1.0, math.inf)
    assert result['tpr'] == 0 and result['fpr'] == 0
    with pytest.raises(ValueError):
        calibrate([float('nan'), 0.1], [1, 0])


def test_gate_rejects_missing_mock_or_tied_evidence():
    from smaip.eval.acceptance import assess
    assert assess(contract_manifest())['status'] == 'pending'
    report = {'schema_version': 2, 'kind': 'brd-evidence', 'backend': 'mock',
              'rows': [{'name': c.name, 'utility': 1, 'asr': 0, 'fpr': 0} for c in evaluation_matrix()]}
    result = assess(report)
    assert result['status'] == 'fail'
    assert not result['passed']
    assert 'full_stack_strictly_better' in result['failed']
    assert 'real open-model run identity' in result['pending']


def test_gate_needs_actual_performance_budgets_and_finite_numbers():
    from smaip.eval.acceptance import assess
    report = {'schema_version': 2, 'kind': 'brd-evidence', 'backend': 'hf-local', 'model_id': 'test', 'run_id': 'test-run',
              'rows': [{'name': c.name, 'utility': 1, 'asr': (0 if c.name == 'full-stack' else 0.5), 'fpr': 0} for c in evaluation_matrix()]}
    result = assess(report)
    assert result['status'] == 'pending'
    assert any('performance' in item for item in result['pending'])
    report['rows'][0]['utility'] = float('nan')
    assert assess(report)['status'] == 'fail'
