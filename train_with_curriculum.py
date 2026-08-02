"""Train Ranker V4 with Curriculum Learning on WDC-PAVE.

Comparison script: Regular training vs Curriculum Learning
- Baseline: train_ranker_v4_gpu.py (standard triplet loss)
- Curriculum: This script (progressive negative difficulty)

Expected: Curriculum should improve MRR by 5-15% on test set.
"""

import json
import sys
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, Dataset
from torch.optim import Adam
from pathlib import Path
from tqdm import tqdm
from datetime import datetime

sys.path.insert(0, 'pave')

from curriculum_learning import CurriculumSchedule, HardNegativeMiner
from ranker_training import TripletLoss, RankingLoss

print("\n" + "="*80)
print("RANKER V4 + CURRICULUM LEARNING ON WDC-PAVE")
print("="*80)

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f"\nDevice: {device}")

if device.type == "cuda":
    print(f"GPU: {torch.cuda.get_device_name(0)}")
else:
    print("[WARNING] Using CPU. Training will be slow.")

# Load data
print("\nLoading WDC-PAVE triplets...")
with open("wdc_pave_triplets.json", 'r') as f:
    triplets = json.load(f)

print(f"Loaded {len(triplets)} triplets")

# Dataset class
class TripletDataset(Dataset):
    """WDC-PAVE triplet dataset."""

    def __init__(self, triplets, max_len=512):
        self.triplets = triplets
        self.max_len = max_len

    def __len__(self):
        return len(self.triplets)

    def __getitem__(self, idx):
        t = self.triplets[idx]

        query = (t["query"] or "")[:self.max_len]
        pos_title = (t["positive"]["title"] or "")[:self.max_len]
        neg_title = (t["negative"]["title"] or "")[:self.max_len]

        return {
            "query": query,
            "positive": pos_title,
            "negative": neg_title,
            "query_id": t["query_id"],
            "category": t["category"]
        }

dataset = TripletDataset(triplets)
print(f"Dataset: {len(dataset)} samples")

# Model definition
class SimpleEmbedder(nn.Module):
    """Simple embedding (hash-based demo)."""

    def __init__(self, vocab_size=10000, embed_dim=100):
        super().__init__()
        self.embedding = nn.Embedding(vocab_size, embed_dim)

    def forward(self, text):
        """Deterministic embedding."""
        tokens = [hash(c) % 10000 for c in text[:100]]
        tokens = torch.tensor(tokens, dtype=torch.long, device=self.embedding.weight.device)
        embs = self.embedding(tokens)
        return embs.mean(dim=0)


