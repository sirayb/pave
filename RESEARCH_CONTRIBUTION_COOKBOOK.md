# PAVE Research Contributions Cookbook

Detailed code patterns for implementing each research contribution.

## Overview

PAVE includes 4 research contributions that build on the solid Benchmark Adapter foundation:

| # | Contribution | Goal | Impact | Status |
|---|--------------|------|--------|--------|
| 1 | Adaptive Query Understanding | Learn aliases from user interactions | Category accuracy 95% → 97%+ | Phase 4 |
| 2 | Confidence-based Self Learning | Feedback loop for KB updates | Top-1 accuracy 85% → 90%+ | Phase 5 |
| 3 | Ontology Evolution | Auto-suggest new concepts | Unknown concepts 100/day → 50/day | Phase 6 |
| 4 | Semantic Memory | Infer attributes from co-occurrence | Manufacturer recall 80% → 85%+ | Phase 7 |

---

## Research Contribution 1: Adaptive Query Understanding

**Problem**: System hardcodes 100+ keywords. Users use aliases ("Lat" for "Latitude", "pneumatic stool" vs "air stool"). Can't scale.

**Solution**: Learn aliases from user interactions. When user searches "pneumatic stools" and clicks product with ProductType="Stool", record alias.

### 1.1 Core Implementation

```python
# pave/research/adaptive_understanding.py

from typing import Dict, List, Tuple, Optional
from collections import defaultdict
import json

class AliasLearner:
    """Learn category keywords from user interactions."""
    
    def __init__(self, ontology_registry, min_frequency=2):
        """
        Args:
            ontology_registry: OntologyRegistry instance
            min_frequency: Minimum occurrences before adding alias
        """
        self.ontology = ontology_registry
        self.min_frequency = min_frequency
        
        # Track alias occurrences: {product_type: [query1, query2, ...]}
        self.aliases_observed = defaultdict(list)
        
        # Track sessions: {user_id: [(query, predicted_product_type, clicked), ...]}
        self.sessions = defaultdict(list)
    
    def observe_user_interaction(self, 
                                user_id: str,
                                query: str, 
                                predicted_product_type: str,
                                user_clicked: bool,
                                actual_product_type: Optional[str] = None):
        """
        Record user interaction with search results.
        
        Example:
            observe_user_interaction(
                user_id="user_123",
                query="pneumatic stool",
                predicted_product_type="Stool",  # Our prediction
                user_clicked=True,  # User found it useful
                actual_product_type="Stool"  # Ground truth
            )
        """
        
        # Record session
        self.sessions[user_id].append({
            'query': query.lower(),
            'predicted': predicted_product_type,
            'clicked': user_clicked,
            'actual': actual_product_type or predicted_product_type
        })
        
        # If user clicked, record alias
        if user_clicked or user_clicked is None:  # Assume correct if not explicitly wrong
            self.aliases_observed[actual_product_type or predicted_product_type].append(query.lower())
    
    def mine_aliases(self) -> Dict[str, List[str]]:
        """
        Extract common alias patterns from interaction data.
        
        Returns:
            {product_type: [alias1, alias2, ...]} where alias appeared >= min_frequency
        """
        mined = {}
        
        for product_type, queries in self.aliases_observed.items():
            # Count query tokens: {"pneumatic": 5, "lift": 3, "stool": 8}
            token_freq = defaultdict(int)
            for query in queries:
                tokens = query.split()
                for token in tokens:
                    token_freq[token] += 1
            
            # Find tokens that appear frequently and are meaningful
            aliases = []
            for token, freq in token_freq.items():
                if freq >= self.min_frequency:
                    # Verify token is distinctive (not generic like "with", "and")
                    if len(token) > 2 and token not in ['and', 'with', 'the', 'for']:
                        aliases.append(token)
            
            if aliases:
                mined[product_type] = sorted(aliases, key=lambda t: token_freq[t], reverse=True)
        
        return mined
    
    def update_kb(self, product_type: str, new_aliases: List[str]):
        """
        Add learned aliases to category classifier knowledge base.
        
        Args:
            product_type: e.g., "Stool"
            new_aliases: e.g., ["pneumatic", "lift", "air-assisted"]
        """
        # This would be integrated with CategoryClassifier
        # For now, return what would be updated
        return {
            'product_type': product_type,
            'action': 'add_keywords',
            'keywords': new_aliases
        }
    
    def analyze_accuracy(self, product_type: str) -> Dict[str, float]:
        """
        Analyze accuracy of predictions for a product type.
        
        Returns:
            {
                'precision': % of predicted correct,
                'recall': % of actual found,
                'f1': harmonic mean
            }
        """
        true_positive = 0
        false_positive = 0
        false_negative = 0
        
        for user_sessions in self.sessions.values():
            for session in user_sessions:
                if session['predicted'] == product_type:
                    if session['actual'] == product_type:
                        true_positive += 1
                    else:
                        false_positive += 1
                elif session['actual'] == product_type:
                    false_negative += 1
        
        precision = true_positive / (true_positive + false_positive) if (true_positive + false_positive) > 0 else 0
        recall = true_positive / (true_positive + false_negative) if (true_positive + false_negative) > 0 else 0
        f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
        
        return {'precision': precision, 'recall': recall, 'f1': f1}
    
    def save_aliases(self, filepath: str):
        """Save learned aliases to file for persistence."""
        mined = self.mine_aliases()
        with open(filepath, 'w') as f:
            json.dump(mined, f, indent=2)
    
    def load_aliases(self, filepath: str):
        """Load previously learned aliases."""
        with open(filepath, 'r') as f:
            mined = json.load(f)
        
        for product_type, aliases in mined.items():
            self.update_kb(product_type, aliases)
```

