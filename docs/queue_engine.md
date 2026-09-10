# AraCare — The Queue Engine
### Deep Dive: The Brain Behind Patient Flow

---

## What the Queue Engine Actually Is

The queue engine is not just a "take a number" system.
It is the **central nervous system** of a patient's hospital visit —
a real-time state machine that knows where every patient is,
what they are waiting for, who is serving them, and what happens next.

It answers four questions at every moment:

1. **Who is next?** (Priority + fairness algorithm)
2. **Where does this patient go next?** (Journey cascade)
3. **How long will this patient wait?** (Real-time ETA)
4. **What just changed?** (Broadcasts to all screens and staff)

---

## The Real Nigerian Queue Problem We're Solving

A typical OPD morning in Nigeria:

> 200 patients arrive between 7:30–10:00 AM.
> 3 doctors. Each sees a patient every 8–12 minutes.
> Maximum realistic throughput: ~20 patients per doctor per session = 60 total.
> Remaining 140 patients wait — often 3–5 hours.
> Many walk out, go to the market, go eat, go home nearby.
> When they return, there's no record of their position. Chaos.

The queue engine fixes this. When a patient leaves the premises,
their position is preserved. The SMS tells them when to return.
The hospital is no longer a waiting room — it becomes a service
appointment system that happens to take walk-ins.

---

## Part 1: Queue Types

Every department has its own queue. They are independent but linked through the journey.

| Queue ID | Department | Reset Time | Notes |
|----------|-----------|------------|-------|
| `TRIAGE` | Nurse triage / vitals | Daily midnight | First stop for everyone |
| `OPD-GEN` | General OPD (multiple doctors) | Daily midnight | Highest volume |
| `OPD-PEDS` | Paediatrics | Daily midnight | Children u-18 |
| `OPD-ANC` | Antenatal Clinic | Daily midnight | Pregnant women only |
| `OPD-SPEC-{code}` | Specialist clinics (Cardio, Ortho, etc.) | Daily midnight | One queue per clinic |
| `LAB` | Laboratory | Daily midnight | Multiple windows |
| `PHARM` | Pharmacy | Daily midnight | One or more counters |
| `CASH` | Cashier / billing | Daily midnight | Payment collection |
| `EMRG` | Emergency | Never resets | Always open, always priority |
| `XRAY` | Radiology/Imaging | Daily midnight | If applicable |

Each queue has:
- An independent number counter (LAB-001 to LAB-999 per day)
- Its own set of active counters (service windows)
- Its own capacity limit (configurable)
- Its own priority rules (some departments apply priority, cashier is FIFO only)

---

## Part 2: The Ticket Lifecycle — Complete State Machine

Every patient in every queue is a **ticket**. A ticket has exactly one state at any moment.

```
                      ┌─────────────────────┐
                      │      PENDING         │  ← Created but not yet active
                      │  (next step waiting) │  ← e.g. Lab ticket before doc finishes
                      └──────────┬──────────┘
                                 │  journey step activated
                                 ▼
                      ┌─────────────────────┐
                 ┌───▶│      WAITING         │  ← In the queue, can be called
                 │    │  (in active queue)   │
                 │    └──────────┬──────────┘
                 │               │  staff clicks "Serve Next"
                 │               ▼
                 │    ┌─────────────────────┐
                 │    │      CALLED          │  ← Number announced, SMS sent
                 │    │  (3-min countdown)   │  ← Patient has 3 minutes to appear
                 │    └──────┬───────┬───────┘
                 │           │       │
                 │    arrived│       │ no-show timer fires
                 │           ▼       ▼
                 │    ┌──────────┐  ┌────────────────────┐
                 │    │IN_SERVICE│  │     NO_SHOW         │
                 │    │(with doc)│  │ (missed the call)   │
                 │    └────┬─────┘  └─────────┬──────────┘
                 │         │                   │
                 │         │ staff marks done  │ reply "1" / returns within 30min
                 │         ▼                   └──────────────┐
                 │    ┌──────────┐                            │ rejoin
                 │    │COMPLETED │                            └────────▶ WAITING
                 │    └──────────┘                                    (back of tier)
                 │
                 │    ┌──────────────────────────┐
                 └────│  TRANSFERRED              │  ← Moved to different queue
                      │  (admin redirect)         │     (creates new ticket there)
                      └──────────────────────────┘

         CANCELLED — Patient left hospital entirely. Manual or auto (no-show x2 + 30min)
```

