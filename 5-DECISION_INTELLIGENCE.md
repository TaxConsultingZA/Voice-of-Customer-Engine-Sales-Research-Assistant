# Decision Intelligence & Action Orchestration

## Decision Framework

A decision is an autonomous action triggered by customer signals, executed within governance guardrails.

### Anatomy of a Decision

```
EVENT (Customer Signal)
  ↓ [sentiment = NEGATIVE, value = $500K, channel = email]
  ↓
EVALUATION (Does this match a rule?)
  ↓ [YES: matches Rule G1 - Sentiment-Driven Escalation]
  ↓
PREDICTION (What is the likely outcome?)
  ↓ [Escalate to CSM → resolve within 24h (78% historical success)]
  ↓
GOVERNANCE CHECK (Is this within guardrails?)
  ↓ [YES: Yellow gate approved]
  ↓
DECISION (Action + Confidence)
  ↓ [escalate_to_account_team, confidence: 0.92]
  ↓
EXECUTION (Perform action)
  ↓ [Notification sent to CSM, Slack alert triggered]
  ↓
MEASUREMENT (Track outcome)
  ↓ [Monitor: was issue resolved? CSM response time? Customer satisfaction?]
```

---

## Decision Types & Routing Logic

### Type 1: Routing Decisions (95%+ automation)
**Trigger:** Issue categorization  
**Example:** Support ticket → Tier 2 specialist

**Logic:**
```
IF (issue_type == "TECHNICAL_BUG")
    AND (priority == "HIGH")
    AND (customer_segment == "ENTERPRISE")
THEN route_to = "senior_engineer"
```

**Confidence:** Generally high (>95%)  
**Automation:** Safe (only routing, no action taken)

---

### Type 2: Escalation Decisions (90%+ automation)
**Trigger:** Severity + sentiment  
**Example:** Negative + high account value → Account executive

**Logic:**
```
IF (sentiment == "NEGATIVE")
    AND (priority == "HIGH")
    AND (account_value > $500K)
THEN escalate_to = "account_executive"
    AND send_notification = "URGENT"
```

**Confidence:** High (>90%)  
**Automation:** Medium risk (escalation can generate false positives)  
**Mitigation:** Tune confidence thresholds, monitor false positive rate

---

### Type 3: Action Decisions (70%+ automation, Yellow gate)
**Trigger:** Specific trigger condition  
**Example:** Churn signal → Offer discount

**Logic:**
```
IF (churn_probability > 0.75)
    AND (account_tenure > 12_months)
    AND (account_value_ytd > $50K)
THEN action = "send_retention_offer"
    AND discount_amount = calculate_win_back_discount()
    AND require_governance_approval = true
```

**Confidence:** Medium (70-80%)  
**Automation:** Medium (requires oversight, Yellow gate)  
**Mitigation:** A/B test different discount amounts, track acceptance rate

---

### Type 4: Alert Decisions (99%+ automation)
**Trigger:** Threshold breach  
**Example:** Negative sentiment spike → Alert leadership

**Logic:**
```
IF (negative_sentiment_rate 
    > rolling_30day_mean + 3σ)
THEN action = "send_alert"
    AND recipients = ["CEO", "VP_Communications"]
    AND severity = "CRITICAL"
```

**Confidence:** Very high (99%+)  
**Automation:** Safe (only alerts, no autonomous action)

---

### Type 5: Blocking Decisions (100% automation, Red gate)
**Trigger:** Risk detection  
**Example:** PII exposure detected → Block automatic action

**Logic:**
```
IF (detected_pii_exposure == true)
    OR (detected_regulatory_keyword == true)
THEN action = "block_all_automatic_actions"
    AND escalate_to = "legal_team"
    AND log_with_severity = "CRITICAL"
```

**Confidence:** 100% (no ambiguity)  
**Automation:** Automatic kill-switch (blocks harmful actions)

---

## ML-Driven Routing Model

### Model Type: Gradient Boosted Decision Trees (XGBoost)

**Why XGBoost?**
- High accuracy on tabular data
- Explainable feature importance (vs. black-box neural nets)
- Fast inference (<100ms)
- Handles categorical features natively
- Established production patterns

### Feature Engineering

**Customer Features:**
- Account value (LTV)
- Tenure (months)
- Segment (Enterprise, Mid-market, SMB)
- Industry vertical
- Historical churn probability
- Historical NPS

**Signal Features:**
- Sentiment score
- Priority level
- Channel (email, ticket, social, etc.)
- Mention of competing product
- Urgency keywords (urgent, critical, help)
- First response time expectations (by channel)

**Contextual Features:**
- Time of day (routing → on-call coverage)
- Day of week
- Seasonal factor (fiscal year-end rush)
- Specialist availability
- Historical routing accuracy (by specialist)

### Training Approach

**Data:** 3-month rolling window (most recent 50K decisions)  
**Target:** Specialist → resolution time (faster = better)  
**Holdout Test Set:** 10% of data, not used in training

