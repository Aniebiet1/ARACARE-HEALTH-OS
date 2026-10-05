# AraCare: how the modules fit together

## Shape

One deployable API per facility (modular monolith) on a local server, so the hospital keeps working without
internet. Role-based web clients talk to it over the hospital LAN. A cloud mirror (later) receives the event
log for analytics and backup.

```
Web client (per role)  --REST-->  API (FastAPI)  --SQL-->  PostgreSQL / SQLite
        ^                              |
        '------ WebSocket <-- events --'   outbox_events (transactional) -> SMS dispatcher, cloud sync, billing, pharmacy
```

## The spine

`Patient -> Visit -> Journey -> JourneyStep -> QueueTicket`, with clinical records (vitals, note, diagnoses,
orders) hanging off the visit. Every future charge, stock movement and claim attaches to the same visit.

## Events (the only coupling between modules)

| Event | Published by | Reacted to by (now) | Reacted to by (planned) |
|---|---|---|---|
| `PatientRegistered` | registration | messaging (card SMS) | |
| `VisitCheckedIn` | registration | queues (journey + triage ticket) | billing: draft invoice, deposit |
| `TriageCompleted` | ehr | queues (complete triage, open doctor ticket, set priority) | |
| `CriticalVitals` | ehr | realtime alert | on-call notification |
| `LabOrdered` | ehr (on sign) | queues (deferred LAB step) | billing, lab queue |
| `Prescribed` | ehr (on sign) | queues (deferred PHARM step) | inventory reservation, pharmacy queue |
| `NoteSigned` | ehr | queues (complete doctor step, close journey) | billing charge, HMO claim (ICD-10) |
| `JourneyClinicalCompleted` | queues | log stub | billing: invoice to pending payment, cashier ticket |

Deferred steps: departments that are not live yet (lab, pharmacy) are recorded as `deferred` journey steps so
the visit still completes cleanly and the data is ready the day those modules ship.

## Decisions worth defending

- **Human in the loop for AI.** The scribe creates `scribe_sessions` drafts. Only a clinician's sign action
  writes to `clinical_notes`, which are immutable (SHA-256 content hash; addenda only).
- **Safety rules live in code, not UI.** Allergy conflicts are a server-side hard block that needs a documented
  reason to override; critical vitals force emergency priority; sign requires an ICD-10 diagnosis.
- **No starvation in queues.** Weighted fair queuing (HIGH:NORMAL burst limit, NORMAL:FOLLOW_UP burst limit)
  plus aging, per the queue spec. Emergency always first.
- **Privacy by default.** Public TV shows ticket number and initials only; WebSocket messages carry no patient
  data; consent is append-only; every view of a chart is audited.
- **Facility-scoped IDs, global patient UUID.** Cross-facility record sharing is possible later without a rewrite.