### State Transition Rules

| From → To | Triggered By | Side Effect |
|-----------|-------------|-------------|
| PENDING → WAITING | Previous journey step marked COMPLETED | Patient gets SMS: "Proceed to [dept]. Queue: LAB-018" |
| WAITING → CALLED | Staff presses "Serve Next" at counter | TV display updates, SMS sent to patient, 3-min timer starts |
| CALLED → IN_SERVICE | Staff confirms "Patient Arrived" | Timer cancelled, service clock starts |
| CALLED → NO_SHOW | 3-min timer fires with no confirmation | Next patient called, no-show SMS sent |
| NO_SHOW → WAITING | Patient replies "1" to SMS or returns | Reinserted at BACK of same priority tier |
| NO_SHOW → CANCELLED | No response in 30 min after no-show | Journey marked abandoned, analytics recorded |
| IN_SERVICE → COMPLETED | Staff marks "Done" | Journey cascade fires — next step activated |
| WAITING → TRANSFERRED | Admin/doctor redirects patient | New ticket created in target queue |
| Any → CANCELLED | Patient tells staff they are leaving | Journey closed, analytics recorded |

---

## Part 3: The Priority System

### Priority Tiers

Every ticket is assigned a priority tier at check-in. Tiers determine ordering within the queue.

| Tier | Code | Who | Visual |
|------|------|-----|--------|
| 0 | `EMERGENCY` | Chest pain, seizure, unconscious, uncontrolled bleeding, child unresponsive | 🔴 Immediate |
| 1 | `HIGH` | Pregnant women (ANC), Children under 5, Elderly 65+, Visibly disabled | 🟠 High |
| 2 | `NORMAL` | Regular adult OPD visit | 🟢 Normal |
| 3 | `FOLLOW_UP` | Returning within 7 days for same complaint, results collection | 🔵 Fast-track |

### The Priority Algorithm — Weighted Fair Queuing

The naive approach is: always serve the highest priority first.
**The problem:** if P1 patients (ANC, children) stream in continuously,
a P2 patient who arrived at 7:30 AM could still be waiting at 2:00 PM.
This is called **starvation** — and it happens in real Nigerian hospitals every day.

AraCare uses **Weighted Fair Queuing** to prevent starvation:

```
HOSPITAL CONFIGURATION (admin-adjustable):
  p1_burst_limit = 3    → after every 3 P1 patients served, serve 1 P2
  p2_burst_limit = 5    → after every 5 P2 patients served, serve 1 P3 (follow-up)
  aging_threshold = 45  → after 45 minutes waiting, bump patient up one tier

get_next_patient(counter):

  STEP 1: Emergency override — always first, always
  ─────────────────────────────────────────────────
  ticket = oldest WAITING ticket with tier = EMERGENCY
  if ticket exists → serve immediately, no counters matter

  STEP 2: Check aging — promote long-waiters
  ──────────────────────────────────────────
  for each WAITING ticket in queue:
    wait_time = now - ticket.entered_waiting_at
    if wait_time > 45 min AND ticket.priority == P2:
      ticket.priority = P1  # promoted, flagged as aged
    if wait_time > 90 min AND ticket.priority == P3:
      ticket.priority = P2  # promoted, flagged as aged

  STEP 3: Weighted fair queuing
  ──────────────────────────────
  p1_served_count = counter.p1_served_since_last_p2

  if p1_served_count >= p1_burst_limit:
    ticket = oldest WAITING P2 (or aged P2) ticket
    if ticket exists:
      counter.p1_served_since_last_p2 = 0
      return ticket

  ticket = oldest WAITING P1 ticket
  if ticket exists:
    counter.p1_served_since_last_p2 += 1
    return ticket

  STEP 4: Fall through — normal FIFO for remaining tiers
  ───────────────────────────────────────────────────────
  ticket = oldest WAITING P2 ticket  → if found, serve
  ticket = oldest WAITING P3 ticket  → if found, serve

  STEP 5: Queue empty for this counter
  ─────────────────────────────────────
  counter.status = IDLE
  notify admin: "Counter idle — no patients waiting"
```

**Why aging matters for Nigeria specifically:**
An ANC patient in her third trimester may arrive at 8 AM. She is P1.
But if 40 ANC patients arrive between 8 AM and 11 AM,
a P2 adult male who arrived at 7:45 AM could be waiting 4+ hours
while P1s are continuously served. The aging mechanism guarantees
that no patient waits more than ~45 minutes without being bumped up.
The admin can tune these thresholds per hospital.

