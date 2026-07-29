"""Phase D: Error Analysis on real WDC-PAVE test set.

Categorize failures by error type.
Identify patterns in MRR=0.2562 performance.
"""

import json
import sys
import numpy as np
from collections import defaultdict

sys.path.insert(0, 'pave')

from ranker_v4_inference import RankerV4

print("\n" + "="*80)
print("PHASE D: ERROR ANALYSIS")
print("="*80)

# Step 1: Load data
print("\n" + "-"*80)
print("STEP 1: LOAD TEST DATA")
print("-"*80)

with open("wdc_pave_test_products.json", 'r') as f:
    test_products = json.load(f)

with open("wdc_pave_triplets.json", 'r') as f:
    all_triplets = json.load(f)

test_triplets = [t for t in all_triplets if t["query_id"] in [p["id"] for p in test_products]]

print(f"\n[+] Test data loaded:")
print(f"    Products: {len(test_products)}")
print(f"    Triplets: {len(test_triplets)}")

# Step 2: Error categories
print("\n" + "-"*80)
print("STEP 2: ANALYZE FAILURES")
print("-"*80)

ranker = RankerV4(device="cpu")

errors = {
    "ranking_error": [],      # Positive not at top 1, but in results
    "candidate_miss": [],     # Positive not in candidate pool at all
    "partial_match": [],      # Similar product ranked higher
    "brand_confusion": [],    # Different brand same model
    "model_confusion": [],    # Similar model numbers
    "capacity_confusion": [], # Similar specs
}

correct = []
eval_count = min(50, len(test_triplets))  # 50 for detailed analysis

print(f"\nAnalyzing {eval_count} test cases...\n")

for i in range(eval_count):
    triplet = test_triplets[i]
    query = triplet["query"]
    positive = triplet["positive"]
    negative = triplet["negative"]
    category = triplet["category"]

    # Build candidate pool
    candidates = [
        {
            "product_id": positive["id"],
            "title": positive["title"],
            "category": positive["category"],
            "attributes": positive["attributes"]
        },
        {
            "product_id": negative["id"],
            "title": negative["title"],
            "category": negative["category"],
            "attributes": negative["attributes"]
        }
    ]

    # Add more candidates
    same_cat_products = [p for p in test_products if p["category"] == category and p["id"] not in [c["product_id"] for c in candidates]]
    for p in same_cat_products[:8]:
        candidates.append({
            "product_id": p["id"],
            "title": p["title"],
            "category": p["category"],
            "attributes": p.get("attributes", {})
        })

    # Rank
    ranked = ranker.rank_candidates(query, candidates)

    # Find positive in ranking
    pos_rank = None
    for rank, score in enumerate(ranked, 1):
        if score.product_id == positive["id"]:
            pos_rank = rank
            break

    # Categorize
    error_found = False

    if pos_rank is None:
        # Candidate miss - shouldn't happen with our pool
        errors["candidate_miss"].append({
            "query": query[:80],
            "expected": positive["title"][:60],
            "pool_size": len(candidates),
            "rank_note": "Not in pool"
        })
        error_found = True

    elif pos_rank > 1:
        # Ranking error - positive not at top
        top_result = ranked[0]
        top_product = next((p for p in candidates if p["product_id"] == top_result.product_id), None)

        # Classify error type
        pos_attrs = set(positive.get("attributes", {}).keys())
        top_attrs = set(top_product.get("attributes", {}).keys()) if top_product else set()
        neg_attrs = set(negative.get("attributes", {}).keys())

        # Check for specific confusion types
        pos_title_lower = positive["title"].lower()
        top_title_lower = top_result.candidate_title.lower() if top_result else ""

        if "brand" in top_attrs and "brand" in pos_attrs:
            if positive["attributes"].get("brand") != top_product["attributes"].get("brand"):
                errors["brand_confusion"].append({
                    "query": query[:60],
                    "expected": f"{positive['attributes'].get('Brand', 'N/A')} - {positive['title'][:50]}",
                    "predicted": f"{top_product['attributes'].get('Brand', 'N/A')} - {top_result.candidate_title[:50]}",
                    "rank": pos_rank
                })
                error_found = True

        if "model" in positive["attributes"] and "model" in (top_product["attributes"] if top_product else {}):
            if positive["attributes"].get("model") != top_product.get("attributes", {}).get("model"):
                if "model" in pos_title_lower and "model" in top_title_lower:
                    errors["model_confusion"].append({
                        "query": query[:60],
                        "expected_model": positive["attributes"].get("Model", "N/A"),
                        "predicted_model": top_product.get("attributes", {}).get("Model", "N/A"),
                        "rank": pos_rank
                    })
                    error_found = True

        if "capacity" in positive["attributes"]:
            if top_product and "capacity" in top_product.get("attributes", {}):
                errors["capacity_confusion"].append({
                    "query": query[:60],
                    "expected_capacity": positive["attributes"].get("Capacity", "N/A"),
                    "predicted_capacity": top_product.get("attributes", {}).get("Capacity", "N/A"),
                    "rank": pos_rank
                })
                error_found = True

        if not error_found:
            errors["ranking_error"].append({
                "query": query[:60],
                "expected": positive["title"][:50],
                "predicted": top_result.candidate_title[:50],
                "rank": pos_rank
            })

    else:
        correct.append({
            "query": query[:60],
            "title": positive["title"][:50]
        })

