"""Tests for Curriculum Learning."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from curriculum_learning import (
    CurriculumSchedule, Difficulty, HardNegativeMiner,
    NegativeDifficulty
)


def test_curriculum_schedule_creation():
    """Test curriculum schedule creation."""
    curriculum = CurriculumSchedule(total_epochs=50)

    assert len(curriculum.stages) == 3, "Should have 3 stages"
    assert curriculum.stages[0].difficulty == Difficulty.EASY
    assert curriculum.stages[1].difficulty == Difficulty.MEDIUM
    assert curriculum.stages[2].difficulty == Difficulty.HARD

    print("[PASS] Curriculum schedule creation")


def test_curriculum_stage_transitions():
    """Test transitions between curriculum stages."""
    curriculum = CurriculumSchedule(total_epochs=50)

    stage = curriculum.get_current_stage(0)
    assert stage.difficulty == Difficulty.EASY

    stage = curriculum.get_current_stage(25)
    assert stage.difficulty == Difficulty.MEDIUM

    stage = curriculum.get_current_stage(40)
    assert stage.difficulty == Difficulty.HARD

    print("[PASS] Curriculum stage transitions")


def test_loss_weight_progression():
    """Test loss weight increases with difficulty."""
    curriculum = CurriculumSchedule(total_epochs=50)

    easy_weight = curriculum.get_loss_weight(5)
    medium_weight = curriculum.get_loss_weight(25)
    hard_weight = curriculum.get_loss_weight(45)

    assert easy_weight < medium_weight < hard_weight, \
        f"Weights should increase: {easy_weight} < {medium_weight} < {hard_weight}"

    print(f"[PASS] Loss weight progression: {easy_weight:.1f} > {medium_weight:.1f} > {hard_weight:.1f}")


def test_negative_difficulty_scoring():
    """Test negative difficulty scoring."""
    query_emb = [1.0, 0.0, 0.0, 0.0, 0.0]
    positive_emb = [0.9, 0.1, 0.0, 0.0, 0.0]
    easy_neg = [0.0, 1.0, 0.0, 0.0, 0.0]
    hard_neg = [0.85, 0.05, 0.05, 0.0, 0.0]

    easy_score = NegativeDifficulty.score_easy(query_emb, easy_neg, positive_emb)
    hard_score = NegativeDifficulty.score_easy(query_emb, hard_neg, positive_emb)

    assert easy_score > hard_score, "Easy negatives should score lower"

    print(f"[PASS] Difficulty scoring: easy={easy_score:.3f}, hard={hard_score:.3f}")


def test_hard_negative_miner():
    """Test hard negative mining."""
    curriculum = CurriculumSchedule(total_epochs=50)
    miner = HardNegativeMiner(curriculum)

    query_emb = [1.0, 0.0, 0.0]
    positive_emb = [0.9, 0.0, 0.0]

    candidates = {
        "cand_1": [0.0, 1.0, 0.0],
        "cand_2": [0.85, 0.0, 0.0],
        "cand_3": [0.88, 0.0, 0.0],
    }

    categories = {
        "cand_1": "home",
        "cand_2": "computer",
        "cand_3": "computer",
    }

    selected_easy = miner.select_negatives(
        query_emb, positive_emb, candidates, categories,
        "computer", epoch=5, num_negatives=1
    )
    assert len(selected_easy) == 1

    selected_hard = miner.select_negatives(
        query_emb, positive_emb, candidates, categories,
        "computer", epoch=45, num_negatives=1
    )
    assert len(selected_hard) == 1
    assert selected_hard[0] in ["cand_2", "cand_3"]

    print("[PASS] Hard negative mining")


def test_curriculum_progress_tracking():
    """Test curriculum progress tracking."""
    curriculum = CurriculumSchedule(total_epochs=50)

    progress_0 = curriculum.progress(0)
    progress_25 = curriculum.progress(25)
    progress_49 = curriculum.progress(49)

    assert progress_0["difficulty"] == "EASY"
    assert progress_25["difficulty"] == "MEDIUM"
    assert progress_49["difficulty"] == "HARD"

    assert progress_0["loss_weight"] == 1.0
    assert progress_25["loss_weight"] > 1.0
    assert progress_49["loss_weight"] > progress_25["loss_weight"]

    print("[PASS] Curriculum progress tracking")


def test_custom_curriculum():
    """Test creating custom curriculum."""
    curriculum = CurriculumSchedule(total_epochs=100)
    assert curriculum.stages[0].epoch_end == 30
    assert curriculum.stages[1].epoch_end == 70
    assert curriculum.stages[2].epoch_end == 100

    print("[PASS] Custom curriculum with 100 epochs")


if __name__ == "__main__":
    test_curriculum_schedule_creation()
    test_curriculum_stage_transitions()
    test_loss_weight_progression()
    test_negative_difficulty_scoring()
    test_hard_negative_miner()
    test_curriculum_progress_tracking()
    test_custom_curriculum()

    print("\n[SUCCESS] All curriculum learning tests passed!")
