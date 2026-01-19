# Pilot Runbook

## Purpose and Scope
The pilot runbook outlines the coordination model for ChessGuard pilot events. It is intended for operations leads, analysts, technical responders, and federation partners who must collaborate to evaluate anti-cheating alerts, protect player experience, and collect feedback that informs future rollouts.

## Roles and Responsibilities

### Pilot Lead
- Owns overall success criteria, risk register, and daily briefing cadence.
- Approves go/no-go decisions for event stages and signs off on escalations resolved during the pilot.
- Acts as the primary liaison with federation leadership and legal stakeholders.

### Operations Analysts
- Monitor incoming alerts in the analyst console and follow standard operating procedures (SOPs) to disposition each flag.
- Maintain case notes, attach corroborating evidence, and ensure timelines are documented for audit purposes.
- Provide live updates to the pilot lead during high-severity cases.

### Technical Support Engineer
- Ensures ingestion pipelines, detection services, and console deployments remain healthy.
- Investigates telemetry gaps or service degradations, coordinating with infrastructure teams for fixes.
- Manages configuration changes (thresholds, whitelists) requested by analysts or the pilot lead.

### Communications Lead
- Coordinates messaging with players, arbiters, and federation representatives before, during, and after the event.
- Tracks stakeholder questions, drafts responses, and ensures consistency with approved communication templates.
- Supports the pilot lead when preparing post-event summaries or press statements.

### Legal and Compliance Advisor
- Confirms data processing agreements, consent language, and jurisdiction-specific requirements are satisfied.
- Reviews escalations that could result in disciplinary action or public disclosure.
- Advises on retention and deletion obligations for pilot-generated data.

### Feedback Coordinator (optional role)
- Aggregates analyst, player, and technical feedback across the pilot.
- Facilitates daily retrospectives and owns the backlog of improvement actions.

## Pilot Rhythm
- **T-14 to T-1 days:** Conduct readiness checklist, confirm integrations, rehearse high-severity scenarios, and send pre-event communications.
- **Event days:** Hold pre-round standups, monitor dashboards continuously, run mid-day sync with key stakeholders, and circulate an end-of-day summary.
- **T+1 to T+7 days:** Finalize disposition of outstanding cases, deliver retrospectives, and document model or process improvements.

## SOP: Reviewing Flags

### 1. Intake and Classification
- Acknowledge the alert within five minutes of appearance in the console.
- Verify metadata: event, board, players, round, and triggering rule/model.
- Assign an initial severity rating (`low`, `medium`, `high`, `critical`) based on model score and context.

### 2. Evidence Gathering
- Review move-by-move analysis, time usage charts, and anomaly markers provided by the detection engine.
- Pull supplemental telemetry (device checks, audio/video clips, arbiter notes) if the alert indicates potential corroborating evidence.
- Confirm data completeness by checking for ingestion gaps or system issues; coordinate with technical support if inconsistencies appear.

### 3. Investigation and Collaboration
- Compare the flagged behavior against historical baselines for the player and peer cohort.
- Request arbiter input when on-site observations are available.
- Document hypotheses, supporting facts, and open questions directly in the case record.

### 4. Determination
- Select an outcome (`clear`, `monitor`, `escalate`) based on weight of evidence and policy thresholds.
- For `monitor` outcomes, define specific conditions (e.g., next 3 rounds, additional device checks) and set reminders.
- For `escalate` outcomes, immediately notify the pilot lead and initiate the relevant escalation path.

### 5. Documentation and Closure
- Complete structured fields: summary, evidence references, contributors, and recommended follow-up.
- Attach any exported analysis artifacts and ensure time stamps are correct.
- Close the case in the console and verify that the audit log reflects the final status.

## Escalation Paths

| Severity | Trigger Examples | Notification Window | Primary Owner | Escalation Path |
| --- | --- | --- | --- | --- |
| **Low** | Minor statistical anomaly, no corroborating evidence | Within shift | Operations Analyst | Log in daily summary; no external notification |
| **Medium** | Repeated anomalies, moderate risk indicators | 30 minutes | Operations Analyst | Inform Pilot Lead; coordinate enhanced monitoring |
| **High** | Strong statistical evidence, conflicting telemetry, or arbiter concern | 15 minutes | Pilot Lead | Convene response huddle (Pilot Lead, Analyst, Technical Support, Legal); determine interim action |
| **Critical** | Confirmed cheating evidence or imminent competitive impact | Immediate (5 minutes) | Pilot Lead | Activate full incident response: notify federation duty officer, suspend player participation per regulations, involve Legal & Communications |

**Escalation Mechanics**
1. Triggering analyst pages the Pilot Lead via agreed channel (e.g., PagerDuty, secure messaging).
2. Pilot Lead acknowledges and opens a virtual war room with required stakeholders.
3. Legal advisor determines if external notification obligations are triggered.
4. Communications lead prepares templated statements (see `docs/comms_templates/`).
5. Pilot Lead documents the escalation in the incident tracker and schedules follow-up review.

## Feedback Capture and Continuous Improvement
- **Daily Debrief:** 15-minute session capturing what went well, issues, and action items. Record findings in the feedback tracker.
- **Player and Arbiter Feedback:** Use post-round surveys or direct outreach to capture sentiment about checks and interactions; log results with timestamps.
- **Model Performance Review:** Analysts flag false positives/negatives; technical support updates the model calibration backlog.
- **Process Retrospective:** Within seven days post-event, hold a 60-minute retrospective covering tooling, communication, and policy gaps. Ensure outcomes feed into the post-event checklist.
- **Knowledge Base Updates:** Publish improvements, clarified SOPs, and resolved questions to the shared knowledge repository for future pilots.

## Document Control
- Store the latest signed-off runbook version in the central knowledge base.
- Any updates during the pilot must be approved by the Pilot Lead and communicated to all stakeholders.
