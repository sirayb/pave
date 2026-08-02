# Production Deployment Guide

**PAVE: Product Attribute Value Extraction & Ranking**

---

## Quick Start (5 min)

```bash
# 1. Clone & setup
git clone https://github.com/sirayb/pave.git
cd pave
pip install -r requirements.txt

# 2. Download checkpoint
wget https://huggingface.co/sirayb/pave-ranker/resolve/main/ranker_v4_curriculum_final.pt

# 3. Run API
python -m uvicorn api:app --host 0.0.0.0 --port 8000

# 4. Test
curl -X POST http://localhost:8000/extract \
  -H "Content-Type: application/json" \
  -d '{"title": "iPhone 15 256GB Black"}'
```

---

## System Architecture

```
Input (Product Title)
    ↓
[Lexical Normalization] ← 197-term vocabulary
    ↓
[Category Classifier] ← Rule-based + ML
    ↓
[Attribute Extraction] ← Expert framework
    ↓
[Candidate Ranking] ← Curriculum-trained ranker
    ↓
[Benchmark Adapter] ← Dataset-specific mapping
    ↓
Output (Structured Attributes)
```

---

## Configuration

### Environment Variables

```bash
# Model
PAVE_MODEL_PATH=./ranker_v4_curriculum_final.pt
PAVE_DEVICE=cuda  # or 'cpu'
PAVE_BATCH_SIZE=32

# Normalization
PAVE_NORMALIZE=true
PAVE_NORM_THRESHOLD=0.85

# Adapter
PAVE_ADAPTER=wdc  # wdc, amazon, icecat, custom
```

### Hyperparameters

```python
# In config.py
CONFIG = {
    "ranker": {
        "embed_dim": 100,
        "hidden_dim": 256,
        "dropout": 0.2,
        "margin": 0.5,
    },
    "curriculum": {
        "stages": 3,
        "weights": [1.0, 1.5, 2.0],
        "difficulty": ["easy", "medium", "hard"],
    },
    "normalization": {
        "vocabulary_size": 197,
        "confidence_threshold": 0.85,
        "distance_threshold": 2,
    }
}
```

---

## API Endpoints

### 1. Extract Attributes

**POST** `/extract`

```bash
curl -X POST http://localhost:8000/extract \
  -H "Content-Type: application/json" \
  -d '{
    "title": "iPhone 15 256GB Black",
    "description": "Latest Apple smartphone"
  }'
```

**Response:**
```json
{
  "category": "computer",
  "category_confidence": 0.95,
  "attributes": {
    "Manufacturer": {"value": "Apple", "confidence": 0.95},
    "Capacity": {"value": "256GB", "confidence": 1.0},
    "Color": {"value": "Black", "confidence": 0.90}
  },
  "normalization": {
    "applied": true,
    "corrected_tokens": 0,
    "quality_score": 1.0
  }
}
```

### 2. Rank Products

**POST** `/rank`

```bash
curl -X POST http://localhost:8000/rank \
  -H "Content-Type: application/json" \
  -d '{
    "query": "apple phone 256gb",
    "candidates": [
      {"id": "P001", "title": "iPhone 15 256GB Black"},
      {"id": "P002", "title": "iPhone 14 128GB Silver"}
    ]
  }'
```

**Response:**
```json
{
  "query": "apple phone 256gb",
  "results": [
    {"rank": 1, "product_id": "P001", "relevance": 0.89},
    {"rank": 2, "product_id": "P002", "relevance": 0.65}
  ]
}
```

### 3. Validate Gold Standard

**POST** `/validate`

```bash
curl -X POST http://localhost:8000/validate \
  -H "Content-Type: application/json" \
  -d '{
    "title": "iPhone 15 256GB Black",
    "gold_attributes": {
      "Manufacturer": "Apple",
      "Capacity": "256GB"
    }
  }'
```

---

## Monitoring

### Metrics to Track

```python
# In monitoring.py
metrics = {
    "extraction_accuracy": 0.90,      # % correct extractions
    "ranking_mrr": 0.7725,             # Mean Reciprocal Rank
    "ranking_recall_10": 1.0,          # Recall@10
    "normalization_rate": 0.12,        # % queries normalized
    "avg_latency_ms": 45,              # Per-query latency
    "throughput_qps": 22,              # Queries per second
}
```

