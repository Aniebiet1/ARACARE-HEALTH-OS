# AraCare — AraPulse
### Internal communications: the hospital's heartbeat

> AraPulse implements [internal_communications.md](internal_communications.md): role-based routing, "seen" is
> not "acknowledged", and escalation of urgent items. This document describes what was built and where it
> deliberately differs.

---

## The Problem

- **Emergencies travel by shouting.** A nurse with a collapsing patient sends someone running to find a doctor,
  or rings phones until one answers. Nobody knows who is coming, or when, and the doctor arrives knowing nothing
  about the patient.
- **Results wait for a porter.** The lab finishes a test and the report sits on a counter until someone walks
  it to the doctor. A critical potassium can sit unread for an hour.
- **Departments can't reach each other.** A&E needs the lab to hold a crossmatch, pharmacy runs out of
  Artesunate, a ward needs a review. Today that is a personal WhatsApp group with patient names in it and no
  record.

## What AraPulse Does

1. **Pulse Codes**: anyone can page a doctor to an exact **ward and bed**. The doctor's screen takes over with
   the patient's age/sex, blood group, allergies, latest vitals (with danger flags) and diagnoses. One tap to
   respond, with an ETA. Unanswered pages widen automatically.
2. **Results come back to the doctor who asked**: when the lab sends a result, the ordering doctor gets an
   **Alert**. Critical values must be **acknowledged** and escalate if they are not.
3. **Departments talk to each other**: one **channel** per department (`#emergency`, `#laboratory`,
   `#pharmacy`, ...) that every member of staff can read and post in, an **All staff** channel, and private
   **direct messages**.
4. **Orders become messages automatically**: a signed lab request appears in `#laboratory`, a prescription in
   `#pharmacy`. Nobody types them, so every one is traceable to the action that caused it.

---

## Pulse Codes

Listed most severe first; active pages are shown in this order (unanswered before answered within a code).

| Code | Label | Use it for |
|---|---|---|
| `code_blue` | Code Blue | Cardiac or respiratory arrest |
| `obstetric` | Obstetric Emergency | Bleeding, eclampsia, a delivery going wrong |
| `trauma` | Trauma Call | Major injury arriving or on the floor |
| `rapid_response` | Rapid Response | Patient deteriorating: needs a doctor now |
| `urgent_review` | Urgent Review | Needs a doctor soon, not an arrest |