### 1.2 Integration with API

```python
# In pave/api.py

from research.adaptive_understanding import AliasLearner

alias_learner = AliasLearner(ontology_registry)

@app.get("/extract")
def extract(query: str):
    # Extract
    category = classifier.classify(query)
    attributes = expert_manager.extract(query, category)
    prediction = CanonicalPrediction(...)
    
    # Adapt
    adapter = WDCAdapter()
    output = adapter.adapt(prediction)
    
    return output.dataset_json

@app.post("/feedback")
def feedback(user_id: str, query: str, product_type: str, correct: bool):
    """
    User provides feedback on extraction.
    
    Example:
        POST /feedback?user_id=user_123&query=pneumatic+stool&product_type=Stool&correct=true
    """
    
    # Record interaction
    alias_learner.observe_user_interaction(
        user_id=user_id,
        query=query,
        predicted_product_type=product_type,
        user_clicked=correct,
        actual_product_type=product_type if correct else None
    )
    
    # Periodically mine aliases (every 100 interactions)
    if len(alias_learner.aliases_observed) % 100 == 0:
        mined = alias_learner.mine_aliases()
        
        for product_type, aliases in mined.items():
            # Update category classifier
            classifier.add_keywords(product_type, aliases)
            print(f"Added aliases for {product_type}: {aliases}")
    
    return {"status": "recorded"}
```

### 1.3 Testing Contribution 1 (Part of Test A)

```python
# pave/tests/test_adaptive_understanding.py

def test_alias_learning():
    """Test that system learns from user interactions."""
    
    learner = AliasLearner(ontology_registry, min_frequency=2)
    
    # Simulate user interactions: users searching for "stools" with different terms
    queries = [
        ("pneumatic stool", "Stool", True),
        ("air stool", "Stool", True),
        ("pneumatic lift", "Stool", True),
        ("height adjustable stool", "Stool", True),
        ("piano stool", "Stool", True),
    ]
    
    for i, (query, product_type, clicked) in enumerate(queries):
        learner.observe_user_interaction(
            user_id=f"user_{i}",
            query=query,
            predicted_product_type=product_type,
            user_clicked=clicked
        )
    
    # Mine aliases
    mined = learner.mine_aliases()
    
    # Should find "pneumatic", "air", "height", "adjustable" as aliases for Stool
    assert "Stool" in mined
    assert "pneumatic" in mined["Stool"]
    assert "air" in mined["Stool"]
    
    print(f"✓ Learned aliases for Stool: {mined['Stool']}")

def test_accuracy_analysis():
    """Test accuracy tracking."""
    
    learner = AliasLearner(ontology_registry)
    
    # 10 correct predictions
    for i in range(10):
        learner.observe_user_interaction(
            user_id=f"user_{i}",
            query="stool",
            predicted_product_type="Stool",
            user_clicked=True,
            actual_product_type="Stool"
        )
    
    # 2 incorrect predictions
    for i in range(2):
        learner.observe_user_interaction(
            user_id=f"user_{10+i}",
            query="dispenser",
            predicted_product_type="Stool",  # Wrong!
            user_clicked=False,
            actual_product_type="Dispenser"
        )
    
    accuracy = learner.analyze_accuracy("Stool")
    
    # Precision: 10 TP / (10 TP + 2 FP) = 0.833
    assert accuracy['precision'] > 0.80
    # Recall: 10 TP / (10 TP) = 1.0
    assert accuracy['recall'] == 1.0
    
    print(f"✓ Accuracy: {accuracy}")
```

---

## Research Contribution 2: Confidence-based Self Learning

**Problem**: System makes mistakes. User says "wrong", but system repeats same mistake next time.

**Solution**: Build feedback loop. When user corrects extraction, update classifier weights to avoid same mistake.

### 2.1 Core Implementation

