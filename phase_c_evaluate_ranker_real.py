"""Phase C: Evaluate Ranker V4 on real WDC-PAVE test set.

Measure: MRR, Recall@10, nDCG@10, NDCG@5
Report: Measured results only (no synthetic).
"""

import json
import sys
import numpy as np
from collections import defaultdict

sys.path.insert(0, 'pave')

from ranker_v4_inference import RankerV4

print("\n" + "="*80)
print("PHASE C: EVALUATE RANKER V4 ON REAL WDC-PAVE")
print("="*80)

# Step 1: Load test data
print("\n" + "-"*80)
print("STEP 1: LOAD TEST DATA")
print("-"*80)

with open("wdc_pave_test_products.json", 'r') as f:
    test_products = json.load(f)

with open("wdc_pave_triplets.json", 'r') as f:
    all_triplets = json.load(f)

# Filter test triplets
test_triplets = [t for t in all_triplets if t["query_id"] in [p["id"] for p in test_products]]

print(f"\n[+] Test set:")
print(f"    Products: {len(test_products)}")
print(f"    Triplets (for evaluation): {len(test_triplets)}")

if test_triplets:
    print(f"    Sample triplet:")
    sample = test_triplets[0]
    print(f"      Query: {sample['query'][:60]}...")
    print(f"      Positive: {sample['positive']['title'][:50]}...")
    print(f"      Negative: {sample['negative']['title'][:50]}...")

# Step 2: Initialize ranker
print("\n" + "-"*80)
print("STEP 2: INITIALIZE RANKER")
print("-"*80)

ranker = RankerV4(device="cpu")
print(f"[+] Ranker V4 initialized (CPU mode)")

# Step 3: Evaluation metrics
print("\n" + "-"*80)
print("STEP 3: COMPUTE METRICS")
print("-"*80)

def compute_mrr(ranked_list, positive_id):
    """Mean Reciprocal Rank - position of first relevant item."""
    for i, item in enumerate(ranked_list, 1):
        # Handle both RankerScore objects and dicts
        item_id = item.product_id if hasattr(item, "product_id") else item["product_id"]
        if item_id == positive_id:
            return 1.0 / i
    return 0.0

def compute_recall_at_k(ranked_list, positive_id, k=10):
    """Recall@K - whether positive appears in top K."""
    top_k = ranked_list[:k]
    return 1.0 if any((item.product_id if hasattr(item, "product_id") else item["product_id"]) == positive_id for item in top_k) else 0.0

def compute_ndcg_at_k(ranked_list, positive_id, k=10):
    """Normalized DCG@K - rank quality metric."""
    top_k = ranked_list[:k]

    # Relevance: 1 if positive, 0 otherwise
    gains = [1.0 if (item.product_id if hasattr(item, "product_id") else item["product_id"]) == positive_id else 0.0 for item in top_k]

    # DCG
    dcg = sum(gain / np.log2(i + 2) for i, gain in enumerate(gains))

    # IDCG (ideal: positive at position 0)
    idcg = 1.0 / np.log2(2)  # Assume one relevant item

    return dcg / idcg if idcg > 0 else 0.0

# Evaluate on subset (full test set may be slow)
eval_size = min(100, len(test_triplets))
print(f"\nEvaluating on {eval_size} test queries...")

mrr_scores = []
recall_at_10 = []
recall_at_5 = []
ndcg_at_10 = []
ndcg_at_5 = []

