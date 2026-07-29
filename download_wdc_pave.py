"""Download WDC-PAVE from HuggingFace and convert to training format."""

import json
from pathlib import Path
from huggingface_hub import hf_hub_download

print("Downloading WDC-PAVE dataset from HuggingFace...")

# Download files
train_path = hf_hub_download(
    "siavashsaki/wdc-pave-ave",
    filename="train.jsonl",
    repo_type="dataset"
)
val_path = hf_hub_download(
    "siavashsaki/wdc-pave-ave",
    filename="val.jsonl",
    repo_type="dataset"
)
test_path = hf_hub_download(
    "siavashsaki/wdc-pave-ave",
    filename="test.jsonl",
    repo_type="dataset"
)
schemas_path = hf_hub_download(
    "siavashsaki/wdc-pave-ave",
    filename="category_schemas.json",
    repo_type="dataset"
)

# Convert JSONL to JSON
def jsonl_to_json(jsonl_file):
    data = []
    with open(jsonl_file, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                data.append(json.loads(line))
    return data

print("Converting JSONL to JSON...")
train_data = jsonl_to_json(train_path)
val_data = jsonl_to_json(val_path)
test_data = jsonl_to_json(test_path)

# Save as JSON
print("Saving datasets...")
with open("wdc_pave_train.json", 'w', encoding='utf-8') as f:
    json.dump(train_data, f, indent=2)

with open("wdc_pave_val.json", 'w', encoding='utf-8') as f:
    json.dump(val_data, f, indent=2)

with open("wdc_pave_test.json", 'w', encoding='utf-8') as f:
    json.dump(test_data, f, indent=2)

# Copy schemas
import shutil
shutil.copy(schemas_path, "category_schemas.json")

print(f"\nComplete!")
print(f"  Train: {len(train_data)} samples -> wdc_pave_train.json")
print(f"  Val: {len(val_data)} samples -> wdc_pave_val.json")
print(f"  Test: {len(test_data)} samples -> wdc_pave_test.json")
print(f"  Schemas: category_schemas.json")