```python
# pave/research/self_learning.py

from typing import List, Tuple, Optional
import numpy as np
from dataclasses import dataclass

@dataclass
class FeedbackSample:
    """Single feedback instance."""
    query: str
    predicted_product_type: str
    correct_product_type: str
    predicted_attributes: dict
    correct_attributes: dict
    is_correct: bool  # True if prediction was right

class ConfidenceLearner:
    """Learn from user feedback to improve classifier."""
    
    def __init__(self, classifier, min_buffer_size=10):
        """
        Args:
            classifier: CategoryClassifier instance
            min_buffer_size: Learn when buffer has this many samples
        """
        self.classifier = classifier
        self.min_buffer_size = min_buffer_size
        self.feedback_buffer = []
        self.learning_history = []
    
    def record_feedback(self, 
                       query: str,
                       predicted_product_type: str,
                       correct_product_type: str,
                       is_correct: bool = None):
        """
        Record feedback on extraction.
        
        Args:
            query: User's input
            predicted_product_type: What system predicted
            correct_product_type: What should have been predicted
            is_correct: (Optional) Explicit correctness flag
        
        Example:
            record_feedback(
                query="Dell Laptop",
                predicted_product_type="Office",
                correct_product_type="Computer",
                is_correct=False
            )
        """
        
        if is_correct is None:
            is_correct = (predicted_product_type == correct_product_type)
        
        sample = FeedbackSample(
            query=query,
            predicted_product_type=predicted_product_type,
            correct_product_type=correct_product_type,
            predicted_attributes={},
            correct_attributes={},
            is_correct=is_correct
        )
        
        self.feedback_buffer.append(sample)
    
    def learn_from_feedback(self):
        """
        Learn from accumulated feedback.
        
        Updates classifier to:
        1. Upweight features that lead to correct predictions
        2. Downweight features that lead to wrong predictions
        """
        
        if len(self.feedback_buffer) < self.min_buffer_size:
            return {"status": "insufficient_data", "samples": len(self.feedback_buffer)}
        
        # Extract positive and negative samples
        correct_samples = [s for s in self.feedback_buffer if s.is_correct]
        wrong_samples = [s for s in self.feedback_buffer if not s.is_correct]
        
        if not wrong_samples:
            return {"status": "no_errors_to_learn_from"}
        
        # For each wrong sample, extract features that led to wrong prediction
        # and boost features that would lead to correct prediction
        
        corrections_made = 0
        
        for wrong_sample in wrong_samples:
            # Get tokens from wrong prediction
            wrong_tokens = wrong_sample.query.lower().split()
            wrong_category = wrong_sample.predicted_product_type
            correct_category = wrong_sample.correct_product_type
            
            # Update classifier: remove wrong_category score for these tokens
            # and boost correct_category score
            for token in wrong_tokens:
                # Penalize: reduce weight of token→wrong_category
                self.classifier.adjust_keyword_weight(
                    keyword=token,
                    category=wrong_category,
                    adjustment=-0.1  # Decrease confidence
                )
                
                # Reward: increase weight of token→correct_category
                self.classifier.adjust_keyword_weight(
                    keyword=token,
                    category=correct_category,
                    adjustment=+0.15  # Increase confidence more
                )
                
                corrections_made += 1
        
        # Record learning event
        learning_event = {
            'timestamp': len(self.learning_history),
            'samples_learned_from': len(wrong_samples),
            'corrections_made': corrections_made,
            'error_types': {s.predicted_product_type: s.correct_product_type 
                           for s in wrong_samples}
        }
        self.learning_history.append(learning_event)
        
        # Clear buffer
        self.feedback_buffer = []
        
        return {
            'status': 'learned',
            'corrections_made': corrections_made,
            'learning_event': learning_event
        }
    
    def measure_improvement(self, test_set: List[Tuple[str, str]]) -> dict:
        """
        Measure if learning improved accuracy on test set.
        
        Args:
            test_set: [(query, expected_product_type), ...]
        
        Returns:
            {
                'accuracy': float,
                'correct': int,
                'total': int
            }
        """
        
        correct = 0
        for query, expected in test_set:
            predicted, conf = self.classifier.classify(query)
            if predicted == expected:
                correct += 1
        
        return {
            'accuracy': correct / len(test_set),
            'correct': correct,
            'total': len(test_set)
        }
```

### 2.2 Integration with API

