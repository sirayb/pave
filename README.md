# PAVE: Product Attribute Value Extraction & Ranking

**What it does**: Extracts structured attributes (category, color, brand, capacity, etc.) from raw product titles and descriptions, then ranks products by relevance to search queries.

**Status**: ✅ Production ready with 5 categories, 37 attributes, trained on 1,420 real e-commerce products

---

## 🎯 What Is PAVE?

PAVE solves two e-commerce problems:

### 1. **Attribute Extraction** (What properties does this product have?)
- Input: Raw product title like `"iPhone 15 256GB Black"`
- Output: Structured attributes like:
  ```json
  {
    "category": "computer",
    "Manufacturer": "Apple",
    "Capacity": "256GB",
    "Color": "Black",
    "confidence": 0.85
  }
  ```

### 2. **Product Ranking** (Which product best matches this search?)
- Input: Search query `"Apple phone 256GB"` + candidate products
- Output: Ranked products with relevance scores
  ```json
  [
    {"product_id": "P001", "title": "iPhone 15 256GB", "relevance": 0.89},
    {"product_id": "P002", "title": "iPhone 14 128GB", "relevance": 0.72},
    {"product_id": "P003", "title": "Samsung Galaxy S24", "relevance": 0.45}
  ]
  ```

---

## 💼 Where Can You Use It?

### E-Commerce Platforms
- **Seller catalog import**: Auto-extract attributes when sellers upload products
- **Product search**: Improve relevance of user queries
- **Data cleaning**: Normalize messy product data

### Use Cases
- Retail marketplaces (Amazon, eBay-like)
- Bulk product import pipelines
- Search relevance ranking
- Catalog standardization

### Supported Categories
- 🖥️ **Computers**: Laptops, phones, tablets, components
- 💎 **Jewelry**: Rings, necklaces, bracelets, gemstones
- 🏢 **Office**: Desks, chairs, printers, paper
- 🏡 **Home & Garden**: Furniture, tools, decor
- 🛒 **Grocery**: Coffee, tea, snacks, beverages

---

## 🚀 Quick Start (2 minutes)

### Option A: Web Dashboard (Easiest)

```bash
# 1. Install
pip install -r requirements.txt

# 2. Start API
python -m uvicorn pave.api:app --host 127.0.0.1 --port 8000

# 3. Open browser
# Visit: http://localhost:8000
```

Then type in search bar: `"iPhone 15 256GB Black"` → See extracted attributes!

### Option B: Python API (In Your App)

```python
import requests

# Extract attributes from product
response = requests.post('http://localhost:8000/extract', json={
    'title': 'iPhone 15 256GB Black',
    'description': 'Latest Apple smartphone'
})

attributes = response.json()
# {
#   'category': 'computer',
#   'attributes': {
#     'Manufacturer': {'value': 'Apple', 'confidence': 0.85},
#     'Color': {'value': 'Black', 'confidence': 0.90},
#     'Capacity': {'value': '256GB', 'confidence': 1.0}
#   }
# }
```

### Option C: Docker (Production)

```bash
docker-compose up -d
# API runs on http://localhost:8000
```

---

## 📡 API Endpoints

### 1. **Extract Attributes**
Extract all attributes from product title/description.

```bash
curl -X POST http://localhost:8000/extract \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Gold Diamond Ring 18K",
    "description": "Beautiful wedding ring with diamond"
  }'
```

**Response**:
```json
{
  "category": "jewelry",
  "category_confidence": 1.0,
  "attributes": {
    "Metal": {"value": "Gold", "confidence": 0.95},
    "MetalPurity": {"value": "18K", "confidence": 0.90},
    "Gemstone": {"value": "Diamond", "confidence": 0.85}
  },
  "suggestions": {
    "Metal": ["Gold", "Silver", "Platinum"],
    "Color": ["White", "Yellow", "Rose"]
  },
  "mandatory_missing": []
}
```

**Typo Correction**: Handles misspellings automatically
- Input: `"Gld Dimond Ring 18K"` (typos: Gld, Dimond)
- Suggests: `Gold`, `Diamond` from valid values
- Fuzzy matching with 70% similarity threshold

