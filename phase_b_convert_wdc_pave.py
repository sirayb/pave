"""Phase B: Convert WDC-PAVE to pipeline format + generate triplets for Ranker V4.

Real benchmark data. No mock data.
"""

import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, 'pave')

print("\n" + "="*80)
print("PHASE B: WDC-PAVE -> PIPELINE FORMAT")
print("="*80)

# Step 1: Load WDC-PAVE
print("\n" + "-"*80)
print("STEP 1: LOAD WDC-PAVE")
print("-"*80)

with open("wdc_pave_train.json", 'r') as f:
    train_data = json.load(f)

with open("wdc_pave_val.json", 'r') as f:
    val_data = json.load(f)

with open("wdc_pave_test.json", 'r') as f:
    test_data = json.load(f)

print(f"\n[+] Loaded:")
print(f"    Train: {len(train_data)}")
print(f"    Val: {len(val_data)}")
print(f"    Test: {len(test_data)}")
print(f"    Total: {len(train_data) + len(val_data) + len(test_data)}")

# Step 2: Load category schemas
print("\n" + "-"*80)
print("STEP 2: LOAD CATEGORY SCHEMAS")
print("-"*80)

with open(".hf_cache/datasets--siavashsaki--wdc-pave-ave/snapshots/2ba97f3d959e67a21953e64192fffcb63ce57512/category_schemas.json", 'r') as f:
    schemas = json.load(f)

print(f"\n[+] Loaded {len(schemas)} category schemas:")
for cat, attrs in schemas.items():
    print(f"    [{cat}] {len(attrs)} attributes")
    print(f"      {', '.join(attrs[:5])}" + ("..." if len(attrs) > 5 else ""))

# Step 3: Convert to product format
print("\n" + "-"*80)
print("STEP 3: CONVERT TO PRODUCT FORMAT")
print("-"*80)

def convert_record(record, schema):
    """Convert WDC-PAVE record to product format."""
    product = {
        "id": str(record["id"]),
        "title": record["input_title"],
        "description": record.get("input_description", ""),
        "category": record["category"],
        "attributes": {},
        "gold_annotations": {}
    }

    # Extract ground truth values
    gold = record.get("gold_json", {})
    for attr_name, attr_value in gold.items():
        if attr_value is not None:
            product["attributes"][attr_name] = str(attr_value)
            product["gold_annotations"][attr_name] = str(attr_value)

    return product

# Convert all splits
products_by_split = {}

for split_name, split_data in [("train", train_data), ("val", val_data), ("test", test_data)]:
    print(f"\nConverting {split_name}...")

    products = []
    for record in split_data:
        cat = record["category"]
        schema = schemas.get(cat, [])
        product = convert_record(record, schema)
        products.append(product)

    products_by_split[split_name] = products
    print(f"[+] {split_name}: {len(products)} products")

    if products:
        sample = products[0]
        print(f"    Sample product:")
        print(f"      ID: {sample['id']}")
        print(f"      Title: {sample['title'][:60]}")
        print(f"      Category: {sample['category']}")
        print(f"      Attributes: {list(sample['attributes'].keys())}")

# Step 4: Save converted data
print("\n" + "-"*80)
print("STEP 4: SAVE CONVERTED DATA")
print("-"*80)

for split_name, products in products_by_split.items():
    output_file = f"wdc_pave_{split_name}_products.json"
    with open(output_file, 'w') as f:
        json.dump(products, f, indent=2)
    print(f"[+] {output_file}: {len(products)} products")

# Step 5: Generate training triplets for Ranker V4
print("\n" + "-"*80)
print("STEP 5: GENERATE RANKER V4 TRIPLETS")
print("-"*80)

print("\nGenerating triplets from gold annotations...")

triplets = []

for split_name, products in products_by_split.items():
    print(f"\n[->] {split_name.upper()}")

    # Group by category
    by_cat = defaultdict(list)
    for prod in products:
        if prod["gold_annotations"]:  # Only products with annotations
            by_cat[prod["category"]].append(prod)

    for cat, cat_products in by_cat.items():
        if len(cat_products) < 2:
            continue

        # For each product with annotations, create triplets
        for i, anchor in enumerate(cat_products):
            query = f"{anchor['title']} {anchor.get('description', '')}"

            # Positive: same product
            positive = {
                "id": anchor["id"],
                "title": anchor["title"],
                "category": anchor["category"],
                "attributes": anchor["gold_annotations"]
            }

            # Negatives: other products in same category (simplest approach)
            for j, neg in enumerate(cat_products):
                if i != j and len(cat_products) > 1:
                    negative = {
                        "id": neg["id"],
                        "title": neg["title"],
                        "category": neg["category"],
                        "attributes": neg.get("gold_annotations", {})
                    }

                    triplet = {
                        "query": query,
                        "query_id": anchor["id"],
                        "positive": positive,
                        "negative": negative,
                        "category": cat
                    }

                    triplets.append(triplet)

    print(f"    Generated {len(triplets)} triplets for {split_name}")

# Save triplets
triplet_file = "wdc_pave_triplets.json"
with open(triplet_file, 'w') as f:
    json.dump(triplets, f, indent=2)

print(f"\n[+] Total triplets: {len(triplets)}")
print(f"[+] Saved: {triplet_file}")

# Step 6: Summary
print("\n" + "="*80)
print("PHASE B SUMMARY")
print("="*80)

print(f"""
[OK] CONVERSION COMPLETE

Datasets:
  - Train: {len(products_by_split['train'])} products
  - Val: {len(products_by_split['val'])} products
  - Test: {len(products_by_split['test'])} products

Training data:
  - Triplets: {len(triplets)}
  - Ready for Ranker V4

Files generated:
  - wdc_pave_train_products.json
  - wdc_pave_val_products.json
  - wdc_pave_test_products.json
  - wdc_pave_triplets.json

Next: python train_ranker_v4_gpu.py
""")

print("="*80)