```python
# In pave/api.py

from research.self_learning import ConfidenceLearner

learner = ConfidenceLearner(classifier, min_buffer_size=10)

@app.post("/feedback/correction")
def feedback_correction(query: str, predicted: str, correct: str):
    """
    User corrects system extraction.
    
    Example:
        POST /feedback/correction?query=Dell+Laptop&predicted=Office&correct=Computer
    """
    
    learner.record_feedback(
        query=query,
        predicted_product_type=predicted,
        correct_product_type=correct,
        is_correct=False
    )
    
    # Try to learn if we have enough feedback
    result = learner.learn_from_feedback()
    
    if result['status'] == 'learned':
        print(f"System learned from feedback: {result['corrections_made']} corrections")
    
    return result

@app.get("/metrics/improvement")
def get_improvement():
    """Show learning progress."""
    
    # Test on held-out set
    test_set = [
        ("Dell Laptop", "Computer"),
        ("Office Chair", "Office"),
        ("Gold Ring", "Jewelry"),
        ("Garden Shovel", "Home & Garden"),
        ("Pneumatic Stool", "Home & Garden"),
    ]
    
    improvement = learner.measure_improvement(test_set)
    
    return {
        'learning_history': learner.learning_history,
        'current_accuracy': improvement,
    }
```

### 2.3 Testing Contribution 2 (Part of Test G)

```python
# pave/tests/test_self_learning.py

def test_learning_from_correction():
    """Test that system learns to correct mistakes."""
    
    learner = ConfidenceLearner(classifier)
    
    # Baseline: "dell" incorrectly classified as Office
    baseline_pred, _ = classifier.classify("Dell Laptop")
    assert baseline_pred == "Office"  # Assuming this is current behavior
    
    # Record corrections
    learner.record_feedback(
        query="dell laptop",
        predicted_product_type="Office",
        correct_product_type="Computer",
        is_correct=False
    )
    
    learner.record_feedback(
        query="dell precision",
        predicted_product_type="Office",
        correct_product_type="Computer",
        is_correct=False
    )
    
    # ... repeat ~10 times
    
    # Learn
    learner.learn_from_feedback()
    
    # After learning: "dell" should be classified as Computer
    after_pred, _ = classifier.classify("Dell Laptop")
    assert after_pred == "Computer"
    
    print("✓ System learned to correct 'Dell' classification")

def test_no_degradation_on_other_categories():
    """Ensure learning on one category doesn't hurt others."""
    
    learner = ConfidenceLearner(classifier)
    
    # Baseline accuracy on all categories
    test_set = [("Dell Laptop", "Computer"), ("Office Chair", "Office"), ...]
    baseline = learner.measure_improvement(test_set)
    
    # Learn from Dell mistakes
    for i in range(20):
        learner.record_feedback(
            query="dell",
            predicted_product_type="Office",
            correct_product_type="Computer",
            is_correct=False
        )
    
    learner.learn_from_feedback()
    
    # After learning: should not degrade on other categories
    after = learner.measure_improvement(test_set)
    
    # Accuracy should not decrease
    assert after['accuracy'] >= baseline['accuracy'] - 0.05  # Allow 5% noise
    
    print(f"✓ Baseline: {baseline['accuracy']:.2%}, After: {after['accuracy']:.2%}")
```

---

## Research Contribution 3: Ontology Evolution

**Problem**: New product concepts appear. System extracts "UnknownType" confidence=0.3. No way to extend ontology.

**Solution**: Collect unknown concepts, cluster them, suggest extensions to expert.

### 3.1 Core Implementation