### 2. **Rank Products** (Search)
Rank candidate products by relevance to query.

```bash
curl -X POST http://localhost:8000/rank \
  -H "Content-Type: application/json" \
  -d '{
    "query": "dell laptop 512gb ssd",
    "candidates": [
      {"id": "P001", "title": "Dell XPS 13", "description": "High-end laptop"},
      {"id": "P002", "title": "HP Pavilion", "description": "Mid-range laptop"}
    ],
    "top_k": 5
  }'
```

**Response**:
```json
{
  "query": "dell laptop 512gb ssd",
  "category": "computer",
  "results": [
    {"rank": 1, "product_id": "P001", "title": "Dell XPS 13", "relevance_score": 0.89},
    {"rank": 2, "product_id": "P002", "title": "HP Pavilion", "relevance_score": 0.65}
  ]
}
```

### 3. **Typo & Fuzzy Matching**
System automatically corrects misspellings and suggests alternatives.

**Example: Typo in Color**
```bash
curl -X POST http://localhost:8000/extract \
  -H "Content-Type: application/json" \
  -d '{"title": "Apple phone slvr blck"}'
```

**Response**: Recognizes `slvr` → Silver, `blck` → Black
```json
{
  "category": "computer",
  "attributes": {
    "Color": {"value": "Silver", "confidence": 0.7, "explanation": "Partial/typo match"}
  },
  "suggestions": {
    "Color": ["Silver", "Black"]
  }
}
```

**How it works**:
- SequenceMatcher fuzzy matching (70% similarity)
- Returns top suggestions for user review
- Works across all 5 categories

### 4. **Model Info**
Get system configuration and performance metrics.

```bash
curl http://localhost:8000/model-info
```

---

## 📊 Performance

Trained on **1,420 real e-commerce products** from WDC-PAVE benchmark:

| Category | Extraction Accuracy | Attributes Extracted |
|----------|-------------------|----------------------|
| Jewelry | 100% | 3-5 (Metal, Color, Size, etc.) |
| Computer | 40%+ | 4-10 (Brand, RAM, CPU, Storage, etc.) |
| Office | 100% | 1-5 (Type, Material, Size, etc.) |
| Home & Garden | 80%+ | 1-3 (Type, Color, Material, etc.) |
| Grocery | 100% | 5-8 (Weight, Organic, Certifications, etc.) |

**Ranking Performance** (Test set, 100 queries):
- MRR: 0.1321 (37x better than random)
- Recall@10: 1.00 (correct items always in top-10)
- nDCG@10: 0.3225

---

## ✅ Testing & Metrics

**Test Suite**: `test_extraction_features.py`

```bash
python test_extraction_features.py
```

**Results**:
| Metric | Score |
|--------|-------|
| Extraction Pass Rate | 100% (11/11 tests) |
| Category Recognition | 100% (5/5 categories) |
| Typo Matching Rate | 100% (3/3 typos) |
| Avg Attributes/Product | 3.73 |
| **Overall Score** | **100%** |

**Coverage by Category**:
- Computer: 4.3 attributes/test (13 total)
- Jewelry: 4.5 attributes/test (9 total)
- Office: 4.0 attributes/test (8 total)
- Home & Garden: 2.0 attributes/test (4 total)
- Grocery: 3.5 attributes/test (7 total)

---

## 🏗️ How It Works (6 Stages)

```
1. QUERY INPUT
   "iPhone 15 256GB Black"
   ↓
2. CATEGORY CLASSIFIER (keyword matching)
   → "computer" (40% confidence)
   ↓
3. EXTRACTION (Expert system per category)
   → Manufacturer: Apple
   → Capacity: 256GB
   → Color: Black
   ↓
4. ATTRIBUTE VALIDATION
   → Confidence scores per attribute
   ↓
5. PRODUCT RANKING (if search query)
   → Score candidates vs query
   ↓
6. FINAL OUTPUT
   → Ranked products with scores
```

### Component Breakdown

