# Model Refinement Plan: Closed Won/Lost Feedback Loop

## TLDR (For Your Boss - 30 Second Version)

**The Problem:** Our scoring model is currently based only on historical Closed Won data. To improve accuracy, we need to learn from what actually happened - both wins AND losses.

**The Solution:** Build a feedback loop that:
1. Tracks opportunities from Pipeline → Closed Won/Lost
2. Compares predicted scores vs. actual outcomes
3. Identifies patterns in high-scored opportunities that lost
4. Refines the model weights based on real results

**Why This Works:** Machine learning models improve through feedback. By analyzing which high-scored opportunities actually closed vs. which ones lost, we can identify what factors truly predict success and adjust our scoring weights accordingly.

**Timeline:** 2-3 weeks to build, then continuous improvement as more data flows through.

**Confidence Level:** High - This is standard ML practice used by every major tech company (Netflix, Amazon, etc.) for recommendation and prediction systems.

---

## Technical Summary (For Implementation)

### Overview
Implement a feedback loop system that tracks opportunities from the Open Pipeline Account Score through to Closed Won/Lost, then uses this outcome data to refine the scoring model's weights and accuracy.

### Architecture

#### Phase 1: Data Tracking & Storage
1. **Opportunity Snapshot System**
   - When Open Pipeline Account Score runs, store a snapshot of:
     - Opportunity ID
     - Calculated scores (Opportunity Score, Account Score, component scores)
     - All input factors (deal size, stage, owner, etc.)
     - Timestamp
   - Store in JSON files or lightweight database (SQLite)

2. **Outcome Tracking**
   - Weekly/monthly job that:
     - Queries Salesforce for opportunities that moved to Closed Won/Lost
     - Matches against stored snapshots
     - Records actual outcome (Won/Lost) and final deal value
     - Calculates time-to-close for won deals

#### Phase 2: Analysis & Pattern Detection
1. **Closed Won Analysis Report**
   - Compare predicted score vs. actual outcome
   - Identify:
     - High-scored opportunities that won (validates model)
     - High-scored opportunities that lost (model weaknesses)
     - Low-scored opportunities that won (model blind spots)
   - Calculate accuracy metrics:
     - Precision: % of high-scored opps that actually won
     - Recall: % of won deals that were high-scored
     - F1 Score: Balanced accuracy metric

2. **Closed Lost Analysis Report**
   - Focus on high-scored opportunities that lost
   - Identify common patterns:
     - Which component scores were misleading?
     - What factors did we over-weight?
     - What factors did we miss?
   - Example insights:
     - "Opportunities with high Upsell Score but low Win Rate Score lost 40% of the time"
     - "Deals in 'Solution Development' stage with high scores but low Product Mix lost frequently"

#### Phase 3: Model Refinement
1. **Weight Adjustment Algorithm**
   - Use gradient descent or similar optimization
   - Adjust component weights based on:
     - Which factors correlated with actual wins
     - Which factors were misleading (high score but lost)
   - Example:
     - If high "Upsell Instances" score frequently led to losses, reduce its weight from 25% to 20%
     - If "Win Rate" was highly predictive, increase from 20% to 25%

2. **Feature Engineering**
   - Add new factors based on patterns:
     - Stage-specific scoring (different weights per stage)
     - Owner performance history
     - Deal velocity (days in current stage)
     - Competitive factors (if available)

3. **A/B Testing Framework**
   - Run old model vs. new model in parallel
   - Compare accuracy over 30-60 day period
   - Only deploy new model if accuracy improves

### Implementation Details

#### Data Schema
```python
@dataclass
class OpportunitySnapshot:
    opportunity_id: str
    snapshot_date: date
    opportunity_score: float
    account_score: float
    component_scores: Dict[str, float]
    deal_size: float
    stage: str
    owner: str
    # ... other factors

@dataclass
class OpportunityOutcome:
    opportunity_id: str
    outcome: str  # "Won" or "Lost"
    close_date: date
    final_value: float
    days_to_close: int
    actual_score_at_close: float  # Re-calculated at close time
```

