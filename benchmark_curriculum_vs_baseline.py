"""Benchmark: Curriculum Learning vs Baseline Ranker V4.

Compare performance:
- Baseline: train_ranker_v4_gpu.py output
- Curriculum: train_with_curriculum.py output

Metrics:
- MRR (Mean Reciprocal Rank)
- Recall@10
- nDCG@10
- Training loss progression
"""

import json
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, 'pave')

print("\n" + "="*80)
print("CURRICULUM LEARNING BENCHMARK COMPARISON")
print("="*80)

# Load training histories
print("\nLoading training histories...")

try:
    with open("ranker_v4_training_results.json", 'r') as f:
        baseline_history = json.load(f)
    print(f"[+] Baseline: {len(baseline_history)} epochs")
except FileNotFoundError:
    print("[-] Baseline history not found: ranker_v4_training_results.json")
    baseline_history = None

try:
    with open("ranker_v4_curriculum_history.json", 'r') as f:
        curriculum_history = json.load(f)
    print(f"[+] Curriculum: {len(curriculum_history)} epochs")
except FileNotFoundError:
    print("[-] Curriculum history not found: ranker_v4_curriculum_history.json")
    curriculum_history = None

# Analysis
print("\n" + "-"*80)
print("TRAINING LOSS COMPARISON")
print("-"*80)

if baseline_history:
    baseline_losses = [h.get("loss", 0) for h in baseline_history]
    baseline_first = baseline_losses[0]
    baseline_last = baseline_losses[-1]
    baseline_improvement = ((baseline_first - baseline_last) / baseline_first) * 100

    print(f"\nBaseline (Standard Triplet Loss):")
    print(f"  First epoch loss: {baseline_first:.6f}")
    print(f"  Last epoch loss: {baseline_last:.6f}")
    print(f"  Improvement: {baseline_improvement:.1f}%")

if curriculum_history:
    curriculum_losses = [h.get("loss", 0) for h in curriculum_history]
    curriculum_first = curriculum_losses[0]
    curriculum_last = curriculum_losses[-1]
    curriculum_improvement = ((curriculum_first - curriculum_last) / curriculum_first) * 100

    print(f"\nCurriculum Learning:")
    print(f"  First epoch loss: {curriculum_first:.6f}")
    print(f"  Last epoch loss: {curriculum_last:.6f}")
    print(f"  Improvement: {curriculum_improvement:.1f}%")

    # Stage breakdown
    print(f"\n  Stage Breakdown:")
    for h in curriculum_history:
        epoch = h["epoch"]
        loss = h["loss"]
        difficulty = h.get("curriculum_difficulty", "")
        weight = h.get("curriculum_weight", 1.0)
        print(f"    Epoch {epoch:2d}: loss={loss:.6f} | {difficulty:6s} (weight={weight:.1f}x)")

# Comparison
print("\n" + "-"*80)
print("COMPARISON")
print("-"*80)

if baseline_history and curriculum_history:
    baseline_final = baseline_losses[-1]
    curriculum_final = curriculum_losses[-1]
    improvement = ((baseline_final - curriculum_final) / baseline_final) * 100

    print(f"\nFinal Loss:")
    print(f"  Baseline: {baseline_final:.6f}")
    print(f"  Curriculum: {curriculum_final:.6f}")

    if improvement > 0:
        print(f"  Curriculum Better: {improvement:.1f}%")
    else:
        print(f"  Baseline Better: {-improvement:.1f}%")

    # Stability (variance)
    import numpy as np
    baseline_var = np.var(baseline_losses)
    curriculum_var = np.var(curriculum_losses)

    print(f"\nTraining Stability (lower is better):")
    print(f"  Baseline variance: {baseline_var:.6f}")
    print(f"  Curriculum variance: {curriculum_var:.6f}")

    if curriculum_var < baseline_var:
        print(f"  Curriculum more stable: {((baseline_var - curriculum_var) / baseline_var)*100:.1f}%")

# Prediction: Test set evaluation needed
print("\n" + "-"*80)
print("NEXT STEP: TEST SET EVALUATION")
print("-"*80)

print("""
Models trained. Now need to evaluate on test set:

1. Baseline Ranker V4:
   python phase_c_evaluate_ranker_real.py \\
     --checkpoint ranker_v4_final.pt \\
     --output baseline_metrics.json

2. Curriculum Ranker V4:
   python phase_c_evaluate_ranker_real.py \\
     --checkpoint ranker_v4_curriculum_final.pt \\
     --output curriculum_metrics.json

3. Compare metrics:
   Metric          | Baseline | Curriculum | Winner
   MRR             |   ?      |     ?      |   ?
   Recall@10       |   ?      |     ?      |   ?
   nDCG@10         |   ?      |     ?      |   ?
   Training Time   |   ?      |     ?      |   ?

Expected: Curriculum should improve MRR by 5-15% on test set.
""")

print("\n" + "="*80)
print("BENCHMARK COMPLETE (Training Phase)")
print("="*80)
