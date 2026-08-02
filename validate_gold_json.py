"""Validate Gold JSON Format and Attribute Distribution.

Analyze WDC-PAVE gold standard for extraction benchmark.
Metrics: Coverage, attribute frequency, category distribution.
"""

import json
import sys
from collections import defaultdict, Counter

print("\n" + "="*80)
print("GOLD JSON ANALYSIS: WDC-PAVE BENCHMARK STANDARD")
print("="*80)

# Load test data
print("\nLoading WDC-PAVE test set...")
with open("wdc_pave_test.json", 'r') as f:
    test_data = json.load(f)

print(f"Test samples: {len(test_data)}")

# Analyze gold JSON
results = defaultdict(lambda: {
    "total": 0,
    "with_attributes": 0,
    "attr_count": [],
    "attributes": Counter(),
    "coverage": 0,
})

print("\nAnalyzing gold JSON...")

for i, sample in enumerate(test_data):
    if i % 50 == 0:
        print(f"  {i}/{len(test_data)}")

    try:
        category = sample.get("category", "Unknown")
        gold_json = sample.get("gold_json", {})

        results[category]["total"] += 1

        # Count non-null attributes
        attrs = {k: v for k, v in gold_json.items() if v is not None}

        if attrs:
            results[category]["with_attributes"] += 1
            results[category]["attr_count"].append(len(attrs))

            for key in attrs.keys():
                results[category]["attributes"][key] += 1

    except Exception as e:
        continue

# Calculate coverage
for category in results:
    total = results[category]["total"]
    with_attrs = results[category]["with_attributes"]
    results[category]["coverage"] = (with_attrs / total * 100) if total > 0 else 0

# Report
print("\n" + "="*80)
print("GOLD JSON BY CATEGORY")
print("="*80)

for category in sorted(results.keys()):
    r = results[category]
    if r["total"] == 0:
        continue

    avg_attrs = (sum(r["attr_count"]) / len(r["attr_count"])) if r["attr_count"] else 0
    top_attrs = r["attributes"].most_common(5)

    print(f"\n{category}")
    print(f"  Samples: {r['total']}")
    print(f"  With attributes: {r['with_attributes']} ({r['coverage']:.1f}%)")
    print(f"  Avg attributes: {avg_attrs:.1f}")
    print(f"  Top attributes:")
    for attr, count in top_attrs:
        pct = (count / r["with_attributes"] * 100) if r["with_attributes"] > 0 else 0
        print(f"    - {attr}: {count} ({pct:.1f}%)")

# Overall
print("\n" + "="*80)
print("OVERALL")
print("="*80)

total_samples = sum(r["total"] for r in results.values())
total_with_attrs = sum(r["with_attributes"] for r in results.values())
avg_attrs_per_sample = sum(sum(r["attr_count"]) for r in results.values()) / max(total_with_attrs, 1)

print(f"\nSamples: {total_samples}")
print(f"With attributes: {total_with_attrs} ({total_with_attrs/total_samples*100:.1f}%)")
print(f"Avg attributes per sample: {avg_attrs_per_sample:.1f}")
print(f"Categories: {len(results)}")

# Save
report = {
    "total_samples": total_samples,
    "with_attributes": total_with_attrs,
    "coverage": total_with_attrs/total_samples if total_samples > 0 else 0,
    "avg_attributes": avg_attrs_per_sample,
    "categories": len(results),
    "by_category": {cat: {
        "total": r["total"],
        "with_attributes": r["with_attributes"],
        "coverage": r["coverage"],
        "avg_attrs": (sum(r["attr_count"]) / len(r["attr_count"])) if r["attr_count"] else 0,
        "top_attrs": dict(r["attributes"].most_common(10))
    } for cat, r in results.items()}
}

with open("gold_json_analysis.json", "w") as f:
    json.dump(report, f, indent=2)

print(f"\nAnalysis saved: gold_json_analysis.json")

print("\n" + "="*80)
