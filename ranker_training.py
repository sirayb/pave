"""Ranker V4 Training with Curriculum Learning and Triplet Loss."""

from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
import torch
import torch.nn as nn
from torch.optim import Adam
from pathlib import Path
import json
from datetime import datetime

try:
    from .curriculum_learning import CurriculumSchedule, HardNegativeMiner
except ImportError:
    from curriculum_learning import CurriculumSchedule, HardNegativeMiner

try:
    from .ranker_v4_inference import CrossEncoderRanker
except ImportError:
    pass  # Not needed for training


@dataclass
class TrainingConfig:
    """Training hyperparameters."""
    num_epochs: int = 50
    batch_size: int = 32
    learning_rate: float = 1e-4
    margin: float = 0.5  # Triplet loss margin
    device: str = "cpu"
    checkpoint_dir: str = "checkpoints"
    log_interval: int = 10


@dataclass
class TrainingMetrics:
    """Metrics for training epoch."""
    epoch: int
    loss: float
    triplet_loss: float
    ranking_loss: float
    curriculum_difficulty: str
    curriculum_weight: float
    lr: float


class TripletLoss(nn.Module):
    """Triplet loss with hard negatives."""

    def __init__(self, margin: float = 0.5):
        """
        Initialize triplet loss.

        Args:
            margin: Margin between positive and negative pairs
        """
        super().__init__()
        self.margin = margin

    def forward(
        self,
        anchor: torch.Tensor,
        positive: torch.Tensor,
        negative: torch.Tensor
    ) -> torch.Tensor:
        """
        Compute triplet loss.

        Args:
            anchor: Anchor embeddings [batch_size, embedding_dim]
            positive: Positive embeddings [batch_size, embedding_dim]
            negative: Negative embeddings [batch_size, embedding_dim]

        Returns:
            Loss scalar
        """
        pos_dist = torch.norm(anchor - positive, dim=1)
        neg_dist = torch.norm(anchor - negative, dim=1)

        loss = torch.clamp(pos_dist - neg_dist + self.margin, min=0.0)
        return loss.mean()


class RankingLoss(nn.Module):
    """Ranking loss: prefer positive over negative."""

    def __init__(self):
        super().__init__()
        self.bce = nn.BCELoss()

    def forward(
        self,
        pos_scores: torch.Tensor,
        neg_scores: torch.Tensor
    ) -> torch.Tensor:
        """
        Ranking loss: positive scores > 1, negative scores > 0.

        Args:
            pos_scores: Scores for positive examples [batch_size, 1]
            neg_scores: Scores for negative examples [batch_size, 1]

        Returns:
            Loss scalar
        """
        pos_labels = torch.ones_like(pos_scores)
        neg_labels = torch.zeros_like(neg_scores)

        pos_loss = self.bce(pos_scores, pos_labels)
        neg_loss = self.bce(neg_scores, neg_labels)

        return (pos_loss + neg_loss) / 2