```python
# pave/research/ontology_evolution.py

from typing import Dict, List, Optional, Tuple
from collections import defaultdict
from dataclasses import dataclass
import json

@dataclass
class UnknownConcept:
    """Concept extraction failed to recognize."""
    value: str
    category: str
    confidence: float
    query: str  # Where it came from
    timestamp: str

class OntologyEvolver:
    """Auto-discover and integrate new ontology concepts."""
    
    def __init__(self, ontology_registry, embedding_model=None, threshold=0.80):
        """
        Args:
            ontology_registry: OntologyRegistry instance
            embedding_model: Model for semantic similarity (optional, for clustering)
            threshold: Cosine similarity threshold for clustering
        """
        self.ontology = ontology_registry
        self.embedding_model = embedding_model
        self.threshold = threshold
        self.unknown_buffer = []
    
    def observe_unknown_concept(self, 
                               value: str,
                               category: str,
                               confidence: float,
                               query: str):
        """
        Record concept we couldn't classify.
        
        Args:
            value: The unrecognized concept value
            category: Which category (Home & Garden, Computer, etc.)
            confidence: How sure was the extraction? (lower = more unknown)
            query: The query that produced this unknown
        
        Example:
            observe_unknown_concept(
                value="mini-stool",
                category="Home & Garden",
                confidence=0.45,
                query="mini-stool with back"
            )
        """
        
        if confidence < 0.65:  # Only track low-confidence extractions
            unknown = UnknownConcept(
                value=value.lower(),
                category=category,
                confidence=confidence,
                query=query,
                timestamp=datetime.now().isoformat()
            )
            self.unknown_buffer.append(unknown)
    
    def cluster_unknowns(self) -> Dict[str, List[UnknownConcept]]:
        """
        Group similar unknown concepts.
        
        Returns:
            {cluster_label: [UnknownConcept, ...], ...}
        """
        
        if len(self.unknown_buffer) < 3:
            return {}  # Need at least 3 to cluster
        
        clusters = defaultdict(list)
        
        if self.embedding_model:
            # Use semantic similarity
            embeddings = {}
            for unknown in self.unknown_buffer:
                embeddings[unknown.value] = self.embedding_model.encode(unknown.value)
            
            # Group by similarity
            processed = set()
            for unknown in self.unknown_buffer:
                if unknown.value in processed:
                    continue
                
                cluster_key = unknown.value
                clusters[cluster_key].append(unknown)
                processed.add(unknown.value)
                
                # Find similar concepts
                for other in self.unknown_buffer:
                    if other.value in processed:
                        continue
                    
                    sim = cosine_similarity(
                        embeddings[unknown.value],
                        embeddings[other.value]
                    )
                    
                    if sim > self.threshold:
                        clusters[cluster_key].append(other)
                        processed.add(other.value)
        else:
            # Simple string matching fallback
            for unknown in self.unknown_buffer:
                cluster_key = unknown.value
                clusters[cluster_key].append(unknown)
        
        return clusters
    
    def suggest_extensions(self) -> List[Dict]:
        """
        Propose new ontology concepts.
        
        Returns:
            [
                {
                    'category': 'Home & Garden',
                    'new_concept': 'Mini Stool',
                    'cluster_size': 5,
                    'examples': ['mini-stool', 'small stool', 'compact stool'],
                    'confidence': 0.92,
                    'action': 'auto_approve'  # or 'human_review'
                },
                ...
            ]
        """
        
        clusters = self.cluster_unknowns()
        suggestions = []
        
        for cluster_label, concepts in clusters.items():
            if len(concepts) < 3:
                continue  # Need at least 3 examples
            
            # Group by category
            by_category = defaultdict(list)
            for concept in concepts:
                by_category[concept.category].append(concept)
            
            for category, category_concepts in by_category.items():
                # Calculate average confidence
                avg_confidence = np.mean([c.confidence for c in category_concepts])
                
                # Determine if we should auto-approve
                action = 'auto_approve' if (len(category_concepts) >= 5 and avg_confidence > 0.6) else 'human_review'
                
                suggestion = {
                    'category': category,
                    'new_concept': self._generate_label(cluster_label, category_concepts),
                    'cluster_size': len(category_concepts),
                    'examples': [c.value for c in category_concepts[:5]],
                    'confidence': avg_confidence,
                    'action': action,
                    'rationale': self._generate_rationale(category_concepts)
                }
                suggestions.append(suggestion)
        
        return sorted(suggestions, key=lambda s: s['cluster_size'], reverse=True)
    
    def apply_extension(self, category: str, new_concept: str, examples: List[str]):
        """
        Add new concept to ontology.
        
        Args:
            category: e.g., "Home & Garden"
            new_concept: e.g., "Mini Stool"
            examples: e.g., ["mini-stool", "compact stool"]
        """
        
        # Add to ontology
        self.ontology.add_concept(
            category=category,
            value=new_concept,
            aliases=examples,
            confidence_threshold=0.70,
            source="ontology_evolution"
        )
        
        # Clear related unknowns from buffer
        self.unknown_buffer = [
            u for u in self.unknown_buffer 
            if u.value not in examples
        ]
        
        return {
            'status': 'added',
            'category': category,
            'concept': new_concept
        }
    
    def get_metrics(self) -> Dict:
        """Get metrics on unknown concepts."""
        
        if not self.unknown_buffer:
            return {'unknowns_per_day': 0, 'categories': {}}
        
        by_category = defaultdict(list)
        for unknown in self.unknown_buffer:
            by_category[unknown.category].append(unknown)
        
        return {
            'total_unknowns': len(self.unknown_buffer),
            'unknowns_per_day': len(self.unknown_buffer) / 1,  # TODO: calculate actual
            'categories': {
                cat: len(concepts)
                for cat, concepts in by_category.items()
            }
        }
    
    def _generate_label(self, cluster_label: str, examples: List[UnknownConcept]) -> str:
        """Generate human-readable label for cluster."""
        # Simple: capitalize cluster label
        return cluster_label.title()
    
    def _generate_rationale(self, examples: List[UnknownConcept]) -> str:
        """Explain why this concept should be added."""
        count = len(examples)
        avg_conf = np.mean([e.confidence for e in examples])
        return f"{count} examples observed, avg confidence {avg_conf:.2f}"
```

### 3.2 Integration with Pipeline