---

## Part 4: The Journey — How a Patient Crosses All Departments

### What a Journey Is

When a patient checks in, a **Journey** is created.
It is the ordered chain of queue tickets the patient will move through.
Each ticket in the chain is a **step**.

The initial steps are created at check-in. Later steps are created
dynamically as the clinical picture becomes clearer (e.g., doctor
orders a lab test — that creates a LAB ticket mid-journey).

### Journey for a Typical Nigerian Hospital Visit

```
CHECK-IN (Reception)
│
├─ STEP 1: TRIAGE queue (auto-created on check-in)
│          Status: WAITING → IN_SERVICE → COMPLETED
│          Nurse records: BP, temp, weight, pulse, SpO2
│          Duration: avg 5-8 minutes
│
├─ STEP 2: OPD queue (auto-created after TRIAGE completes)
│          Status: PENDING → WAITING → IN_SERVICE → COMPLETED
│          Doctor records consultation, makes decisions:
│          ├── prescribes medication → creates PHARM ticket
│          ├── orders lab test → creates LAB ticket
│          └── refers to specialist → creates SPEC queue ticket
│
├─ STEP 3a: LAB queue (created by doctor, if test ordered)
│           Status: PENDING → WAITING → IN_SERVICE → COMPLETED
│           Lab tech records results → results pushed to doctor's screen
│           Doctor may need to see patient again → creates new OPD ticket (FOLLOW_UP)
│
├─ STEP 3b: PHARM queue (created by doctor, if prescription issued)
│            Status: PENDING → WAITING → IN_SERVICE → COMPLETED
│            Pharmacist dispenses, records against patient and inventory
│
└─ STEP 4: CASHIER queue (auto-created when all clinical steps done)
           Aggregates all charges from consultation + lab + pharmacy
           Patient pays → journey COMPLETED
```

### The Cascade Mechanism

When a step is marked COMPLETED, the engine fires a **cascade check**:

```
on_step_completed(journey_step):

  1. Mark step as COMPLETED, record timestamp
  2. Record analytics (wait_time, service_time)
  3. Activate next PENDING steps:
     - If it's TRIAGE completing → activate OPD step
     - If it's OPD completing → activate all PENDING steps
       created by doctor during consultation (LAB, PHARM, SPEC)
  4. For each newly WAITING step:
     - Insert ticket into that department's queue
     - Calculate position and ETA
     - Send SMS to patient: "Next: [Dept]. Queue: [Number]. ETA: ~[X] min"
  5. Check if journey is complete:
     - All steps COMPLETED or CANCELLED?
     - Yes → mark journey COMPLETED, trigger final billing cascade
```

### What If the Doctor Orders Something Mid-Visit?

The doctor opens the patient's chart on their workstation during consultation.
They have buttons:
- `+ Request Lab Test` → dialog opens, select test type, confirm → LAB ticket created instantly
- `+ Issue Prescription` → pharmacy system gets the prescription → PHARM ticket created
- `+ Refer to Specialist` → select specialist/department → SPEC ticket created
- `+ Admit Patient` → triggers admission workflow (different module)

Each of these creates a new PENDING journey step.
The patient doesn't need to go back to reception. They just go to the lab.

---

## Part 5: Multi-Counter Management

### What Is a Counter?

A **counter** is any service point where a patient is physically seen:
- Doctor's consulting room ("Dr. Eze — Room 1")
- A lab window ("Lab Window 2")
- A pharmacy counter ("Pharmacy Counter A")
- A cashier position ("Cashier 3")

A queue can have multiple counters active simultaneously.
Each counter operates independently but pulls from the same queue.

### Counter States

| State | Meaning | Queue Behavior |
|-------|---------|---------------|
| `ACTIVE` | Staff is at the counter, ready to serve | Engine assigns patients to this counter |
| `PAUSED` | Staff stepped away briefly | No new patients assigned; current patient stays |
| `BREAK` | Scheduled break | No assignments until staff returns |
| `OFFLINE` | Counter closed for the day | Patients redistributed to other active counters |

### Doctor Session Management

This is particularly important for Nigeria, where doctors often:
- Arrive 30-60 minutes after the queue opens
- Go on ward rounds mid-session
- Leave early for emergencies
- Have multiple rooms/clinics in a day