#### Key Scripts
1. **`snapshot_pipeline_scores.py`**
   - Runs after Open Pipeline Account Score
   - Stores snapshots of all scored opportunities

2. **`track_outcomes.py`**
   - Weekly/monthly job
   - Queries Closed Won/Lost opportunities
   - Matches against snapshots
   - Records outcomes

3. **`analyze_model_accuracy.py`**
   - Generates Closed Won/Lost analysis reports
   - Calculates precision/recall metrics
   - Identifies patterns in misclassified opportunities

4. **`refine_model_weights.py`**
   - Analyzes outcome data
   - Suggests weight adjustments
   - Generates new model configuration

5. **`closed_won_analysis_report.py`**
   - HTML dashboard showing:
     - Predicted vs. Actual outcomes
     - Accuracy metrics
     - Pattern analysis
     - Model improvement over time

6. **`closed_lost_analysis_report.py`**
   - HTML dashboard showing:
     - High-scored opportunities that lost
     - Common failure patterns
     - Recommendations for model refinement

### Technical Approach

#### Machine Learning Method
- **Supervised Learning**: Use historical outcomes (Won/Lost) as labels
- **Feature Importance**: Calculate which factors most predict success
- **Weight Optimization**: Use scikit-learn's LogisticRegression or similar to find optimal weights
- **Cross-Validation**: Test model on different time periods to avoid overfitting

#### Example Weight Refinement
```python
# Current weights
weights = {
    "speed_to_close": 0.15,
    "largest_deal": 0.20,
    "product_mix": 0.15,
    "upsell_instances": 0.25,
    "win_rate": 0.20,
    "recency": 0.05
}

# After analyzing outcomes:
# - Upsell instances correlated with losses in some cases → reduce to 0.20
# - Win rate highly predictive → increase to 0.25
# - Speed to close less predictive than expected → reduce to 0.10

# Refined weights
weights = {
    "speed_to_close": 0.10,
    "largest_deal": 0.20,
    "product_mix": 0.15,
    "upsell_instances": 0.20,  # Reduced
    "win_rate": 0.25,  # Increased
    "recency": 0.10  # Increased
}
```

### Success Metrics
- **Accuracy Improvement**: Target 5-10% improvement in precision over 6 months
- **False Positive Reduction**: Reduce high-scored opportunities that lose by 20%
- **False Negative Reduction**: Identify more low-scored opportunities that actually win
- **Model Confidence**: Increase confidence level accuracy (High/Medium/Low predictions)

### Timeline
- **Week 1-2**: Build snapshot and outcome tracking system
- **Week 3**: Build analysis reports (Closed Won/Lost)
- **Week 4**: Implement weight refinement algorithm
- **Week 5-6**: A/B test refined model
- **Ongoing**: Continuous refinement as more data accumulates

### Why This Is Technically Sound
1. **Standard ML Practice**: This is exactly how recommendation systems (Netflix, Amazon) and prediction models (Google, Facebook) improve
2. **Feedback Loop**: Every successful ML system uses feedback loops to improve
3. **Data-Driven**: Decisions based on actual outcomes, not assumptions
4. **Iterative**: Continuous improvement as more data flows through
5. **Measurable**: Clear metrics to track improvement

### Risks & Mitigations
- **Risk**: Not enough data initially (need ~100+ outcomes)
  - **Mitigation**: Start with manual analysis, automate once data accumulates
- **Risk**: Model overfitting to historical patterns
  - **Mitigation**: Use cross-validation, test on different time periods
- **Risk**: External factors not captured (market changes, competitive landscape)
  - **Mitigation**: Include recency weighting, regular model refresh

---

## Conclusion

This approach transforms the scoring model from a static analysis tool into a self-improving predictive system. By learning from actual outcomes, the model becomes more accurate over time, providing increasingly valuable insights for sales leadership and coaching.

The technical implementation is straightforward and follows industry best practices. The business value is clear: better predictions lead to better sales decisions, more effective coaching, and improved win rates.

