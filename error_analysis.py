"""Error Analysis: Curriculum Learning Model Failures.

Analyze triplets where model ranks incorrectly.
Categorize failure patterns.
"""

import json
import torch
import numpy as np
from pathlib import Path
from collections import defaultdict

print("\n" + "="*80)
print("CURRICULUM LEARNING ERROR ANALYSIS")
print("="*80)

# Load triplets
print("\nLoading triplets...")
with open("ranker_v4_training_triplets.json", 'r') as f:
    triplets = json.load(f)

print(f"Total triplets: {len(triplets)}")

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

# Load model
print("\nLoading curriculum model...")
model = RankerV4().to(device)
checkpoint_data = torch.load("ranker_v4_curriculum_final.pt", map_location=device)
if isinstance(checkpoint_data, dict):
    model.load_state_dict(checkpoint_data.get("model_state", checkpoint_data))
else:
    model.load_state_dict(checkpoint_data)
model.eval()

# Analyze errors
print("\nAnalyzing errors...")

errors = []
correct = 0
total = 0

with torch.no_grad():
    for triplet in triplets:
        try:
            query = triplet["query"]
            pos_id = triplet.get("positive_product_id", "pos")
            neg_id = triplet.get("negative_product_id", "neg")
            pos_title = triplet.get("positive_title", "")
            neg_title = triplet.get("negative_title", "")
            difficulty = triplet.get("difficulty", "unknown")

            query_emb = model.embedder(query)
            pos_emb = model.embedder(pos_title)
            neg_emb = model.embedder(neg_title)

            pos_score = model(query_emb.unsqueeze(0), pos_emb.unsqueeze(0)).item()
            neg_score = model(query_emb.unsqueeze(0), neg_emb.unsqueeze(0)).item()

            total += 1

            # Check if correct
            if pos_score > neg_score:
                correct += 1
            else:
                # Error: ranked negative higher than positive
                errors.append({
                    "query": query[:80],
                    "positive": pos_title[:80],
                    "negative": neg_title[:80],
                    "pos_score": pos_score,
                    "neg_score": neg_score,
                    "margin": neg_score - pos_score,
                    "difficulty": difficulty,
                    "query_len": len(query),
                    "pos_len": len(pos_title),
                    "neg_len": len(neg_title),
                })

        except Exception as e:
            continue

# Categorize errors
print(f"\nResults: {correct}/{total} correct ({correct/max(total,1)*100:.1f}%)")
print(f"Errors: {len(errors)} ({len(errors)/max(total,1)*100:.1f}%)")

if errors:
    # By difficulty
    by_difficulty = defaultdict(list)
    for error in errors:
        by_difficulty[error["difficulty"]].append(error)

    print(f"\nErrors by Difficulty:")
    for diff in sorted(by_difficulty.keys()):
        count = len(by_difficulty[diff])
        pct = count / len(errors) * 100
        print(f"  {diff}: {count} ({pct:.1f}%)")

    # By margin size
    margins = sorted([e["margin"] for e in errors])
    print(f"\nMargin Statistics (neg_score - pos_score):")
    print(f"  Min: {min(margins):.4f}")
    print(f"  Max: {max(margins):.4f}")
    print(f"  Mean: {np.mean(margins):.4f}")
    print(f"  Median: {np.median(margins):.4f}")

    # Worst errors (largest margins)
    print(f"\nTop 5 Worst Errors (highest neg_score margin):")
    worst = sorted(errors, key=lambda x: x["margin"], reverse=True)[:5]
    for i, error in enumerate(worst, 1):
        print(f"\n  {i}. Margin: {error['margin']:.4f} ({error['difficulty']})")
        print(f"     Query: {error['query']}")
        print(f"     Pos score: {error['pos_score']:.4f}, Neg score: {error['neg_score']:.4f}")

# Save
report = {
    "total": total,
    "correct": correct,
    "accuracy": correct / max(total, 1),
    "errors": len(errors),
    "error_rate": len(errors) / max(total, 1),
    "errors_by_difficulty": {
        diff: len(errs) for diff, errs in by_difficulty.items()
    } if errors else {},
    "worst_errors": worst[:5] if errors else [],
}

with open("error_analysis_report.json", "w") as f:
    json.dump(report, f, indent=2, default=str)

print(f"\nReport saved: error_analysis_report.json")

print("\n" + "="*80)