```
Doctor's workstation has a session panel:

┌──────────────────────────────────────────────────────┐
│  DR. EMEKA EZE — ROOM 2          🟢 ACTIVE          │
│  Serving: OPD-043 (Mrs. Chioma)  ⏱ 8 min elapsed   │
│                                                       │
│  [MARK DONE]  [NEXT PATIENT]  [PAUSE SESSION]        │
│  [REQUEST LAB] [ISSUE PRESCRIPTION] [REFER]          │
│  [EMERGENCY OVERRIDE ⚠]                              │
│                                                       │
│  Queue: 23 waiting | Avg wait: 42 min | Served: 12   │
└──────────────────────────────────────────────────────┘
```

When doctor presses "PAUSE SESSION":
- Counter moves to PAUSED state
- Queue engine stops sending new patients to Room 2
- Other active counters absorb the new calls
- When doctor returns and clicks "RESUME", counter becomes ACTIVE again

---

## Part 6: No-Show Handling — Nigerian Edition

### Why This Is Critical Here

Nigerian patients routinely leave the hospital premises.
They go to:
- Buy food from the canteen or street hawkers
- Step outside to make calls (network is better outside)
- Run a quick errand nearby
- Rest at home (if they live close)
- Attend to their children/dependents

This is not laziness — it is rational adaptation to a system
where waits of 3–5 hours are normal. AraCare must accommodate this.

### The No-Show Flow

```
PATIENT CALLED (e.g., OPD-045):

  T+0:00  → TV display flashes OPD-045 with red border
             Text-to-speech announces: "OPD zero-four-five, please proceed to Room 2"
             SMS sent: "You are NEXT. OPD-045. Please go to Doctor's Room 2 now."

  T+0:00 to T+3:00  → Waiting for patient to appear at Room 2
                       Counter shows: "Waiting for OPD-045..."
                       Doctor can see patient has been called but not yet arrived

  T+3:00  → If patient hasn't been confirmed by doctor:
             Ticket moves to NO_SHOW state
             SMS sent: "You missed your call (OPD-045). Reply 1 to rejoin the queue.
                        You have 30 minutes before your slot is forfeited."
             Next patient in queue is called

  T+3:00 to T+33:00  → Grace window

     If patient replies "1" to SMS:
       → Ticket returns to WAITING state
       → Inserted at BACK of their priority tier
       → New estimated position calculated
       → SMS: "You've rejoined the queue. New position: OPD-051. ETA: ~18 min."

     If patient physically returns to reception within 30 min:
       → Receptionist clicks "Rejoin Queue" on their profile
       → Same effect as replying "1"

  T+33:00  → No response received
             Ticket moves to CANCELLED
             Journey step marked ABANDONED
             SMS: "Your OPD-045 slot has been cancelled. Please check in again at
                   reception if you are still at the hospital."
             Analytics: recorded as "patient walk-away"
```

### Second No-Show = End of Journey

If a patient is called, goes no-show, rejoins, is called again, and goes no-show again:
- Ticket automatically moves to CANCELLED after second no-show
- No automatic SMS retry
- Patient must physically go to reception to re-enter
- This prevents the queue from being polluted by patients who have genuinely left

---

## Part 7: Real-Time Updates — The Broadcast Layer

Every state change in the queue engine must propagate in under 500ms to:
1. **TV screens** in waiting areas
2. **Staff workstations** (doctor, nurse, lab, pharmacy tablets/PCs)
3. **Admin dashboard** (management overview)
4. (Future) **Patient's own phone** via PWA

### How It Works: WebSockets + Redis Pub/Sub

```
Queue Engine (FastAPI backend)
    │
    │  On every state change:
    │  1. Write to PostgreSQL (permanent record)
    │  2. Update Redis queue state (live working memory)
    │  3. Publish event to Redis channel
    │
    ├──▶ Redis Channel: "queue:OPD-GEN:updates"
    │         │
    │         ├──▶ WebSocket Server
    │         │         │
    │         │         ├──▶ TV Display App (subscribed to OPD channel)
    │         │         │       → Screen updates instantly
    │         │         │
    │         │         ├──▶ Doctor's Workstation (subscribed to their counter)
    │         │         │       → "Next patient: OPD-043, Mrs. Chioma, 28F"
    │         │         │         "⚠ Known allergy: Penicillin"
    │         │         │
    │         │         └──▶ Admin Dashboard (subscribed to all channels)
    │         │                 → Live queue lengths, wait times, idle counters
    │         │
    │         └──▶ SMS Dispatcher (subscribed to notification events)
                      → Queues and sends SMS via AfricasTalking/Termii
```

