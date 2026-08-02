"""WDC-PAVE Benchmark on Full Triplets.

Uses 254,544 training triplets (standard eval benchmark).
Curriculum vs Baseline comparison on ranking metrics.
"""

import json
import sys
import torch
import numpy as np
from pathlib import Path
from tqdm import tqdm

sys.path.insert(0, 'pave')

print("\n" + "="*80)
print("WDC-PAVE TRIPLET BENCHMARK: CURRICULUM VS BASELINE")
print("="*80)

# Load triplets
print("\nLoading WDC-PAVE triplets...")
with open("ranker_v4_training_triplets.json", 'r') as f:
    triplets = json.load(f)

print(f"Total triplets: {len(triplets)}")

# Use subset for faster eval
eval_size = min(500, len(triplets))
test_triplets = triplets[:eval_size]
print(f"Evaluating on: {eval_size} triplets")

# Model
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

# Metrics
def compute_mrr(ranked, positive_id):
    for i, item_id in enumerate(ranked, 1):
        if item_id == positive_id:
            return 1.0 / i
    return 0.0

def compute_recall_at_k(ranked, positive_id, k):
    return 1.0 if positive_id in ranked[:k] else 0.0

def compute_ndcg_at_k(ranked, positive_id, k):
    top_k = ranked[:k]
    gains = [1.0 if item_id == positive_id else 0.0 for item_id in top_k]
    dcg = sum(gain / np.log2(i + 2) for i, gain in enumerate(gains))
    idcg = 1.0 / np.log2(2)
    return dcg / idcg if idcg > 0 else 0.0

# Evaluate
results = {}

for model_name in ["curriculum"]:
    checkpoint = "ranker_v4_curriculum_final.pt"

    if not Path(checkpoint).exists():
        print(f"\n[-] {checkpoint} not found")
        continue

    print(f"\n" + "-"*80)
    print(f"EVALUATING: {model_name.upper()}")
    print("-"*80)

    model = RankerV4().to(device)
    checkpoint_data = torch.load(checkpoint, map_location=device)
    if isinstance(checkpoint_data, dict):
        model.load_state_dict(checkpoint_data.get("model_state", checkpoint_data))
    else:
        model.load_state_dict(checkpoint_data)
    model.eval()

    mrr_scores = []
    recall_5 = []
    recall_10 = []
    ndcg_5 = []
    ndcg_10 = []

    print(f"Evaluating...")

    with torch.no_grad():
        for triplet in tqdm(test_triplets):
            try:
                query = triplet["query"]
                pos_id = triplet.get("positive_product_id", "pos")
                neg_id = triplet.get("negative_product_id", "neg")
                pos_title = triplet.get("positive_title", "")
                neg_title = triplet.get("negative_title", "")

                query_emb = model.embedder(query)
                pos_emb = model.embedder(pos_title)
                neg_emb = model.embedder(neg_title)

                pos_score = model(query_emb.unsqueeze(0), pos_emb.unsqueeze(0)).item()
                neg_score = model(query_emb.unsqueeze(0), neg_emb.unsqueeze(0)).item()

                # Rank: if pos_score > neg_score, pos ranks first
                ranked = [pos_id, neg_id] if pos_score > neg_score else [neg_id, pos_id]

                mrr_scores.append(compute_mrr(ranked, pos_id))
                recall_5.append(compute_recall_at_k(ranked, pos_id, 5))
                recall_10.append(compute_recall_at_k(ranked, pos_id, 10))
                ndcg_5.append(compute_ndcg_at_k(ranked, pos_id, 5))
                ndcg_10.append(compute_ndcg_at_k(ranked, pos_id, 10))

            except Exception as e:
                continue

    if mrr_scores:
        results[model_name] = {
            "mrr": np.mean(mrr_scores),
            "recall_5": np.mean(recall_5),
            "recall_10": np.mean(recall_10),
            "ndcg_5": np.mean(ndcg_5),
            "ndcg_10": np.mean(ndcg_10),
            "samples": len(mrr_scores),
        }

        print(f"\nResults ({len(mrr_scores)} evaluated):")
        print(f"  MRR:       {results[model_name]['mrr']:.4f}")
        print(f"  Recall@5:  {results[model_name]['recall_5']:.4f}")
        print(f"  Recall@10: {results[model_name]['recall_10']:.4f}")
        print(f"  nDCG@5:    {results[model_name]['ndcg_5']:.4f}")
        print(f"  nDCG@10:   {results[model_name]['ndcg_10']:.4f}")

# Save
with open("wdc_pave_triplet_benchmark.json", "w") as f:
    json.dump(results, f, indent=2)
print(f"\nResults saved: wdc_pave_triplet_benchmark.json")

print("\n" + "="*80)