| Component | Purpose | Example |
|-----------|---------|---------|
| **Category Classifier** | Identify product type | "laptop" → "computer" |
| **Feature Generator** | Extract 10 features from query+product | Title overlap, semantic similarity, etc. |
| **Expert Extractors** | Category-specific attribute extraction | Phone → extract Manufacturer, RAM, Storage |
| **Router** | Choose rule vs learned ranking | Decide extraction strategy |
| **Fusion** | Combine 5 ranking signals | Merge scores into single relevance score |
| **Calibration** | Confidence → actual probability | Scale 0.89 → 0.87 (realistic confidence) |
| **Ranker V4** | Cross-encoder neural ranking | Deep learning scoring (trained on triplets) |

---

## 💾 Data Format

### Input: Product
```json
{
  "id": "P12345",
  "title": "iPhone 15 256GB Black",
  "description": "Latest Apple smartphone with 5G"
}
```

### Output: Extracted Attributes
```json
{
  "category": "computer",
  "category_confidence": 0.40,
  "attributes": {
    "Manufacturer": {
      "value": "Apple",
      "confidence": 0.85,
      "explanation": "Found Apple in text"
    },
    "Capacity": {
      "value": 256.0,
      "confidence": 1.0,
      "explanation": "Parsed 256.0 GB"
    },
    "Color": {
      "value": "Black",
      "confidence": 0.9,
      "explanation": "Found Black in text"
    }
  },
  "mandatory_missing": []
}
```

---

## 🔧 Training & Customization

### Train on Your Data

```bash
# 1. Prepare your data
# Create: my_products.jsonl with one product per line

# 2. Run training
python train_ranker_v4_gpu.py --data my_products.jsonl

# 3. Evaluate
python phase_c_evaluate_ranker_real.py --checkpoint ranker_v4_final.pt
```

### Add New Category

1. Define schema in `pave/ontology_schema.py`:
```python
MY_CATEGORY_SCHEMA = CategorySchema(
    category_name="my_category",
    optional_attributes=[
        AttributeSpec(name="Color", datatype=DataType.CATEGORICAL, ...),
        AttributeSpec(name="Size", datatype=DataType.CATEGORICAL, ...),
    ]
)
```

2. Add keywords to `pave/category_classifier.py`:
```python
CATEGORY_SIGNATURES["my_category"] = ["keyword1", "keyword2", ...]
```

3. Restart API - done!

---

## 📁 Project Structure

```
├── pave/
│   ├── api.py                          # FastAPI server (main entry point)
│   ├── category_classifier.py          # Detect product category
│   ├── expert_framework.py             # Extract attributes (rules + ML)
│   ├── expert_manager.py               # Load experts per category
│   ├── dynamic_feature_generator.py    # Generate 10 features
│   ├── learned_router.py               # Choose extraction strategy
│   ├── learned_fusion.py               # Combine ranking signals
│   ├── calibration.py                  # Confidence calibration
│   ├── ranker_v4_inference.py          # Neural ranking model
│   ├── ontology_schema.py              # Product schemas (5 categories)
│   └── dashboard.html                  # Web UI
├── train_ranker_v4_gpu.py              # Training script
├── phase_c_evaluate_ranker_real.py     # Evaluation script
├── requirements.txt                     # Dependencies
├── docker-compose.yml                  # Docker config
└── README.md                           # This file
```

---

## 🎓 Key Insights

1. **Extraction > Ranking**: Focus on clean attributes; ranking is downstream.
2. **Schema = Speed**: Predefined ontology enables fast, reliable extraction.
3. **Hybrid Works**: Combining rules + ML outperforms pure neural.
4. **Confidence Matters**: Calibration layer makes scores actionable.
5. **Category-Specific**: Different product types need different attributes.

---

## 🔗 References

- **Dataset**: [WDC-PAVE (Hugging Face)](https://huggingface.co/datasets/siavashsaki/wdc-pave-ave)
- **Research**: Phase F research report in repo
- **Contact**: siraysanembozdogan@gmail.com

---

**Last Updated**: 2026-07-29  
**License**: MIT