### What Each Screen Sees

**TV Display in OPD Waiting Room:**
```
┌──────────────────────────────────────────────────────────┐
│  🏥 GENERAL HOSPITAL — OPD             FRI 29 AUG, 2:14PM│
├─────────────────────────┬────────────────────────────────┤
│   NOW BEING SERVED      │   NEXT UP (please be ready)    │
│                         │                                │
│   OPD-043 → Room 1     │   🟠 ANC-014                   │
│   ANC-012 → Room 3     │   🟢 OPD-044                   │
│   PEDS-006 → Room 4    │   🟢 OPD-045                   │
├─────────────────────────┴────────────────────────────────┤
│  In queue: 34  │  Avg wait: ~38 min  │  Doctors active: 3│
├──────────────────────────────────────────────────────────┤
│  📢  OPD-043 — ADAEZE OKONKWO — please go to Room 1     │
└──────────────────────────────────────────────────────────┘
```

**Doctor's Workstation — Next Patient Preview:**
```
┌──────────────────────────────────────────────────────────┐
│  NEXT PATIENT: OPD-044                                   │
│  BELLO YUSUF  |  Male, 45 yrs  |  In queue: 4 min       │
│  Last visit: 12 Jun 2026 — Hypertension follow-up        │
│  ⚠ Known conditions: Hypertension                        │
│  ⚠ Current meds: Amlodipine 5mg                         │
│                                                           │
│  [CALL NOW]  [SKIP — CALL NEXT]  [FLAG EMERGENCY]       │
└──────────────────────────────────────────────────────────┘
```

The doctor sees the next patient's summary **before** calling them.
This lets them mentally prepare — especially important for chronic condition patients.

---

## Part 8: Overflow and Capacity Management

### The Overflow Problem

What if 250 patients arrive but the hospital can only serve 80 in a session?

```
CAPACITY LIMIT (set by admin per department per day):
  OPD-GEN capacity: 80 patients

When the 81st patient tries to check in for OPD-GEN:

  OPTION A (default): "Soft overflow"
    → Patient is registered and given a ticket
    → SMS: "The OPD queue is very full today. Your estimated wait is 4+ hours.
            We will send you an update when your position is clearer.
            You do not need to stay at the hospital."
    → Their ticket is created but flagged as OVERFLOW
    → Shown at bottom of queue display: "34 waiting + 12 overflow"
    → Admin sees overflow count and can decide to:
         a) Extend the session (add more doctors)
         b) Convert overflow to next-day slots

  OPTION B: "Hard cap" (if hospital enables this)
    → After capacity limit, new check-ins are told:
       "Today's OPD queue is full. Please come back tomorrow or 
        go to the nurse's station if this is urgent."
    → Emergency cases are NEVER blocked by capacity limits
```

### Session Management

Admin can manage session capacity in real time:

```
ADMIN CAPACITY DASHBOARD:

OPD General:
  Capacity: 80 | Checked in: 73 | Served: 41 | Waiting: 32 | Overflow: 7
  Active doctors: 3 | Estimated end of session: 5:20 PM
  
  [Add 20 more slots]  [Extend session 1 hour]  [Open extra room]
  [Convert overflow to tomorrow]  [Close queue]

Laboratory:
  Capacity: 120 | In queue: 44 | Served: 31
  Active windows: 2 | Avg service time: 6.3 min
  
  [Open Window 3]  [Close at 4:30 PM]
```

---

## Part 9: The Data Models

### The 6 Core Tables