### Logging

```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('pave.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)
logger.info("Extraction: iPhone 15 -> Computer (0.95)")
logger.warning("Low confidence: 0.45 < 0.5")
logger.error("Model load failed: checkpoint not found")
```

### Health Check

```bash
# /health endpoint
curl http://localhost:8000/health

{
  "status": "healthy",
  "model_loaded": true,
  "categories": 5,
  "vocabulary_size": 197,
  "uptime_seconds": 3600,
  "requests_processed": 1523
}
```

---

## Training & Tuning

### Retrain on New Data

```bash
# 1. Prepare data
python pave/data_utils.py --input your_triplets.json --output train_data.pt

# 2. Configure training
export PAVE_EPOCHS=50
export PAVE_DEVICE=cuda
export PAVE_LEARNING_RATE=2e-4

# 3. Run training
python pave/train_with_curriculum.py \
  --data train_data.pt \
  --epochs 50 \
  --batch_size 32 \
  --output new_checkpoint.pt

# 4. Evaluate
python pave/benchmark_wdc_pave_triplets.py \
  --checkpoint new_checkpoint.pt \
  --output eval_results.json

# 5. Deploy
cp new_checkpoint.pt ranker_v4_curriculum_final.pt
```

### Hyperparameter Tuning

```python
# Grid search
GRID = {
    "learning_rate": [1e-4, 2e-4, 5e-4],
    "margin": [0.3, 0.5, 0.7],
    "weights": [
        [1.0, 1.5, 2.0],  # default
        [1.0, 1.3, 1.8],  # conservative
        [1.0, 2.0, 3.0],  # aggressive
    ]
}

# Run: for each combination, train 50 epochs, evaluate on test
best = max(results, key=lambda x: x['accuracy'])
```

---

## Troubleshooting

### Common Issues

| Issue | Solution |
|-------|----------|
| `ModuleNotFoundError` | Run `pip install -r requirements.txt` |
| `CUDA out of memory` | Reduce batch_size or use CPU mode |
| `Model not found` | Download checkpoint from HuggingFace |
| `Low accuracy` | Increase epochs (50+), retrain on GPU |
| `Slow inference` | Batch requests, enable GPU, check CPU utilization |
| `Normalization issues` | Check vocabulary (should be 197 terms) |

### Debug Mode

```bash
export PAVE_DEBUG=true
python -m uvicorn api:app --log-level debug
```

---

## Scaling

### Single Machine (CPU)
- Throughput: 5 QPS
- Latency: 200ms
- Cost: $0/mo (local)

### Single GPU (A100)
- Throughput: 50+ QPS
- Latency: 20ms
- Cost: $3-5/day (cloud)

### Distributed (Multi-GPU)
- Throughput: 500+ QPS
- Latency: 2-5ms
- Cost: $50-100/day (cloud)

### Serverless (AWS Lambda)
- Throughput: 100+ concurrent
- Latency: 100-500ms (cold start)
- Cost: $0.0000166/request

---

## Maintenance

### Weekly Checks

```bash
# 1. Performance metrics
python pave/monitor.py --period week

# 2. Error analysis
python pave/error_analysis.py --model ranker_v4_curriculum_final.pt

# 3. Backup checkpoint
cp ranker_v4_curriculum_final.pt backups/$(date +%Y%m%d).pt
```

### Monthly Updates

```bash
# 1. Reprocess all queries
python pave/reprocess_batch.py --input 2026-08-01.jsonl

# 2. Evaluate accuracy drift
python pave/accuracy_drift.py

# 3. Retrain if drift > 5%
if python pave/accuracy_drift.py | grep "DRIFT > 5%"; then
    python pave/train_with_curriculum.py --data recent_data.pt
fi
```

---

## Support

**Issues:** https://github.com/sirayb/pave/issues  
**Documentation:** https://github.com/sirayb/pave/wiki  
**Email:** siraysanembozdogan@gmail.com

---

**Version:** 1.0  
**Last Updated:** 2026-08-02  
**Status:** ✅ Production Ready
