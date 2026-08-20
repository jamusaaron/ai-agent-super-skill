#!/usr/bin/env python3
"""Runnable extract of the input-drift detector from SKILL.md (section 8.3).

Uses a two-sample Kolmogorov-Smirnov test over query token lengths. Run
directly to compare a reference query set against a drifted set:

    python3 examples/drift_detection.py
"""

import numpy as np
from scipy.stats import ks_2samp


def detect_input_drift(
    reference_inputs: list[str],
    current_inputs: list[str],
    threshold_p: float = 0.05,
) -> dict:
    """Detect distribution shift in agent input queries using
    token length distribution as a proxy metric."""
    ref_lengths = np.array([len(t.split()) for t in reference_inputs])
    cur_lengths = np.array([len(t.split()) for t in current_inputs])

    stat, p_value = ks_2samp(ref_lengths, cur_lengths)

    return {
        "drift_detected": p_value < threshold_p,
        "ks_statistic": float(stat),
        "p_value": float(p_value),
        "ref_mean_tokens": float(ref_lengths.mean()),
        "cur_mean_tokens": float(cur_lengths.mean()),
        "recommendation": (
            "Retrain or re-evaluate agent prompts -- input distribution shifted significantly."
            if p_value < threshold_p else
            "No significant drift detected."
        ),
    }


def _demo() -> None:
    reference = ["short query"] * 20 + ["a slightly longer query here"] * 20
    drifted = [
        "this is a substantially longer user query with many more tokens than before"
    ] * 40

    result = detect_input_drift(reference, drifted)
    print("Drift check (reference vs. drifted):")
    for k, v in result.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    _demo()