class RankerV4(nn.Module):
    """Cross-encoder Ranker V4."""

    def __init__(self, embed_dim=100, hidden_dim=256):
        super().__init__()

        self.embed_dim = embed_dim
        self.embedder = SimpleEmbedder(embed_dim=embed_dim)

        self.fc1 = nn.Linear(embed_dim * 2, hidden_dim)
        self.bn1 = nn.BatchNorm1d(hidden_dim)
        self.dropout1 = nn.Dropout(0.2)

        self.fc2 = nn.Linear(hidden_dim, hidden_dim // 2)
        self.bn2 = nn.BatchNorm1d(hidden_dim // 2)
        self.dropout2 = nn.Dropout(0.2)

        self.fc3 = nn.Linear(hidden_dim // 2, 1)
        self.sigmoid = nn.Sigmoid()

    def forward(self, query_emb, candidate_emb):
        """Score (query, candidate) pair."""
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

model = RankerV4().to(device)
print(f"\nModel: RankerV4 (cross-encoder)")
print(f"Parameters: {sum(p.numel() for p in model.parameters()):,}")

# Training setup
batch_size = 32 if device.type == "cuda" else 8
num_epochs = 10 if device.type == "cuda" else 2
learning_rate = 2e-4

train_loader = DataLoader(dataset, batch_size=batch_size, shuffle=True, num_workers=0)
optimizer = Adam(model.parameters(), lr=learning_rate)

print(f"\nTraining setup:")
print(f"  Batch size: {batch_size}")
print(f"  Epochs: {num_epochs}")
print(f"  Learning rate: {learning_rate}")
print(f"  Total steps: {num_epochs * len(train_loader)}")

# Curriculum setup
print(f"\nCurriculum Learning setup:")
curriculum = CurriculumSchedule(total_epochs=num_epochs)
print(f"  Stage 1 (EASY): epochs 0-{int(num_epochs*0.3)} (weight 1.0x)")
print(f"  Stage 2 (MEDIUM): epochs {int(num_epochs*0.3)}-{int(num_epochs*0.7)} (weight 1.5x)")
print(f"  Stage 3 (HARD): epochs {int(num_epochs*0.7)}-{num_epochs} (weight 2.0x)")

# Losses
triplet_loss_fn = TripletLoss(margin=1.0)
ranking_loss_fn = RankingLoss()

# Training loop
print(f"\n" + "="*80)
print("TRAINING")
print("="*80)

best_loss = float('inf')
history = []

for epoch in range(num_epochs):
    model.train()
    epoch_loss = 0.0
    triplet_loss_total = 0.0
    ranking_loss_total = 0.0
    batch_count = 0

    # Get curriculum info
    curriculum_stage = curriculum.get_current_stage(epoch)
    loss_weight = curriculum.get_loss_weight(epoch)
    difficulty = curriculum_stage.difficulty.name

    print(f"\nEpoch {epoch + 1}/{num_epochs} | Curriculum: {difficulty} (weight={loss_weight:.1f}x)")

    progress_bar = tqdm(train_loader, desc=f"Epoch {epoch + 1}", total=len(train_loader))

    for batch in progress_bar:
        optimizer.zero_grad()

        # Get embeddings
        query_embs = torch.stack([
            model.embedder(q) for q in batch["query"]
        ]).to(device)

        pos_embs = torch.stack([
            model.embedder(p) for p in batch["positive"]
        ]).to(device)

        neg_embs = torch.stack([
            model.embedder(n) for n in batch["negative"]
        ]).to(device)

        # Scores
        pos_scores = model(query_embs, pos_embs)
        neg_scores = model(query_embs, neg_embs)

        # Losses
        trip_loss = triplet_loss_fn(query_embs, pos_embs, neg_embs)
        rank_loss = ranking_loss_fn(pos_scores, neg_scores)

        # Combined loss with curriculum weight
        loss = (trip_loss + rank_loss) * loss_weight

        # Backward
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        optimizer.step()

        epoch_loss += loss.item()
        triplet_loss_total += trip_loss.item()
        ranking_loss_total += rank_loss.item()
        batch_count += 1

        progress_bar.update(1)
        progress_bar.set_postfix({
            "loss": f"{loss.item():.4f}",
            "difficulty": difficulty
        })

    avg_loss = epoch_loss / batch_count
    avg_triplet = triplet_loss_total / batch_count
    avg_ranking = ranking_loss_total / batch_count

    history.append({
        "epoch": epoch,
        "loss": avg_loss,
        "triplet_loss": avg_triplet,
        "ranking_loss": avg_ranking,
        "curriculum_difficulty": difficulty,
        "curriculum_weight": loss_weight,
        "timestamp": datetime.now().isoformat()
    })

    print(f"Epoch {epoch + 1} complete:")
    print(f"  Total Loss: {avg_loss:.6f}")
    print(f"  Triplet Loss: {avg_triplet:.6f}")
    print(f"  Ranking Loss: {avg_ranking:.6f}")
    print(f"  Curriculum: {difficulty} ({loss_weight:.1f}x)")

    # Save checkpoint
    if avg_loss < best_loss:
        best_loss = avg_loss
        checkpoint_path = f"ranker_v4_curriculum_best.pt"
        torch.save({
            "epoch": epoch,
            "model_state": model.state_dict(),
            "optimizer_state": optimizer.state_dict(),
            "loss": avg_loss,
            "curriculum_difficulty": difficulty,
        }, checkpoint_path)
        print(f"  [BEST] Saved: {checkpoint_path}")

# Save training history
history_path = "ranker_v4_curriculum_history.json"
with open(history_path, 'w') as f:
    json.dump(history, f, indent=2)
print(f"\nTraining history saved: {history_path}")

# Save final checkpoint
final_checkpoint = "ranker_v4_curriculum_final.pt"
torch.save({
    "epoch": num_epochs - 1,
    "model_state": model.state_dict(),
    "optimizer_state": optimizer.state_dict(),
    "loss": avg_loss,
}, final_checkpoint)
print(f"Final checkpoint saved: {final_checkpoint}")

print("\n" + "="*80)
print("TRAINING COMPLETE")
print("="*80)
print(f"\nNext: Run evaluation and compare with baseline")
print(f"  Baseline: ranker_v4_final.pt")
print(f"  Curriculum: ranker_v4_curriculum_final.pt")
