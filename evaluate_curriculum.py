"""Quick evaluation: Curriculum vs Baseline on training triplets.

Simpler eval using available data.
Metrics: MRR, Recall@10, nDCG@10
"""

import json
import sys
import torch
import numpy as np
from pathlib import Path

sys.path.insert(0, 'pave')

print("\n" + "="*80)
print("CURRICULUM VS BASELINE EVALUATION")
print("="*80)

# Load data
print("\nLoading test triplets...")
with open("ranker_v4_training_triplets.json", 'r') as f:
    triplets = json.load(f)

# Use subset for quick eval
eval_size = min(50, len(triplets))
test_triplets = triplets[:eval_size]
print(f"Evaluating on {eval_size} triplets")

# Define model (same as training)
class SimpleEmbedder(torch.nn.Module):
    def __init__(self, vocab_size=10000, embed_dim=100):
        super().__init__()
        self.embedding = torch.nn.Embedding(vocab_size, embed_dim)

    def forward(self, text):
        tokens = [hash(c) % 10000 for c in text[:100]]
        tokens = torch.tensor(tokens, dtype=torch.long, device=self.embedding.weight.device)
        embs = self.embedding(tokens)
        return embs.mean(dim=0)

class RankerV4(torch.nn.Module):
    def __init__(self, embed_dim=100, hidden_dim=256):
        super().__init__()
        self.embed_dim = embed_dim
        self.embedder = SimpleEmbedder(embed_dim=embed_dim)
        self.fc1 = torch.nn.Linear(embed_dim * 2, hidden_dim)
        self.bn1 = torch.nn.BatchNorm1d(hidden_dim)
        self.dropout1 = torch.nn.Dropout(0.2)
        self.fc2 = torch.nn.Linear(hidden_dim, hidden_dim // 2)
        self.bn2 = torch.nn.BatchNorm1d(hidden_dim // 2)
        self.dropout2 = torch.nn.Dropout(0.2)
        self.fc3 = torch.nn.Linear(hidden_dim // 2, 1)
        self.sigmoid = torch.nn.Sigmoid()

    def forward(self, query_emb, candidate_emb):
        combined = torch.cat([query_emb, candidate_emb], dim=-1)
        x = self.fc1(combined)
        x = self.bn1(x)
        x = torch.relu(x)
        x = self.dropout1(x)
        x = self.fc2(x)
        x = self.bn2(x)
        x = torch.relu(x)
        x = self.dropout2(x)
        score = self.sigmoid(self.fc3(x))
        return score

device = torch.device("cpu")

# Evaluation metrics
def compute_mrr(ranked_ids, positive_id):
    for i, item_id in enumerate(ranked_ids, 1):
        if item_id == positive_id:
            return 1.0 / i
    return 0.0

def compute_recall_at_k(ranked_ids, positive_id, k=10):
    return 1.0 if positive_id in ranked_ids[:k] else 0.0

def compute_ndcg_at_k(ranked_ids, positive_id, k=10):
    top_k = ranked_ids[:k]
    gains = [1.0 if item_id == positive_id else 0.0 for item_id in top_k]
    dcg = sum(gain / np.log2(i + 2) for i, gain in enumerate(gains))
    idcg = 1.0 / np.log2(2)
    return dcg / idcg if idcg > 0 else 0.0

# Test both models
results = {}

for model_name in ["baseline", "curriculum"]:
    if model_name == "baseline":
        checkpoint = "ranker_v4_final.pt"
    else:
        checkpoint = "ranker_v4_curriculum_final.pt"

    if not Path(checkpoint).exists():
        print(f"[-] {checkpoint} not found")
        continue

    print(f"\nEvaluating {model_name}...")
    model = RankerV4().to(device)

    # Load checkpoint
    checkpoint_data = torch.load(checkpoint, map_location=device)
    if isinstance(checkpoint_data, dict):
        model.load_state_dict(checkpoint_data.get("model_state", checkpoint_data))
    else:
        model.load_state_dict(checkpoint_data)

    model.eval()

    mrr_scores = []
    recall_10 = []
    recall_5 = []
    ndcg_10 = []
    ndcg_5 = []

    with torch.no_grad():
        for triplet in test_triplets:
            query = triplet["query"]
            positive_id = triplet["positive_product_id"]
            negative_id = triplet["negative_product_id"]

            query_emb = model.embedder(query)

            # Score positive and negative
            pos_emb = model.embedder(triplet["positive_title"])
            neg_emb = model.embedder(triplet["negative_title"])

            pos_score = model(query_emb.unsqueeze(0), pos_emb.unsqueeze(0)).item()
            neg_score = model(query_emb.unsqueeze(0), neg_emb.unsqueeze(0)).item()

            # Rank: positive first if pos_score > neg_score
            if pos_score > neg_score:
                ranked = [positive_id, negative_id]
            else:
                ranked = [negative_id, positive_id]

            # Compute metrics
            mrr_scores.append(compute_mrr(ranked, positive_id))
            recall_10.append(compute_recall_at_k(ranked, positive_id, 10))
            recall_5.append(compute_recall_at_k(ranked, positive_id, 5))
            ndcg_10.append(compute_ndcg_at_k(ranked, positive_id, 10))
            ndcg_5.append(compute_ndcg_at_k(ranked, positive_id, 5))

    results[model_name] = {
        "mrr": np.mean(mrr_scores),
        "recall_5": np.mean(recall_5),
        "recall_10": np.mean(recall_10),
        "ndcg_5": np.mean(ndcg_5),
        "ndcg_10": np.mean(ndcg_10),
    }

    print(f"  MRR: {results[model_name]['mrr']:.4f}")
    print(f"  Recall@5: {results[model_name]['recall_5']:.4f}")
    print(f"  Recall@10: {results[model_name]['recall_10']:.4f}")
    print(f"  nDCG@5: {results[model_name]['ndcg_5']:.4f}")
    print(f"  nDCG@10: {results[model_name]['ndcg_10']:.4f}")

# Comparison
print("\n" + "-"*80)
print("COMPARISON")
print("-"*80)

if "baseline" in results and "curriculum" in results:
    baseline = results["baseline"]
    curriculum = results["curriculum"]

    print(f"\nMetric       | Baseline | Curriculum | Improvement")
    print(f"MRR          | {baseline['mrr']:.4f}   | {curriculum['mrr']:.4f}      | {((curriculum['mrr'] - baseline['mrr']) / max(baseline['mrr'], 0.0001) * 100):.1f}%")
    print(f"Recall@5     | {baseline['recall_5']:.4f}   | {curriculum['recall_5']:.4f}      | {((curriculum['recall_5'] - baseline['recall_5']) / max(baseline['recall_5'], 0.0001) * 100):.1f}%")
    print(f"Recall@10    | {baseline['recall_10']:.4f}   | {curriculum['recall_10']:.4f}      | {((curriculum['recall_10'] - baseline['recall_10']) / max(baseline['recall_10'], 0.0001) * 100):.1f}%")
    print(f"nDCG@5       | {baseline['ndcg_5']:.4f}   | {curriculum['ndcg_5']:.4f}      | {((curriculum['ndcg_5'] - baseline['ndcg_5']) / max(baseline['ndcg_5'], 0.0001) * 100):.1f}%")
    print(f"nDCG@10      | {baseline['ndcg_10']:.4f}   | {curriculum['ndcg_10']:.4f}      | {((curriculum['ndcg_10'] - baseline['ndcg_10']) / max(baseline['ndcg_10'], 0.0001) * 100):.1f}%")

    # Save results
    with open("curriculum_evaluation_results.json", "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved: curriculum_evaluation_results.json")

print("\n" + "="*80)
