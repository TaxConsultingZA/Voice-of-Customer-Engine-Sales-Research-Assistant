# NLP & Social Intelligence Architecture

## NLP Processing Pipeline

```
Raw Input (Text)
    ↓
[1] TOKENIZATION & NORMALIZATION
    - Language detection (detect_language)
    - Character normalization (unicode, emoji handling)
    - URL/mention extraction (preserve for context)
    ↓
[2] SENTIMENT ANALYSIS
    - Model: Fine-tuned DistilBERT (domain-specific)
    - Output: {sentiment, confidence, intensity}
    - Confidence threshold: 0.7 (below triggers manual review)
    ↓
[3] ENTITY EXTRACTION
    - Named Entity Recognition (product, competitor, person)
    - Relationship extraction (entity_A relates_to entity_B)
    - Coreference resolution (pronoun → entity mapping)
    ↓
[4] INTENT DETECTION
    - Primary intent: {complaint, praise, question, request, comparison}
    - Secondary intents: multi-label classification
    - Triggers downstream routing
    ↓
[5] TAXONOMY CLASSIFICATION
    - Hierarchical multi-label classification
    - Confidence scores for each label
    - Flags low-confidence classifications for review
    ↓
[6] ANOMALY DETECTION
    - Compare against customer historical baseline
    - Flag unusual spikes or pattern changes
    - Trigger alerts if >3σ deviation
    ↓
STRUCTURED OUTPUT (JSON)
{
  "raw_text": "...",
  "language": "en",
  "sentiment": "NEGATIVE",
  "sentiment_confidence": 0.94,
  "sentiment_intensity": 0.8,
  "entities": [...],
  "intent": "complaint",
  "taxonomy_labels": {...},
  "priority": "P1_HIGH",
  "anomaly_score": 0.15,
  "requires_manual_review": false
}
```

## Sentiment Analysis

### Model Architecture

**Base Model:** DistilBERT (66M parameters)
- 40% smaller than BERT, 2x faster inference
- 97% of BERT's performance on GLUE benchmark
- Fine-tuned on company domain data

**Fine-tuning Dataset:**
- Internal: 50K manually labeled support tickets + feedback forms
- External: 100K publicly available sentiment datasets
- Augmentation: Synthetic data for edge cases
- Domain variants: SaaS, FinTech, Healthcare (separate models)

**Training Details:**
- Learning rate: 2e-5
- Batch size: 32
- Epochs: 3
- Validation strategy: 80/10/10 train/val/test split

### Performance Targets

| Metric | Target | Status |
|--------|--------|--------|
| **Accuracy (Overall)** | >94% | ✓ Goal |
| **Precision (Negative)** | >92% | ✓ Goal (false positives costly) |
| **Recall (Negative)** | >85% | ✓ Goal (false negatives acceptable) |
| **F1-Score** | >0.88 (all classes) | ✓ Goal |
| **Latency** | <500ms per document | ✓ Goal |
| **Multi-language Accuracy** | >90% (ES, FR) | ✓ Goal |

### Training & Validation

**Quarterly Retraining Cycle:**
```
Monday: Collect corrections from users (flagged decisions)
Tuesday: Merge with base training data (stratified sampling)
Wednesday: Retrain model (checkpoint every 100 steps)
Thursday: Validate on held-out test set
Friday: A/B test old vs. new model (5% traffic)
→ If new wins, promote to production (100% traffic)
```

**Continuous Validation:**
- Monitor sentiment accuracy on daily held-out sample
- Alert if accuracy drops >2% (vs. baseline)
- Track false positive rate (overly negative classification)
- Measure sentiment correlation with churn (validation)

---

## Entity Extraction & Relationship Mapping

### Named Entity Recognition (NER)

**Entity Types:**
- **PRODUCT:** Internal products, features, integrations
- **COMPETITOR:** Competing products mentioned
- **PERSON:** Customer names, executive mentions
- **ORGANIZATION:** Customer company, partners
- **ISSUE:** Technical problems, bugs, feature requests
- **VALUE:** Pricing, usage metrics, volumes

**Model:** Fine-tuned RoBERTa-base with token classification

**Example:**
```
Input: "We tried Competitor-X but integration with Slack is easier in your product"
Output: 
- PRODUCT: ["Competitor-X", "Slack", "your product"]
- Issue: "integration"
- Relationship: PRODUCT(Competitor-X) → harder_than → PRODUCT(your product)
```

### Relationship Extraction

**Relationship Types:**
- Customer → loves/hates → Product
- Customer → compared → Competitor
- Product → causes → Issue
- Issue → blocked_by → Feature

**Implementation:** Graph-based, bidirectional relationships

---

## Social Intelligence Connectors

### Channel Integration Matrix