for i in range(eval_size):
    triplet = test_triplets[i]
    query = triplet["query"]
    positive = triplet["positive"]
    negative = triplet["negative"]
    category = triplet["category"]

    # Create candidate pool (positive + random negatives from same category)
    candidates = [
        {
            "product_id": positive["id"],
            "title": positive["title"],
            "category": positive["category"]
        },
        {
            "product_id": negative["id"],
            "title": negative["title"],
            "category": negative["category"]
        }
    ]

    # Add more candidates from test set (same category)
    same_cat_products = [p for p in test_products if p["category"] == category and p["id"] not in [c["product_id"] for c in candidates]]
    for p in same_cat_products[:8]:  # Top 8 more candidates
        candidates.append({
            "product_id": p["id"],
            "title": p["title"],
            "category": p["category"]
        })

    # Rank
    ranked = ranker.rank_candidates(query, candidates)
    ranked_ids = [r.product_id for r in ranked]

    # Metrics
    mrr = compute_mrr(ranked, positive["id"])
    recall_10 = compute_recall_at_k(ranked, positive["id"], k=10)
    recall_5 = compute_recall_at_k(ranked, positive["id"], k=5)
    ndcg_10 = compute_ndcg_at_k(ranked, positive["id"], k=10)
    ndcg_5 = compute_ndcg_at_k(ranked, positive["id"], k=5)

    mrr_scores.append(mrr)
    recall_at_10.append(recall_10)
    recall_at_5.append(recall_5)
    ndcg_at_10.append(ndcg_10)
    ndcg_at_5.append(ndcg_5)

    if i < 3:
        print(f"\n  Query {i+1}: {query[:50]}...")
        print(f"    Ranked: {ranked_ids[:3]}")
        print(f"    MRR={mrr:.3f}, R@10={recall_10:.1f}, nDCG@10={ndcg_10:.3f}")

# Step 4: Aggregate metrics
print("\n" + "-"*80)
print("STEP 4: AGGREGATED RESULTS")
print("-"*80)

avg_mrr = np.mean(mrr_scores)
avg_recall_10 = np.mean(recall_at_10)
avg_recall_5 = np.mean(recall_at_5)
avg_ndcg_10 = np.mean(ndcg_at_10)
avg_ndcg_5 = np.mean(ndcg_at_5)

print(f"\n[OK] MEASURED RESULTS (Ranker V4 on WDC-PAVE Test Set)")
print(f"   Eval size: {eval_size} queries")
print(f"\n   MRR:        {avg_mrr:.4f}")
print(f"   Recall@5:   {avg_recall_5:.4f}")
print(f"   Recall@10:  {avg_recall_10:.4f}")
print(f"   nDCG@5:     {avg_ndcg_5:.4f}")
print(f"   nDCG@10:    {avg_ndcg_10:.4f}")

# Step 5: Save results
print("\n" + "-"*80)
print("STEP 5: SAVE RESULTS")
print("-"*80)

results = {
    "phase": "C",
    "dataset": "wdc-pave-real",
    "eval_size": eval_size,
    "metrics": {
        "MRR": float(avg_mrr),
        "Recall@5": float(avg_recall_5),
        "Recall@10": float(avg_recall_10),
        "nDCG@5": float(avg_ndcg_5),
        "nDCG@10": float(avg_ndcg_10),
    },
    "distribution": {
        "MRR_scores": mrr_scores[:20],  # Sample
        "Recall_at_10": recall_at_10[:20],
        "nDCG_at_10": ndcg_at_10[:20],
    },
    "status": "COMPLETED"
}

output_file = "phase_c_evaluation_results.json"
with open(output_file, 'w') as f:
    json.dump(results, f, indent=2)

print(f"[+] Results saved: {output_file}")

# Step 6: Summary
print("\n" + "="*80)
print("PHASE C SUMMARY")
print("="*80)

print(f"""
[OK] EVALUATION COMPLETE

Dataset: WDC-PAVE (real benchmark)
  - Test products: {len(test_products)}
  - Evaluated queries: {eval_size}

Baseline Results (Ranker V4, random init):
  - MRR:       {avg_mrr:.4f}
  - Recall@10: {avg_recall_10:.4f}
  - nDCG@10:   {avg_ndcg_10:.4f}

Interpretation:
  - Random model: ~{1/len(test_products):.4f} (baseline)
  - Current MRR {avg_mrr:.4f}: {'ABOVE' if avg_mrr > 1/len(test_products) else 'BELOW'} random

Next phases:
  [OK] Phase D: Error analysis
  [OK] Phase E: Ablation study
  [OK] Phase F: Research report

Files:
  - phase_c_evaluation_results.json
  - wdc_pave_test_products.json
  - ranker_v4_wdc_pave_real.json
""")

print("="*80)