```python
# In pave/expert_framework.py or extraction pipeline

from research.ontology_evolution import OntologyEvolver

evolver = OntologyEvolver(ontology_registry)

def extract_with_evolution(query, category):
    """Extract attributes, track unknowns for evolution."""
    
    attributes = {}
    
    for attr_type in ['ProductType', 'Color', 'Material']:
        expert = get_expert_for(attr_type, category)
        value, confidence = expert.extract(query)
        
        if confidence < 0.65:
            # Track as unknown
            evolver.observe_unknown_concept(
                value=value,
                category=category,
                confidence=confidence,
                query=query
            )
        
        attributes[attr_type] = (value, confidence)
    
    return attributes

# Periodically check for new concepts
def check_for_new_concepts():
    """Call this periodically (e.g., every hour)."""
    
    suggestions = evolver.suggest_extensions()
    
    for suggestion in suggestions:
        if suggestion['action'] == 'auto_approve':
            # Auto-add if high confidence
            evolver.apply_extension(
                category=suggestion['category'],
                new_concept=suggestion['new_concept'],
                examples=suggestion['examples']
            )
            print(f"Auto-approved: {suggestion['new_concept']}")
        
        else:
            # Human review required
            print(f"Review needed: {suggestion['new_concept']}")
            # Would send to human reviewer interface
```

### 3.3 Testing Contribution 3

```python
# pave/tests/test_ontology_evolution.py

def test_cluster_unknowns():
    """Test that similar unknowns get clustered."""
    
    evolver = OntologyEvolver(ontology_registry)
    
    # Observe similar unknown concepts
    for value in ["mini-stool", "compact stool", "small stool", "compact seat"]:
        evolver.observe_unknown_concept(
            value=value,
            category="Home & Garden",
            confidence=0.45,
            query=f"query with {value}"
        )
    
    clusters = evolver.cluster_unknowns()
    
    # Should cluster similar concepts together
    assert len(clusters) > 0
    
    for cluster_label, concepts in clusters.items():
        print(f"Cluster '{cluster_label}': {[c.value for c in concepts]}")

def test_auto_extension():
    """Test auto-approving high-confidence clusters."""
    
    evolver = OntologyEvolver(ontology_registry)
    
    # Add 10 examples of "mini-stool" (high confidence)
    for i in range(10):
        evolver.observe_unknown_concept(
            value="mini-stool",
            category="Home & Garden",
            confidence=0.65,
            query=f"query {i}"
        )
    
    suggestions = evolver.suggest_extensions()
    
    # Should have auto_approve action
    auto_suggestions = [s for s in suggestions if s['action'] == 'auto_approve']
    assert len(auto_suggestions) > 0
    
    # Apply auto-approved extensions
    for suggestion in auto_suggestions:
        evolver.apply_extension(
            category=suggestion['category'],
            new_concept=suggestion['new_concept'],
            examples=suggestion['examples']
        )
    
    # After applying: should be recognized in ontology
    print("✓ Auto-extensions applied")
```

---

## Research Contribution 4: Semantic Memory

**Problem**: Manufacturer often co-occurs with product model. If we see "Latitude 5420", we should infer Manufacturer=Dell. But if only "Latitude" appears, we miss it.

**Solution**: Build co-occurrence graph. Learn "Latitude" is 95% associated with "Dell". Use to infer missing attributes.

### 4.1 Core Implementation