**Validation Strategy:**
- Time-series cross-validation (avoid future leakage)
- Stratified by customer segment (ensure coverage)
- Monitor accuracy by specialist (ensure fairness)

### Output & Decision Logic

```
Model Output: 
  specialist_recommendation = "senior_engineer_sarah"
  confidence_score = 0.82
  expected_resolution_time = 2.3_hours

Decision Logic:
IF confidence > 0.80:
    → Auto-route to specialist (95% of cases)
ELIF 0.60 < confidence <= 0.80:
    → Route to team + notify specialist (4% of cases)
ELSE (confidence <= 0.60):
    → Route to team lead for review (1% of cases)
```

### Continuous Learning

**Weekly Retraining:**
- Monday 5 AM: Collect resolution outcomes from last week
- Tuesday 6 AM: Retrain model on new data
- Wednesday 10 AM: Validate on hold-out test set
- Thursday 2 PM: A/B test champion vs. challenger (5% traffic)
- Friday 6 PM: If challenger wins (lower resolution time), promote to production

**Fallback Logic:**
- If model becomes unstable (accuracy drops >5%), revert to previous version
- Alert data science team for investigation
- Use rule-based routing as fallback

---

## Action Orchestration

### Supported Action Types

| Action Type | System | SLA | Example |
|------------|--------|-----|---------|
| **Email** | SendGrid | 5 min | Welcome email, nurture sequence |
| **SMS** | Twilio | 30 sec | Urgent alert, password reset |
| **In-App Notification** | Internal | Real-time | Feature announcement, warning |
| **Support Ticket** | Zendesk | 1 min | Auto-create ticket from social mention |
| **Slack Alert** | Slack API | 10 sec | Critical issue alert to channel |
| **CRM Update** | Salesforce | 2 min | Update opportunity stage, add note |
| **Workflow Trigger** | Zapier | 1 min | Trigger sequence in marketing automation |
| **Escalation** | Internal | 30 sec | Notify manager, add to queue |
| **Report Generation** | Reporting Engine | 5 min | Daily summary email to team |
| **Webhook** | Custom | 2 min | Post to external systems |

### Action Execution Guarantees

**Exactly-Once Delivery:**
- Each action tagged with unique idempotency key
- Key stored in cache (Redis) for 24 hours
- If duplicate received, skip execution (already handled)
- Prevents duplicate emails, duplicate tickets, etc.

**Transactional Semantics:**
- Action logged to database before execution
- If execution fails, retry with exponential backoff
- After 3 failed retries, move to dead-letter queue
- Manual replay capability for DLQ items

**Rate Limiting:**
- Prevent system overload: max 100 actions/second per target system
- Queue excess actions, execute on FIFO basis
- Alert ops if queue depth exceeds threshold

### Action Templating

**Template Example:**
```
Email Template: customer_negative_sentiment_escalation

Subject: [URGENT] Customer issue detected - {{customer_name}}
To: {{assigned_cse_email}}
Cc: {{account_executive_email}}

Body:
Dear {{assigned_cse_name}},

We've detected high-priority feedback from {{customer_name}} ({{customer_company}}).

Signal: {{signal_text}} (Sentiment: {{sentiment}})
Account Value: {{account_ltv}}
Response SLA: 2 hours

Recommended Action:
- Contact customer immediately
- Acknowledge issue
- Provide timeline to resolution

{{action_button_url}}

Thanks,
Voice-of-Customer Engine
```

**Dynamic Variables:**
- {{customer_name}}: Personalization
- {{sentiment}}: Contextualization
- {{action_button_url}}: One-click action tracking

---

## Decision Performance Metrics

### Decision Quality Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| **True Positive Rate** | >85% | Decisions that led to positive outcome |
| **False Positive Rate** | <10% | Unnecessary escalations/actions |
| **Precision** | >90% | Of escalations, % that needed action |
| **Recall** | >80% | Of real issues, % that were detected |

### Outcome Tracking

**For Escalation Decisions:**
- Resolution time (faster is better)
- Customer satisfaction (post-resolution survey)
- Issue repeat rate (did it happen again?)

**For Action Decisions:**
- Acceptance rate (% of offers accepted)
- Conversion rate (% that led to upsell)
- ROI (revenue generated vs. cost of action)

**For Routing Decisions:**
- Specialist accuracy (% that closed issue on first contact)
- Average handle time (faster is better)
- Customer satisfaction with specialist

### A/B Testing Framework

**Setup:**
- 5% of traffic gets new rule/model variant (challenger)
- 95% gets current rule/model (champion)
- Run for 1-2 weeks (minimum 10K decisions per variant)

**Metrics Tracked:**
- Primary: Resolution time (faster = better)
- Secondary: Customer satisfaction, false positive rate
- Guardrails: No increase in escalations to legal

**Decision Rules:**
- If challenger wins on primary metric by >5% AND no regression on secondaries → promote
- If no clear winner → extend test, increase traffic to 10%
- If challenger loses → revert to champion

---

**Decision intelligence is the bridge between understanding and action. It's where speed meets governance, where automation meets control.**