# Step 3: Summary
print("\n" + "-"*80)
print("STEP 3: ERROR SUMMARY")
print("-"*80)

total_cases = eval_count
accuracy = len(correct) / total_cases if total_cases > 0 else 0

print(f"\n[OK] CORRECT: {len(correct)}/{total_cases} ({100*accuracy:.1f}%)")

for error_type, cases in errors.items():
    if cases:
        print(f" {error_type.upper()}: {len(cases)} cases")

print(f"\nDetailed breakdown:")

# Ranking errors
if errors["ranking_error"]:
    print(f"\n[RANKING ERROR] ({len(errors['ranking_error'])} cases)")
    print("  Root cause: Positive found but not at rank 1")
    print("  Example (first 3):")
    for case in errors["ranking_error"][:3]:
        print(f"    Query: {case['query']}")
        print(f"      Expected: {case['expected']}")
        print(f"      Got (rank {case['rank']}): {case['predicted']}")
        print()

# Brand confusion
if errors["brand_confusion"]:
    print(f"\n[BRAND CONFUSION] ({len(errors['brand_confusion'])} cases)")
    print("  Root cause: Different brand with similar model ranked higher")
    print("  Example (first 3):")
    for case in errors["brand_confusion"][:3]:
        print(f"    Query: {case['query']}")
        print(f"      Expected: {case['expected']}")
        print(f"      Got (rank {case['rank']}): {case['predicted']}")
        print()

# Model confusion
if errors["model_confusion"]:
    print(f"\n[MODEL CONFUSION] ({len(errors['model_confusion'])} cases)")
    print("  Root cause: Similar model numbers, wrong rank")
    print("  Example (first 2):")
    for case in errors["model_confusion"][:2]:
        print(f"    Query: {case['query']}")
        print(f"      Expected model: {case['expected_model']}")
        print(f"      Got model (rank {case['rank']}): {case['predicted_model']}")
        print()

# Capacity confusion
if errors["capacity_confusion"]:
    print(f"\n[CAPACITY CONFUSION] ({len(errors['capacity_confusion'])} cases)")
    print("  Root cause: Same product type, different capacity")
    print()

# Step 4: Save analysis
print("-"*80)
print("STEP 4: SAVE ANALYSIS")
print("-"*80)

analysis = {
    "phase": "D",
    "dataset": "wdc-pave-real",
    "eval_cases": eval_count,
    "accuracy": float(accuracy),
    "correct_count": len(correct),
    "error_breakdown": {
        k: len(v) for k, v in errors.items()
    },
    "error_details": {
        k: v[:5] for k, v in errors.items() if v  # First 5 examples
    },
    "interpretation": {
        "ranking_error": "Positive exists but not ranked first -> Ranker/embeddings issue",
        "brand_confusion": "Different brands with similar specs -> Needs better brand weighting",
        "model_confusion": "Similar model numbers -> Needs exact model matching",
        "capacity_confusion": "Same type, different capacity -> Feature generation improvement",
        "candidate_miss": "Positive not in candidate pool -> Pool generation issue"
    }
}

output_file = "phase_d_error_analysis.json"
with open(output_file, 'w') as f:
    json.dump(analysis, f, indent=2)

print(f"[+] Analysis saved: {output_file}")

# Step 5: Summary
print("\n" + "="*80)
print("PHASE D SUMMARY")
print("="*80)

print(f"""
ERROR ANALYSIS ON {eval_count} TEST CASES

Accuracy (rank 1): {100*accuracy:.1f}%

Top Error Categories:
  - Ranking error: {len(errors['ranking_error'])} (positive exists but wrong rank)
  - Brand confusion: {len(errors['brand_confusion'])} (brand mismatch)
  - Model confusion: {len(errors['model_confusion'])} (model number issues)
  - Capacity confusion: {len(errors['capacity_confusion'])} (spec differences)

Root Causes:
  1. Embeddings too generic (hash-based, not transformer)
  2. Attributes not weighted properly
  3. Product similarity calculated on title only
  4. No brand/model extraction from query

Recommendations for improvement:
  [OK] Use better embeddings (e.g., ModernBERT)
  [OK] Weight attributes by category (brand=high for some cats)
  [OK] Extract structured attributes from query
  [OK] Implement brand-aware ranking

Files:
  - phase_d_error_analysis.json (detailed breakdown)
  - phase_c_evaluation_results.json (metrics)
""")

print("="*80)