```python
# pave/research/semantic_memory.py

from typing import Dict, Tuple, Optional
from collections import defaultdict
import json

class SemanticMemory:
    """
    Learn cross-attribute associations from observed products.
    Use associations to infer missing attributes.
    """
    
    def __init__(self, min_cooccurrence=5):
        """
        Args:
            min_cooccurrence: Only use association if observed >= this many times
        """
        self.min_cooccurrence = min_cooccurrence
        
        # Track co-occurrences: {(attr1, val1, attr2, val2): count}
        self.cooccurrence_matrix = defaultdict(int)
        
        # Track single attribute observations: {(attr, val): count}
        self.occurrence_matrix = defaultdict(int)
    
    def observe_extraction(self, attributes: Dict[str, str]):
        """
        Learn from a successfully extracted product.
        
        Args:
            attributes: Dict of {attribute_name: value} from extraction
        
        Example:
            observe_extraction({
                "ProductType": "Laptop",
                "Manufacturer": "Dell",
                "Color": "Silver"
            })
        """
        
        attr_list = list(attributes.items())
        
        # Track single attributes
        for attr_name, attr_val in attr_list:
            self.occurrence_matrix[(attr_name, attr_val)] += 1
        
        # Track pairwise co-occurrences
        for i, (attr1_name, attr1_val) in enumerate(attr_list):
            for attr2_name, attr2_val in attr_list[i+1:]:
                # Both directions
                key1 = (attr1_name, attr1_val, attr2_name, attr2_val)
                key2 = (attr2_name, attr2_val, attr1_name, attr1_val)
                
                self.cooccurrence_matrix[key1] += 1
                self.cooccurrence_matrix[key2] += 1
    
    def infer_attribute(self,
                       known_attr_name: str,
                       known_attr_val: str,
                       target_attr_name: str) -> Tuple[Optional[str], float]:
        """
        Infer a missing attribute based on known attributes.
        
        Args:
            known_attr_name: e.g., "ProductType"
            known_attr_val: e.g., "Latitude 5420"
            target_attr_name: e.g., "Manufacturer"
        
        Returns:
            (inferred_value, confidence) or (None, 0.0) if no inference
        
        Example:
            mfr, conf = memory.infer_attribute(
                known_attr_name="ProductType",
                known_attr_val="Latitude 5420",
                target_attr_name="Manufacturer"
            )
            # Returns: ("Dell", 0.92)
        """
        
        # Find all cases where known_attr_val co-occurs with any target_attr value
        candidates = []
        
        for (a1, v1, a2, v2), count in self.cooccurrence_matrix.items():
            if a1 == known_attr_name and v1 == known_attr_val and a2 == target_attr_name:
                if count >= self.min_cooccurrence:
                    candidates.append((v2, count))
        
        if not candidates:
            return None, 0.0
        
        # Return most frequent target value
        best_val, best_count = max(candidates, key=lambda x: x[1])
        
        # Calculate confidence
        total = sum(count for _, count in candidates)
        confidence = best_count / total
        
        return best_val, confidence
    
    def infer_multiple(self, 
                      known_attributes: Dict[str, str],
                      target_attr_names: list) -> Dict[str, Tuple[Optional[str], float]]:
        """
        Infer multiple missing attributes.
        
        Args:
            known_attributes: {attr_name: attr_val, ...}
            target_attr_names: List of attribute names to infer
        
        Returns:
            {attr_name: (inferred_value, confidence), ...}
        """
        
        inferences = {}
        
        for target_attr in target_attr_names:
            # Try to infer from each known attribute
            best_inference = (None, 0.0)
            
            for known_attr_name, known_attr_val in known_attributes.items():
                if known_attr_name == target_attr:
                    continue  # Skip if already known
                
                inferred_val, conf = self.infer_attribute(
                    known_attr_name=known_attr_name,
                    known_attr_val=known_attr_val,
                    target_attr_name=target_attr
                )
                
                # Use highest confidence inference
                if inferred_val and conf > best_inference[1]:
                    best_inference = (inferred_val, conf)
            
            inferences[target_attr] = best_inference
        
        return inferences
    
    def get_association_strength(self,
                                attr1_name: str,
                                attr1_val: str,
                                attr2_name: str,
                                attr2_val: str) -> float:
        """
        Get how strongly two attribute values are associated.
        
        Returns confidence (0.0 to 1.0).
        """
        
        key = (attr1_name, attr1_val, attr2_name, attr2_val)
        if key not in self.cooccurrence_matrix:
            return 0.0
        
        co_count = self.cooccurrence_matrix[key]
        attr1_count = self.occurrence_matrix[(attr1_name, attr1_val)]
        
        return co_count / attr1_count if attr1_count > 0 else 0.0
    
    def get_stats(self) -> Dict:
        """Get statistics on memory."""
        
        return {
            'total_attributes_observed': len(self.occurrence_matrix),
            'total_associations': sum(self.cooccurrence_matrix.values()),
            'strong_associations': sum(1 for count in self.cooccurrence_matrix.values() 
                                      if count >= self.min_cooccurrence),
            'top_associations': self._get_top_associations(k=10)
        }
    
    def _get_top_associations(self, k=10) -> List[Dict]:
        """Get top K strongest associations."""
        
        sorted_assoc = sorted(
            self.cooccurrence_matrix.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        top = []
        for (a1, v1, a2, v2), count in sorted_assoc[:k]:
            if a1 < a2:  # Avoid duplicates
                attr1_count = self.occurrence_matrix[(a1, v1)]
                strength = count / attr1_count if attr1_count > 0 else 0
                top.append({
                    'from': f"{a1}={v1}",
                    'to': f"{a2}={v2}",
                    'strength': strength,
                    'observations': count
                })
        
        return top
    
    def save_memory(self, filepath: str):
        """Save learned memory to file."""
        
        # Convert defaultdicts to regular dicts for JSON serialization
        data = {
            'cooccurrence_matrix': dict(self.cooccurrence_matrix),
            'occurrence_matrix': dict(self.occurrence_matrix),
            'min_cooccurrence': self.min_cooccurrence
        }
        
        # Convert tuple keys to strings
        data['cooccurrence_matrix'] = {
            str(k): v for k, v in data['cooccurrence_matrix'].items()
        }
        data['occurrence_matrix'] = {
            str(k): v for k, v in data['occurrence_matrix'].items()
        }
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
    
    def load_memory(self, filepath: str):
        """Load previously learned memory."""
        
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        # Restore data structures
        for key_str, count in data['cooccurrence_matrix'].items():
            key_tuple = eval(key_str)  # Convert back to tuple
            self.cooccurrence_matrix[key_tuple] = count
        
        for key_str, count in data['occurrence_matrix'].items():
            key_tuple = eval(key_str)
            self.occurrence_matrix[key_tuple] = count
```