**Who gets paged** (first match wins): the named person (`target_staff_id`) → on-duty doctors of the target
department (`target_department_id`, else the ward's department) → every on-duty doctor → every active doctor.
The person raising the page is left out unless they are the only one. No doctor accounts at all → 409 with
"Call the emergency line".

**One emergency, one page.** A second page with the same code for the same patient (or the same ward + bed when
no patient is attached) while one is open does **not** create a new page: the API returns the existing page with
HTTP **200** and `duplicate: true` (a new page returns **201**, `duplicate: false`) and re-alerts its targets.

### Lifecycle

```
  raise ──▶ paging ──ack──▶ acknowledged ──arrive──▶ arrived ──resolve──▶ resolved
              │  └────────────── arrive (skips ack) ──────▲
              │                     │
              └──── cancel ─────────┴──▶ cancelled        (raiser or admin, before arrival)
```

- Only one responder: a second `ack` gets 409 "Dr. X is already responding to this page".
- `acked_at - created_at` is the **response time** (`response_seconds` in the page view; median in admin stats).
- Resolve: responder, raiser, a target, any doctor, or admin. Cancel: raiser or admin, before arrival.
- Every transition is audited and posts a short system line in the page's channel (the target department's
  channel, else the ward's department, else `#emergency` (code EMERG), else All staff).

### Escalation (sweeper, every 15 s)

| Still `paging` after | Level | Paged |
|---|---|---|
| `page_escalate_seconds` (120 s) | 1 | + every on-duty doctor |
| another 120 s | 2 | + every active doctor, including off duty |

Each escalation alerts the raiser ("not answered yet") and the new targets, re-rings everyone already paged, and
posts a critical line in the channel. Level 2 is the ceiling. The sweep uses `SELECT ... FOR UPDATE SKIP LOCKED`
and is idempotent; acknowledging stops it.

---

## Alerts

Personal, actionable items for one person. **Open = not acknowledged**; opening an alert only sets `seen_at`.

| Kind | Trigger (event) | To | Priority | Ack required |
|---|---|---|---|---|
| `lab_result` | `LabResulted`, flag normal / abnormal | ordering doctor | routine / urgent | no |
| `lab_critical` | `LabResulted`, flag critical | ordering doctor | critical | **yes** |
| `critical_vitals` | `CriticalVitals` at triage | every on-duty doctor (else every doctor) | critical | yes |
| `dispensed` | `Dispensed` | prescriber | routine | no |
| `page_escalated` | sweeper | raiser + newly paged doctors | critical | no |

- If the ordering doctor's account is deactivated, the result goes to on-duty doctors instead.
- `critical_vitals` goes to several doctors: the first acknowledgement closes everyone's copy (`acked_by` shows who).
- Items dispensed one by one for a visit fold into one unseen `dispensed` alert instead of five.
- **Critical result escalation**: unacknowledged after `critical_result_escalate_minutes` (10) → copied as a
  critical, acknowledge-required message into the doctor's department channel (or All staff) and `escalated_at`
  is set. The original stays open: escalation adds readers, it never removes the doctor's responsibility.

## Channels and messages

- `broadcast` (All staff), one `department` channel per active department (created lazily and idempotently from
  the departments table; renames follow), `direct` between two people (private: others get 404).
- Message kinds: `text`, `system`, `lab_order`, `prescription`, `page`. Priority `routine | urgent | critical`;
  critical messages require acknowledgement by default, and the sender cannot acknowledge their own message.
- **Unread**: messages after your read marker, not sent by you; a channel you've never opened counts only the last
  7 days. The badge in `/summary` counts only All staff, your own department and your direct chats; other
  departments' channels show `unread` in the list but don't nag you.

## Lab and pharmacy worklists

- Lab: `sent` (note signed) → `in_progress` (start) → `resulted` (result + flag). Results are final: a second
  result is refused (order a repeat).
- Pharmacy: prescriptions grouped per visit; `sent` → `dispensed`, one item at a time.
- Orders still on an unsigned note (`ordered`) are not on either worklist and can't be started/dispensed.

---

## Data model

```
pulse_channels      (id, facility_id, kind, key UNIQUE per facility, name, department_id, member_a, member_b,
                     created_at, last_message_at)          key: "broadcast" | "dept:<id>" | "dm:<a>:<b>"
pulse_reads         (channel_id, staff_id) PK, last_read_at
pulse_messages      (id, facility_id, channel_id, sender_id NULL=system, kind, body, priority, patient_id,
                     payload JSON, ack_required, acknowledged_by, acknowledged_at, created_at)
                     INDEX (channel_id, created_at)
pulse_alerts        (id, facility_id, recipient_id, kind, title, body, priority, ack_required, patient_id,
                     visit_id, ref_id, payload, created_at, seen_at, acked_at, acked_by, escalated_at)
                     INDEX (recipient_id, created_at), (ref_id)
pulse_pages         (id, facility_id, code, status, ward_id, bed, patient_id, note, raised_by, target_staff_id,
                     target_department_id, channel_id, responder_id, eta_minutes, escalation_level, outcome,
                     created_at, acked_at, arrived_at, resolved_at, escalated_at)  INDEX (facility_id, status)
pulse_page_targets  (page_id, staff_id) PK, level, notified_at
```

`patient_id` columns have no foreign key on purpose (as in `lab_orders`), so the mock-data reset never trips on
them. Migration: `0005_arapulse`.

## API (all under `/api`)

| | |
|---|---|
| `GET /pulse/summary` | `{unread_messages, open_alerts, critical_alerts, active_pages_for_me: [page], on_duty}` |
| `GET /pulse/codes` | Pulse Codes in severity order `[{code, label, description}]` |
| `GET /pulse/channels` · `POST /pulse/channels/direct {staff_id}` | channel list / open a DM (idempotent) |
| `GET/POST /pulse/channels/{id}/messages` · `POST .../read` · `POST /pulse/messages/{id}/ack` | messages |
| `GET /pulse/alerts?status=open\|all` · `POST /pulse/alerts/{id}/seen\|ack` | alerts |
| `GET /pulse/patients?q=` | quick patient lookup (min 2 characters, audited as a search) |
| `POST /pulse/pages` · `GET /pulse/pages?scope=active\|mine\|all` · `GET /pulse/pages/{id}` | pages |
| `POST /pulse/pages/{id}/ack {eta_minutes?}` · `/arrive` · `/resolve {outcome?}` · `/cancel {reason?}` | transitions |
| `GET /pulse/stats` (admin) | pages today, open pages, median ack time, by code (14 days), recent pages |
| `GET /lab/worklist?status=pending\|done` · `POST /lab/orders/{id}/start\|result` | lab |
| `GET /pharmacy/worklist?status=pending\|done` · `POST /pharmacy/orders/{id}/dispense` | pharmacy |
| `WS /ws/pulse?token=<JWT>` | pushes `{"event": "pulse"}` (refetch) or `{"event": "page", "id"}`; close 4401 on a bad token |

The socket joins rooms `staff:<id>` and `fac:<facility_id>`. **No patient data ever goes over the socket.**
Pushes are queued during the request and sent only after commit.

## Privacy and audit

Every page, message and alert that names a patient is audited on view (pages once per person per page, since
they are re-fetched on every push) and on create; every page transition and acknowledgement is audited.
Direct messages are visible only to the two people in them, admins included.

## Nigerian edge cases

| Scenario | Handling |
|---|---|
| Doctor in theatre, phone in a locker | Unanswered pages widen to every on-duty doctor after 2 min, then every doctor |
| Night shift with one doctor for the hospital | Department → on-duty → all doctors fallback means a page always lands somewhere |
| Nurse presses Code Blue three times in panic | One page; repeat presses re-ring the same targets |
| Doctor goes off duty without signing out | Off-duty doctors are only paged at level 2, so they're still reachable in a real emergency |
| Critical result while the doctor is busy | Must be acknowledged; after 10 min it's copied to their department so a colleague acts |
| Patients' names in personal WhatsApp groups | Department channels inside AraCare, audited, on the hospital LAN |
| Power or network blip | The client refetches on reconnect; nothing is pushed that isn't also in the database |

## Open questions

- Ward-level nursing alerts (IoT monitoring, `docs/iot_patient_monitoring.md`) will reuse `critical_vitals`.
- Escalation timeouts are global settings; per-department rules (ICU faster than GOPD) are not built yet.
- SMS fallback for pages to doctors who aren't signed in (needs the SMS gateway).