| Channel | Data Points | Frequency | Coverage | Cost |
|---------|------------|-----------|----------|------|
| **Support Tickets** | Full text, metadata, resolution time | Real-time | 100% (owned) | Internal |
| **Email Feedback** | Full message body, sender, reply-to | Real-time | 100% (via Zapier) | $50/mo |
| **Web Forms** | Form responses, user profile data | Real-time | 100% (native) | Internal |
| **Twitter/X** | Mentions, retweets, likes, replies | Real-time | 30-50% (coverage varies) | $100/mo (API Tier) |
| **Reddit** | Posts in subreddits, comments, upvotes | Hourly | 20-30% (limited to relevant subs) | Free (rate-limited) |
| **LinkedIn** | Company mentions, employee sentiment | Daily | 10-15% (limited content access) | $200/mo (API Tier) |
| **Glassdoor** | Employee reviews, company sentiment | Daily | 30-40% (public data only) | Web scrape (risk) |
| **G2/Capterra** | Product reviews, ratings, feature feedback | Daily | 40-60% (depends on sector) | $300/mo (data feeds) |
| **Industry News** | Company mentions, analyst reports | Daily | 5-10% (limited relevance) | $100/mo (News API) |
| **Support Forums** | Community discussions, help requests | Real-time | 50-70% (depends on community) | Custom integration |
| **Mobile App Stores** | App reviews, ratings, version feedback | Daily | 80-90% (structured data) | $50/mo (AppFigures) |
| **Slack/Teams** | Customer community posts, discussions | Real-time | 30-50% (opt-in only) | Custom connector |

### Social Media Processing

**Twitter/X Flow:**
1. Stream mentions (track keywords: company name, product name, competitors)
2. Extract sentiment, entities, intent
3. Enrich with user profile (follower count, influence)
4. Classify as public/internal concern
5. Route to comms team if >100K followers or negative + mentions

**Reddit Flow:**
1. Poll relevant subreddits (r/productname, industry subs)
2. Extract discussion threads, sentiment
3. Identify common pain points (aggregate across discussions)
4. Monthly report to product team

**Glassdoor Flow:**
1. Daily poll for new reviews
2. Extract employee sentiment (retention risk indicator)
3. Flag if review mentions customer impact or service issues
4. Escalate if >3 reviews mention same issue

---

## Sentiment Scoring Algorithm

### 5-Point Scale

| Score | Label | Definition | Action Trigger |
|-------|-------|-----------|-----------------|
| **5** | Very Positive | Enthusiastic, recommending, praising | Archive (positive feedback log) |
| **4** | Positive | Satisfied, no major issues | Archive (positive feedback log) |
| **3** | Neutral | No clear opinion, factual statement | Route to support if question |
| **2** | Negative | Dissatisfied, some issues mentioned | Escalate to team (30 min SLA) |
| **1** | Very Negative | Angry, frustrated, demanding action | Escalate to manager (15 min SLA) |

### Confidence Scoring

- 0.90-1.0: High confidence (>95% of predictions)
- 0.70-0.89: Medium confidence (4-5% of predictions)
- <0.70: Low confidence, flag for manual review (1% of predictions)

**Manual Review Queue:**
- Low-confidence predictions reviewed by CS team (SME)
- Feedback captured and used for model retraining
- Target: <50 items/day in queue (1-2 hours to review)

---

## Intent Classification

### Intent Types

| Intent | Definition | Example | Action |
|--------|-----------|---------|--------|
| **Complaint** | Customer expressing dissatisfaction | "Your product keeps crashing" | Escalate, troubleshoot |
| **Praise** | Customer expressing satisfaction | "Amazing support team!" | Log positive feedback |
| **Question** | Customer asking for information | "How do I enable SSO?" | Route to support FAQ/self-serve |
| **Request** | Customer asking for action | "Can you add feature X?" | Route to product, evaluate |
| **Comparison** | Customer comparing with competitor | "Why is X cheaper than your product?" | Route to sales, competitive analysis |
| **Bug Report** | Customer reporting technical issue | "Getting 500 error on login" | Escalate to engineering |

### Multi-Intent Handling

Text can have multiple intents. Rank by confidence:
```
Input: "Love the product but the support team is slow to respond"
Output: [Praise (0.88), Complaint (0.82), Request (0.65)]
Action: Escalate complaint (fix support SLA) but acknowledge praise
```

---

## Language Support

### Phase 1: English (en)
- Fine-tuned model on 50K English documents
- Target accuracy: >94%

### Phase 2: Spanish (es) + French (fr)
- Multilingual model: mBERT (supports 104 languages)
- Fine-tuned on 10K Spanish + 10K French documents
- Target accuracy: >90%

### Phase 3 (Future): German (de), Portuguese (pt), Japanese (ja)
- Expand fine-tuning data
- Monitor accuracy by language

---

## Quality Assurance

### Data Quality Metrics

- **Completeness:** All required fields present (target: 100%)
- **Accuracy:** Sentiment matches ground truth (target: >94%)
- **Timeliness:** Processed within 1 second of receipt (target: 99.9%)
- **Consistency:** Same input always produces same output (target: 100%)

### Model Monitoring

- **Sentiment Accuracy:** Continuous validation on hold-out sample
- **Entity F1-Score:** Track entity extraction quality
- **Intent Accuracy:** Verify intent classification against ground truth
- **Language-Specific Accuracy:** Monitor each language separately

### Continuous Improvement

- Weekly calibration: Adjust confidence thresholds based on false positive/negative rates
- Monthly retraining: Incorporate new data and user corrections
- Quarterly domain adaptation: Retrain on latest customer language/terminology

---

**NLP is the sensory layer. Its job is simple: take raw human language and convert it to machine-understandable meaning. Every decision downstream depends on accuracy here.**