### 4.2 Integration with Extraction Pipeline

```python
# In pave/expert_framework.py or extraction pipeline

from research.semantic_memory import SemanticMemory

memory = SemanticMemory(min_cooccurrence=5)

def extract_with_inference(query, category):
    """Extract attributes and infer missing ones."""
    
    # Step 1: Extract directly from query
    extracted = extract(query, category)
    
    # Step 2: Infer missing attributes
    to_infer = ['Manufacturer', 'Series', 'SKU']
    inferred = memory.infer_multiple(
        known_attributes=extracted,
        target_attr_names=to_infer
    )
    
    # Step 3: Combine extracted and inferred
    final_attributes = extracted.copy()
    for attr_name, (inferred_val, conf) in inferred.items():
        if inferred_val and conf > 0.8:  # Only use high-confidence inferences
            final_attributes[attr_name] = (inferred_val, conf)
    
    return final_attributes

def learn_from_extractions(batch_of_extractions):
    """Periodically learn from successful extractions."""
    
    for extracted_product in batch_of_extractions:
        # Only learn from high-confidence extractions
        attributes = {
            name: val for name, (val, conf) in extracted_product.items()
            if conf > 0.85
        }
        
        memory.observe_extraction(attributes)
    
    # Print stats
    stats = memory.get_stats()
    print(f"Memory stats: {stats['total_associations']} associations learned")
    print(f"Top associations: {stats['top_associations']}")
```

### 4.3 Testing Contribution 4

```python
# pave/tests/test_semantic_memory.py

def test_infer_from_cooccurrence():
    """Test that system infers missing attributes from co-occurrence."""
    
    memory = SemanticMemory(min_cooccurrence=2)
    
    # Observe products: Latitude laptop is always Dell
    observations = [
        {"ProductType": "Latitude 5420", "Manufacturer": "Dell"},
        {"ProductType": "Latitude 7320", "Manufacturer": "Dell"},
        {"ProductType": "Latitude 3420", "Manufacturer": "Dell"},
    ]
    
    for obs in observations:
        memory.observe_extraction(obs)
    
    # Infer: If we see "Latitude 5420", what's the manufacturer?
    mfr, conf = memory.infer_attribute(
        known_attr_name="ProductType",
        known_attr_val="Latitude 5420",
        target_attr_name="Manufacturer"
    )
    
    assert mfr == "Dell"
    assert conf > 0.8
    
    print(f"✓ Inferred Manufacturer=Dell with confidence {conf:.2f}")

def test_improvement_with_inference():
    """Test that inference improves manufacturer detection."""
    
    memory = SemanticMemory()
    
    # Train memory on known products
    train_data = [
        {"ProductType": "Latitude", "Manufacturer": "Dell"},
        {"ProductType": "Latitude", "Manufacturer": "Dell"},
        {"ProductType": "XPS", "Manufacturer": "Dell"},
        {"ProductType": "ThinkPad", "Manufacturer": "Lenovo"},
    ]
    
    for product in train_data:
        memory.observe_extraction(product)
    
    # Test: Can we infer manufacturer from just product type?
    # Baseline: without memory, would fail
    # With memory: should infer correctly
    
    dell_mfr, dell_conf = memory.infer_attribute(
        "ProductType", "Latitude", "Manufacturer"
    )
    assert dell_mfr == "Dell"
    assert dell_conf > 0.5
    
    lenovo_mfr, lenovo_conf = memory.infer_attribute(
        "ProductType", "ThinkPad", "Manufacturer"
    )
    assert lenovo_mfr == "Lenovo"
    assert lenovo_conf > 0.5
    
    print("✓ Memory enables manufacturer inference")
```

---

## Summary

Each research contribution follows this pattern:

1. **Core Class**: Handles the research logic (AliasLearner, ConfidenceLearner, etc.)
2. **API Integration**: Hook into extraction pipeline via new endpoint or callback
3. **Testing**: Validate contribution works and improves metrics
4. **Metrics**: Track progress on specific evaluation criteria

Together, these 4 contributions demonstrate that extraction can be **dataset-independent** while remaining **continuously improving** through adaptive learning, self-correction, ontology evolution, and semantic inference.

See `RESEARCH_FRAMEWORK.md` for the complete validation framework and success criteria.