class RankerTrainer:
    """Training loop with curriculum learning."""

    def __init__(self, config: TrainingConfig):
        """
        Initialize trainer.

        Args:
            config: Training configuration
        """
        self.config = config
        self.device = torch.device(config.device)

        # Models and losses
        self.ranker = CrossEncoderRanker().to(self.device)
        self.optimizer = Adam(self.ranker.parameters(), lr=config.learning_rate)

        self.triplet_loss_fn = TripletLoss(margin=config.margin)
        self.ranking_loss_fn = RankingLoss()

        # Curriculum
        self.curriculum = CurriculumSchedule(total_epochs=config.num_epochs)
        self.hard_miner = HardNegativeMiner(self.curriculum)

        # Tracking
        self.history: List[TrainingMetrics] = []
        Path(config.checkpoint_dir).mkdir(exist_ok=True)

    def train_epoch(
        self,
        epoch: int,
        triplets: List[Tuple[str, str, str]],
        embeddings: Dict[str, torch.Tensor],
        categories: Dict[str, str]
    ) -> TrainingMetrics:
        """
        Train single epoch.

        Args:
            epoch: Epoch number
            triplets: List of (query, positive_cand, negative_cand) triplets
            embeddings: Pre-computed embeddings for all items
            categories: Category for each candidate

        Returns:
            Training metrics for epoch
        """
        self.ranker.train()
        curriculum_stage = self.curriculum.get_current_stage(epoch)
        loss_weight = self.curriculum.get_loss_weight(epoch)

        total_triplet_loss = 0.0
        total_ranking_loss = 0.0
        num_batches = 0

        for i in range(0, len(triplets), self.config.batch_size):
            batch_triplets = triplets[i:i + self.config.batch_size]

            batch_triplet_loss = 0.0
            batch_ranking_loss = 0.0

            for query_id, pos_cand_id, neg_cand_id in batch_triplets:
                query_emb = embeddings[query_id]
                pos_emb = embeddings[pos_cand_id]
                neg_emb = embeddings[neg_cand_id]

                pos_score = self.ranker(query_emb.unsqueeze(0), pos_emb.unsqueeze(0))
                neg_score = self.ranker(query_emb.unsqueeze(0), neg_emb.unsqueeze(0))

                trip_loss = self.triplet_loss_fn(
                    query_emb.unsqueeze(0),
                    pos_emb.unsqueeze(0),
                    neg_emb.unsqueeze(0)
                )

                rank_loss = self.ranking_loss_fn(pos_score, neg_score)

                loss = (trip_loss + rank_loss) * loss_weight

                batch_triplet_loss += trip_loss.item()
                batch_ranking_loss += rank_loss.item()

                self.optimizer.zero_grad()
                loss.backward()
                self.optimizer.step()

            total_triplet_loss += batch_triplet_loss
            total_ranking_loss += batch_ranking_loss
            num_batches += 1

        avg_triplet_loss = total_triplet_loss / num_batches if num_batches > 0 else 0.0
        avg_ranking_loss = total_ranking_loss / num_batches if num_batches > 0 else 0.0
        avg_total_loss = avg_triplet_loss + avg_ranking_loss

        metrics = TrainingMetrics(
            epoch=epoch,
            loss=avg_total_loss,
            triplet_loss=avg_triplet_loss,
            ranking_loss=avg_ranking_loss,
            curriculum_difficulty=curriculum_stage.difficulty.name,
            curriculum_weight=loss_weight,
            lr=self.config.learning_rate
        )

        self.history.append(metrics)

        if epoch % self.config.log_interval == 0:
            print(
                f"Epoch {epoch}/{self.config.num_epochs} | "
                f"Loss: {avg_total_loss:.4f} | "
                f"Triplet: {avg_triplet_loss:.4f} | "
                f"Ranking: {avg_ranking_loss:.4f} | "
                f"Curriculum: {curriculum_stage.difficulty.name} | "
                f"Weight: {loss_weight:.2f}"
            )

        return metrics

    def train(
        self,
        triplets: List[Tuple[str, str, str]],
        embeddings: Dict[str, torch.Tensor],
        categories: Dict[str, str],
        validation_triplets: Optional[List[Tuple[str, str, str]]] = None
    ):
        """Full training loop."""
        for epoch in range(self.config.num_epochs):
            metrics = self.train_epoch(epoch, triplets, embeddings, categories)

            if validation_triplets and epoch % 5 == 0:
                val_metrics = self.validate(epoch, validation_triplets, embeddings)
                print(f"  Validation Loss: {val_metrics['loss']:.4f}")

            if epoch % 10 == 0 and epoch > 0:
                self.save_checkpoint(epoch)

    def validate(
        self,
        epoch: int,
        triplets: List[Tuple[str, str, str]],
        embeddings: Dict[str, torch.Tensor]
    ) -> Dict[str, float]:
        """Validate on triplets."""
        self.ranker.eval()
        total_loss = 0.0
        num_triplets = 0

        with torch.no_grad():
            for query_id, pos_cand_id, neg_cand_id in triplets:
                query_emb = embeddings[query_id]
                pos_emb = embeddings[pos_cand_id]
                neg_emb = embeddings[neg_cand_id]

                pos_score = self.ranker(query_emb.unsqueeze(0), pos_emb.unsqueeze(0))
                neg_score = self.ranker(query_emb.unsqueeze(0), neg_emb.unsqueeze(0))

                loss = self.ranking_loss_fn(pos_score, neg_score)
                total_loss += loss.item()
                num_triplets += 1

        return {"loss": total_loss / max(num_triplets, 1)}

    def save_checkpoint(self, epoch: int):
        """Save model checkpoint."""
        path = Path(self.config.checkpoint_dir) / f"ranker_epoch_{epoch}.pt"
        torch.save(self.ranker.state_dict(), path)
        print(f"Checkpoint saved: {path}")

    def save_history(self):
        """Save training history to JSON."""
        history_path = Path(self.config.checkpoint_dir) / "training_history.json"
        data = [
            {
                "epoch": m.epoch,
                "loss": m.loss,
                "triplet_loss": m.triplet_loss,
                "ranking_loss": m.ranking_loss,
                "curriculum_difficulty": m.curriculum_difficulty,
                "curriculum_weight": m.curriculum_weight,
            }
            for m in self.history
        ]
        with open(history_path, "w") as f:
            json.dump(data, f, indent=2)
        print(f"Training history saved: {history_path}")
