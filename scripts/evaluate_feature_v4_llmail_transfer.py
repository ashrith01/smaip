#!/usr/bin/env python3
"""Observed LLMail transfer diagnostic using a NVIDIA-only score cutoff.

This never changes the saved model or its serving-disabled policy. Both source
datasets have already been observed, so these counts are not a final test.
"""

import argparse
import json

import train_feature_v4_solo_probe as solo


OUTPUT = solo.ROOT / '.local-data/feature-v4-llmail-cutoff-01'


def calculate():
    verified = solo.verify()
    summary = json.loads((solo.OUTPUT / 'summary.json').read_text())
    model = json.loads((solo.OUTPUT / 'model.json').read_text())
    solo.require(model['threshold'] is None and model['serving_enabled'] is False,
                 'source probe was promoted')
    rows = solo.read_jsonl(solo.OUTPUT / 'predictions.jsonl')
    nvidia = [r for r in rows if r['score_role'] == 'training-in-sample']
    llmail = [r for r in rows if r['score_role'] == 'observed-source-transfer']
    solo.require(len(nvidia) == 680 and len(llmail) == 288 and
                 all(r['source_origin'] == model['training_source'] for r in nvidia) and
                 all(r['source_origin'] == model['held_source'] for r in llmail),
                 'saved source membership differs')
    benign_max = max(r['score'] for r in nvidia if r['source_label'] == 0)
    attack_min = min(r['score'] for r in nvidia if r['source_label'] == 1)
    solo.require(benign_max < attack_min, 'NVIDIA training scores do not separate')
    cutoff = (benign_max + attack_min) / 2.0
    counts = {'true_positive': 0, 'false_negative': 0,
              'false_positive': 0, 'true_negative': 0}
    missed = []
    for row in llmail:
        predicted = int(row['score'] >= cutoff)
        key = ('true_positive' if row['source_label'] else 'false_positive') if predicted else (
            'false_negative' if row['source_label'] else 'true_negative')
        counts[key] += 1
        if key == 'false_negative':
            missed.append(row['candidate_id'])
    solo.require(sum(counts.values()) == 288 and
                 counts['true_positive'] + counts['false_negative'] == 128 and
                 counts['true_negative'] + counts['false_positive'] == 160,
                 'LLMail confusion matrix differs')
    return {
        'kind': 'feature-v4-llmail-observed-cutoff-diagnostic-01',
        'model_sha256': summary['model_sha256'],
        'predictions_sha256': summary['predictions_sha256'],
        'verified_predictions': verified['verified_predictions'],
        'cutoff_rule': 'midpoint of maximum benign and minimum attack scores on NVIDIA training rows only',
        'nvidia_training_benign_max': benign_max,
        'nvidia_training_attack_min': attack_min,
        'diagnostic_cutoff': cutoff,
        'llmail_rows': 288, 'llmail_attacks': 128, 'llmail_benign': 160,
        'llmail_source_label_auroc': summary['llmail_observed_source_transfer_auroc'],
        'confusion_matrix': counts,
        'attack_recall': counts['true_positive'] / 128,
        'benign_false_positive_rate': counts['false_positive'] / 160,
        'missed_attack_ids': missed,
        'serving_enabled': False,
        'model_threshold_unchanged': True,
        'independent_final_test': False,
        'limitations': [
            'The feature and LLMail source were observed before this cutoff diagnostic.',
            'The cutoff rule was not prospectively frozen before any LLMail analysis.',
            'LLMail source labels are not accepted human truth and the attack rows share lineage.',
            'No real agent action or attack success was measured.',
        ],
    }


def main(verify_only):
    result = calculate()
    raw = solo.json_bytes(result)
    if verify_only:
        solo.require((OUTPUT / 'summary.json').read_bytes() == raw,
                     'saved LLMail transfer diagnostic does not reproduce')
        print(json.dumps({'verified': True, 'summary_sha256': solo.sha(raw)}, indent=2))
    else:
        solo.require(not OUTPUT.exists(), 'preserve LLMail diagnostic 01; version any rerun')
        OUTPUT.mkdir(mode=0o700, parents=True)
        solo.write_private(OUTPUT / 'summary.json', raw)
        print(json.dumps(result, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify-only', action='store_true')
    main(parser.parse_args().verify_only)