```sql
-- A queue for a specific department, for a specific day
queues (
  id                UUID PRIMARY KEY,
  facility_id       UUID NOT NULL,
  department        VARCHAR NOT NULL,      -- 'OPD-GEN', 'LAB', 'PHARM', etc.
  date              DATE NOT NULL,
  status            ENUM('open','paused','closed') DEFAULT 'open',
  capacity_limit    INTEGER,               -- max tickets for the day
  current_counter   INTEGER DEFAULT 0,    -- the number generator
  opened_at         TIMESTAMP,
  closed_at         TIMESTAMP,
  UNIQUE(facility_id, department, date)
)

-- A service point where patients are physically seen
counters (
  id                UUID PRIMARY KEY,
  facility_id       UUID NOT NULL,
  queue_id          UUID REFERENCES queues(id),
  display_name      VARCHAR NOT NULL,     -- "Dr. Eze — Room 1", "Lab Window 2"
  staff_id          UUID,                -- assigned staff member
  status            ENUM('active','paused','break','offline') DEFAULT 'offline',
  current_ticket_id UUID,               -- ticket currently being served
  p1_served_since_last_p2  INTEGER DEFAULT 0,  -- for WFQ tracking
  session_started_at TIMESTAMP,
  last_active_at    TIMESTAMP
)

-- A single patient's position in a single queue
queue_tickets (
  id                UUID PRIMARY KEY,
  queue_id          UUID REFERENCES queues(id),
  journey_step_id   UUID REFERENCES journey_steps(id),
  patient_id        UUID REFERENCES patients(id),
  ticket_number     VARCHAR NOT NULL,     -- 'OPD-045'
  display_prefix    VARCHAR NOT NULL,     -- 'OPD'
  sequence_number   INTEGER NOT NULL,     -- 45
  priority_tier     ENUM('EMERGENCY','HIGH','NORMAL','FOLLOW_UP') DEFAULT 'NORMAL',
  priority_aged     BOOLEAN DEFAULT FALSE, -- was priority bumped by aging?
  status            ENUM('pending','waiting','called','in_service',
                         'completed','no_show','cancelled','transferred'),
  issued_at         TIMESTAMP NOT NULL,
  entered_waiting_at TIMESTAMP,          -- when PENDING → WAITING
  called_at         TIMESTAMP,           -- when staff pressed "Serve Next"
  confirmed_at      TIMESTAMP,           -- when staff pressed "Patient Arrived"
  completed_at      TIMESTAMP,
  no_show_count     INTEGER DEFAULT 0,
  served_by_counter_id UUID REFERENCES counters(id),
  notes             TEXT,                -- optional staff notes
  UNIQUE(queue_id, sequence_number)
)

-- A patient's complete visit journey
journeys (
  id                UUID PRIMARY KEY,
  visit_id          UUID REFERENCES visits(id),
  patient_id        UUID REFERENCES patients(id),
  facility_id       UUID NOT NULL,
  status            ENUM('in_progress','completed','abandoned'),
  started_at        TIMESTAMP,
  completed_at      TIMESTAMP
)

-- One step in a journey (one queue position in one department)
journey_steps (
  id                UUID PRIMARY KEY,
  journey_id        UUID REFERENCES journeys(id),
  step_order        INTEGER NOT NULL,     -- 1, 2, 3...
  department        VARCHAR NOT NULL,
  ticket_id         UUID REFERENCES queue_tickets(id),
  status            ENUM('pending','active','completed','skipped','abandoned'),
  created_by        ENUM('system','doctor','nurse','admin'),
  created_at        TIMESTAMP,
  activated_at      TIMESTAMP,           -- when PENDING → WAITING
  completed_at      TIMESTAMP,
  clinical_notes    TEXT                 -- e.g. "Doctor ordered CBC, LFT"
)

-- Analytics — written after each ticket completes
queue_analytics (
  id                UUID PRIMARY KEY,
  ticket_id         UUID REFERENCES queue_tickets(id),
  date              DATE NOT NULL,
  facility_id       UUID NOT NULL,
  department        VARCHAR NOT NULL,
  priority_tier     VARCHAR NOT NULL,
  counter_id        UUID,
  wait_time_minutes INTEGER,            -- entered_waiting → called
  service_time_minutes INTEGER,         -- confirmed → completed
  no_show_count     INTEGER,
  was_aged          BOOLEAN,
  hour_of_day       INTEGER             -- for heatmap analysis
)
```

### Redis Live State (Working Memory)

PostgreSQL is the source of truth. Redis is the live working memory.
Redis stores the current queue state for instant reads without DB queries.

```
Key: queue:{queue_id}:waiting
Type: Sorted Set
Score: priority_score (computed from tier + age)
Value: ticket_id

Key: queue:{queue_id}:stats
Type: Hash
Fields:
  total_waiting      → 34
  total_served_today → 41
  avg_wait_minutes   → 38
  avg_service_minutes→ 9

Key: counter:{counter_id}:state
Type: Hash
Fields:
  status             → active
  current_ticket_id  → uuid
  p1_count           → 2

Key: queue:{queue_id}:updates
Type: Pub/Sub Channel
Used for: broadcasting state changes to WebSocket subscribers
```

