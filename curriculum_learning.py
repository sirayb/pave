"""Curriculum Learning for Ranking: Progressive negative difficulty."""

from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from enum import Enum
import math


class Difficulty(Enum):
    """Negative difficulty levels."""
    EASY = 1       # Random negatives, clear semantic distance
    MEDIUM = 2     # Hard negatives, high embedding similarity
    HARD = 3       # Adversarial negatives, same category/close match


@dataclass
class CurriculumStage:
    """Stage in curriculum learning."""
    epoch_start: int
    epoch_end: int
    difficulty: Difficulty
    sampling_weight: float  # Loss weight for this difficulty
    description: str


class CurriculumSchedule:
    """Manages curriculum progression through training."""

    def __init__(self, total_epochs: int = 50):
        """
        Initialize curriculum schedule.

        Args:
            total_epochs: Total training epochs
        """
        self.total_epochs = total_epochs
        self.stages = self._build_default_schedule(total_epochs)

    def _build_default_schedule(self, total_epochs: int) -> List[CurriculumStage]:
        """Build default curriculum: Easy → Medium → Hard."""
        easy_end = int(total_epochs * 0.3)
        medium_end = int(total_epochs * 0.7)

        return [
            CurriculumStage(
                epoch_start=0,
                epoch_end=easy_end,
                difficulty=Difficulty.EASY,
                sampling_weight=1.0,
                description="Random negatives, clear distance"
            ),
            CurriculumStage(
                epoch_start=easy_end,
                epoch_end=medium_end,
                difficulty=Difficulty.MEDIUM,
                sampling_weight=1.5,
                description="Hard negatives, high similarity"
            ),
            CurriculumStage(
                epoch_start=medium_end,
                epoch_end=total_epochs,
                difficulty=Difficulty.HARD,
                sampling_weight=2.0,
                description="Adversarial negatives, same category"
            ),
        ]

    def get_current_stage(self, epoch: int) -> CurriculumStage:
        """Get curriculum stage for epoch."""
        for stage in self.stages:
            if stage.epoch_start <= epoch < stage.epoch_end:
                return stage
        return self.stages[-1]

    def get_difficulty(self, epoch: int) -> Difficulty:
        """Get difficulty level for epoch."""
        return self.get_current_stage(epoch).difficulty

    def get_loss_weight(self, epoch: int) -> float:
        """Get loss weight multiplier for epoch."""
        return self.get_current_stage(epoch).sampling_weight

    def progress(self, epoch: int) -> Dict[str, any]:
        """Get progress info for epoch."""
        stage = self.get_current_stage(epoch)
        progress_in_stage = (epoch - stage.epoch_start) / (stage.epoch_end - stage.epoch_start)

        return {
            "epoch": epoch,
            "total_epochs": self.total_epochs,
            "difficulty": stage.difficulty.name,
            "loss_weight": stage.sampling_weight,
            "stage_progress": f"{progress_in_stage:.1%}",
            "description": stage.description,
        }


class NegativeDifficulty:
    """Score negative samples by difficulty."""

    @staticmethod
    def score_easy(
        query_embedding: List[float],
        negative_embedding: List[float],
        positive_embedding: List[float]
    ) -> float:
        """
        Easy negatives: far from query and positive.

        Returns:
            Difficulty score [0, 1]. Higher = harder.
        """
        query_neg_sim = _cosine_similarity(query_embedding, negative_embedding)
        pos_neg_sim = _cosine_similarity(positive_embedding, negative_embedding)

        # Easy if far from both
        distance_metric = (1 - query_neg_sim) + (1 - pos_neg_sim)
        return min(distance_metric / 2, 1.0)

    @staticmethod
    def score_medium(
        query_embedding: List[float],
        negative_embedding: List[float],
        positive_embedding: List[float]
    ) -> float:
        """
        Medium negatives: similar to query but not positive.

        Returns:
            Difficulty score [0, 1]. Higher = harder.
        """
        query_neg_sim = _cosine_similarity(query_embedding, negative_embedding)
        pos_neg_sim = _cosine_similarity(positive_embedding, negative_embedding)

        # Hard if similar to query but different from positive
        similarity_metric = query_neg_sim * (1 - pos_neg_sim)
        return min(similarity_metric, 1.0)

    @staticmethod
    def score_hard(
        query_embedding: List[float],
        negative_embedding: List[float],
        positive_embedding: List[float],
        category_match: bool = False
    ) -> float:
        """
        Hard (adversarial) negatives: same category, close match.

        Args:
            category_match: True if negative is same category as positive

        Returns:
            Difficulty score [0, 1]. Higher = harder.
        """
        query_neg_sim = _cosine_similarity(query_embedding, negative_embedding)
        pos_neg_sim = _cosine_similarity(positive_embedding, negative_embedding)

        # Hardest if very similar to both query AND positive
        adversarial_metric = query_neg_sim * pos_neg_sim

        if category_match:
            adversarial_metric *= 1.2  # Boost if same category

        return min(adversarial_metric, 1.0)


class HardNegativeMiner:
    """Mining hard negatives with curriculum-aware selection."""

    def __init__(self, curriculum: CurriculumSchedule):
        """
        Initialize miner.

        Args:
            curriculum: Curriculum schedule for progression
        """
        self.curriculum = curriculum

    def select_negatives(
        self,
        query_embedding: List[float],
        positive_embedding: List[float],
        candidate_embeddings: Dict[str, List[float]],
        candidate_categories: Dict[str, str],
        positive_category: str,
        epoch: int,
        num_negatives: int = 3
    ) -> List[str]:
        """
        Select hard negatives based on curriculum difficulty.

        Args:
            query_embedding: Query embedding
            positive_embedding: Positive example embedding
            candidate_embeddings: {candidate_id: embedding}
            candidate_categories: {candidate_id: category}
            positive_category: Category of positive example
            epoch: Current training epoch
            num_negatives: Number of negatives to select

        Returns:
            List of selected negative candidate IDs
        """
        difficulty = self.curriculum.get_difficulty(epoch)

        # Score each candidate by difficulty
        scores = {}
        for cand_id, cand_emb in candidate_embeddings.items():
            if difficulty == Difficulty.EASY:
                scores[cand_id] = NegativeDifficulty.score_easy(
                    query_embedding, cand_emb, positive_embedding
                )
            elif difficulty == Difficulty.MEDIUM:
                scores[cand_id] = NegativeDifficulty.score_medium(
                    query_embedding, cand_emb, positive_embedding
                )
            else:  # HARD
                is_same_category = candidate_categories.get(cand_id) == positive_category
                scores[cand_id] = NegativeDifficulty.score_hard(
                    query_embedding, cand_emb, positive_embedding,
                    category_match=is_same_category
                )

        # Sort by difficulty and select top N
        sorted_cands = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return [cand_id for cand_id, _ in sorted_cands[:num_negatives]]


def _cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """Compute cosine similarity between vectors."""
    if not vec1 or not vec2 or len(vec1) != len(vec2):
        return 0.0

    dot_product = sum(a * b for a, b in zip(vec1, vec2))
    norm1 = math.sqrt(sum(a ** 2 for a in vec1))
    norm2 = math.sqrt(sum(b ** 2 for b in vec2))

    if norm1 == 0 or norm2 == 0:
        return 0.0

    return dot_product / (norm1 * norm2)
