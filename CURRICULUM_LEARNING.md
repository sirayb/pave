# Curriculum Learning for Ranking

**Purpose**: Progressive negative difficulty during training to improve ranker robustness.

## Concept

Start with easy negatives (clear semantic distance), gradually introduce harder negatives (similar to query/positive) to force model to learn fine-grained discrimination.

Inspired by Curriculum Learning (Bengio et al., 2009).

## Architecture

### 3-Stage Progression

| Stage | Epochs | Difficulty | Negatives | Loss Weight | Description |
|-------|--------|-----------|-----------|-------------|------------|
| **Easy** | 0-30% | `EASY` | Random, far from query | 1.0x | Clear semantic separation |
| **Medium** | 30-70% | `MEDIUM` | Hard negatives, high similarity to query | 1.5x | Push model to discriminate close matches |
| **Hard** | 70-100% | `HARD` | Adversarial negatives, same category | 2.0x | Maximize query-candidate relevance discrimination |

### Loss Weighting

Each stage has explicit loss weight. Hard negatives carry 2x weight to force learning from harder examples.

## Components

### 1. CurriculumSchedule

Manages stage progression.

```python
curriculum = CurriculumSchedule(total_epochs=50)
difficulty = curriculum.get_difficulty(epoch=25)  # MEDIUM
loss_weight = curriculum.get_loss_weight(epoch=25)  # 1.5
```

### 2. NegativeDifficulty

Scores candidates by difficulty.

```python
# Easy negatives: far from both query and positive
score = NegativeDifficulty.score_easy(query_emb, neg_emb, pos_emb)

# Hard negatives: similar to query, different from positive
score = NegativeDifficulty.score_hard(query_emb, neg_emb, pos_emb)
```

### 3. HardNegativeMiner

Selects negatives based on curriculum stage.

```python
miner = HardNegativeMiner(curriculum)
negatives = miner.select_negatives(
    query_emb, pos_emb, 
    candidate_embeddings, 
    categories,
    epoch=25
)
```

### 4. RankerTrainer

Full training loop with curriculum and triplet loss.

```python
trainer = RankerTrainer(config)
trainer.train(triplets, embeddings, categories)
trainer.save_checkpoint(epoch)
```

## Losses

### Triplet Loss (Metric Learning)

Learns embeddings where positive examples are close and negatives far.

```
Loss = max(0, distance(anchor, positive) - distance(anchor, negative) + margin)
```

### Ranking Loss (Classification)

Learns to score positive examples high, negatives low.

```
Loss = BCE(positive_score = 1) + BCE(negative_score = 0)
```

**Combined**: `(Triplet + Ranking) x curriculum_weight`

## Usage

### Training

```python
from curriculum_learning import CurriculumSchedule, HardNegativeMiner
from ranker_training import RankerTrainer, TrainingConfig

# Setup
config = TrainingConfig(num_epochs=50, batch_size=32)
trainer = RankerTrainer(config)

# Load data
triplets = [("query_1", "pos_1", "neg_1"), ...]
embeddings = {"query_1": tensor, ...}
categories = {"pos_1": "computer", ...}

# Train
trainer.train(triplets, embeddings, categories)

# Save
trainer.save_checkpoint(50)
trainer.save_history()
```

### Inference

After training, use ranker for scoring:

```python
from ranker_v4_inference import RankerV4

ranker = RankerV4("checkpoints/ranker_epoch_50.pt")
score = ranker.score(query, candidate)
```

## Testing

```bash
cd pave
python tests_curriculum_learning.py
```

**Tests**:
- Schedule creation (3 stages)
- Stage transitions at epoch boundaries
- Loss weight progression (1.0 -> 1.5 -> 2.0)
- Difficulty scoring (hard negatives score higher)
- Hard negative mining (selects hardest candidates at late epochs)
- Progress tracking

## Metrics

Training produces:
- `triplet_loss`: Metric learning progress
- `ranking_loss`: Discrimination progress
- `curriculum_difficulty`: Current stage (EASY/MEDIUM/HARD)
- `curriculum_weight`: Loss multiplier

Saved to `checkpoints/training_history.json`.

## Implementation Details

### Difficulty Scoring

**Easy**: Distance from both query and positive
```
score = ((1 - sim(query, neg)) + (1 - sim(pos, neg))) / 2
```

**Medium**: Similarity to query, difference from positive
```
score = sim(query, neg) x (1 - sim(pos, neg))
```

**Hard**: Similarity to both (adversarial)
```
score = sim(query, neg) x sim(pos, neg) x (1.2 if same_category else 1.0)
```

### Negative Selection

Top-K by difficulty score:
1. Early epochs (EASY): Random negatives tend to score highest (far)
2. Mid epochs (MEDIUM): Similar-to-query negatives selected
3. Late epochs (HARD): Same-category high-similarity negatives selected

## Next Steps

1. Integrate with ranker training pipeline
2. Validate on WDC-PAVE benchmark (Phase 3 dataset)
3. Compare performance: curriculum vs. non-curriculum baseline
4. Measure MRR improvement at different stages

## References

- Bengio et al., "Curriculum Learning" (2009)
- Schroff et al., "FaceNet" (Triplet Loss, 2015)
- Hinton et al., "Distilling Neural Networks" (Loss weight scheduling)