---

## Part 10: Offline Mode — When NEPA Strikes

### The Offline-First Guarantee

The queue engine must work without:
- Internet connection to the cloud
- Cloud sync confirmation
- External SMS delivery

```
LOCAL SERVER (on-site mini PC or server rack):
  - Runs PostgreSQL locally
  - Runs Redis locally
  - Runs the FastAPI queue engine locally
  - Runs the WebSocket server locally
  - All staff tablets/PCs connect to LOCAL server via hospital WiFi
  - TV displays connect to LOCAL server via hospital LAN

CLOUD SERVER:
  - Mirror of the local database
  - Receives sync packages from local server
  - Serves the admin analytics dashboard
  - Receives backup of all data
```

### During Outage (No Internet)

| Function | Status | How |
|----------|--------|-----|
| Check-in new patients | ✅ Works | Local PostgreSQL + Redis |
| Assign queue numbers | ✅ Works | Local counter continues |
| TV displays update | ✅ Works | Local LAN WebSocket |
| Staff workstations | ✅ Works | Local LAN connection |
| SMS notifications | ⏳ Queued | SMS queued locally, sent when network returns |
| Cloud analytics | ❌ Delayed | Sync on reconnection |
| WhatsApp notifications | ⏳ Queued | Same as SMS |

### Ticket Number Continuity During Offline

The local counter is the authoritative source for ticket numbers.
Cloud always accepts local numbers. There can never be a conflict
because each facility has its own sequence space and the local
server is the one generating numbers.

```
Local: OPD-043, OPD-044, OPD-045... (generated offline)
Cloud: receives these on sync and acknowledges
No duplicates possible — the local server owns the counter
```

### Sync on Reconnection

When internet returns:
1. Local server detects connectivity
2. Collects all events that occurred during offline period (from event log table)
3. Sends compressed batch to cloud server
4. Cloud acknowledges each event
5. Cloud updates its state to match local
6. SMS notifications in the send queue are dispatched

---

## Part 11: Analytics — What the Engine Measures

Every ticket completion writes to `queue_analytics`. This powers:

| Report | What It Shows | Used By |
|--------|--------------|---------|
| Daily throughput | Patients served per department per hour | Hospital admin |
| Wait time heatmap | Which hours have longest waits | Admin — for staffing decisions |
| Bottleneck detection | Which department is the slowest | Admin — for process improvement |
| Doctor performance | Avg patients per hour per doctor | Medical director |
| No-show rate | % of called patients who don't respond | Admin |
| Priority distribution | % of Emergency/High/Normal daily | Clinical governance |
| Overflow tracking | Days and times when capacity exceeded | Planning |

Example admin dashboard insight:
```
⚠ BOTTLENECK DETECTED
Laboratory is processing 6.3 min/patient with 2 windows.
With 44 waiting, estimated backlog clearance: 3h 8min.
Recommendation: Open Window 3, or notify doctors to space out lab orders.
[Open Lab Window 3]  [Notify Doctors]  [Dismiss]
```

---

## Summary: Key Design Decisions

| Decision | Choice | Reason |
|---------|--------|--------|
| Priority algorithm | Weighted Fair Queuing + aging | Prevents P2 starvation in high-P1 environments |
| State machine | Strict single-state per ticket | No ambiguity, clean audit trail |
| Working memory | Redis sorted sets | Sub-millisecond queue reads, real-time scores |
| Permanent storage | PostgreSQL | ACID compliance for all state transitions |
| Real-time broadcast | WebSockets via Redis Pub/Sub | <500ms propagation to all displays |
| No-show window | 3 min call + 30 min grace | Nigerian behavior — patients leave premises |
| Offline support | Local server with sync | NEPA reality — must never depend on internet |
| Journey cascade | Automatic on step completion | Patient never needs to re-queue manually |
| Counter management | Per-counter state with WFQ tracking | Multiple doctors share one queue fairly |
| Capacity overflow | Soft overflow with SMS transparency | Better than turning patients away silently |
| Number format | DEPT-NNN (e.g., OPD-045) | Short, vocal-friendly, human-readable |
| Daily reset | Midnight every day | Clean slate, analytics archived |
