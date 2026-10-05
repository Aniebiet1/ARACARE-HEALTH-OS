# AraCare — Capacity Dashboard
### Deep Dive: Real-Time Bed, Staff, and Equipment Visibility

---

## The Problem We're Actually Solving

### Failure 1: Bed Availability Is Tribal Knowledge

Knowing whether Ward 3 has a free bed right now means someone physically walking there or calling someone who was there recently. There's no single place that answer lives, which means the answer is frequently wrong by the time it's acted on.

**Result:** an ambulance crew or a referring doctor sends a patient toward a ward that's actually full, discovered only on arrival.

### Failure 2: Capacity Problems Are Discovered, Not Anticipated

By the time an emergency department is visibly overwhelmed — no chairs, no beds, a line out the door — the problem has already arrived. Nothing upstream of that moment gave management a chance to act: call in extra staff, open an overflow area, or start diverting non-critical admissions.

**Result:** every capacity crisis is managed reactively, at the worst possible moment to be making decisions calmly.

### Failure 3: Oxygen and Equipment Status Lives in Someone's Head

Whether there are enough oxygen cylinders for the night, or whether the one working ventilator on a ward is actually working, is known by whichever staff member last checked — and that knowledge doesn't automatically transfer at shift change. A ward can run short of oxygen not because none was available in the building, but because nobody connected what Ward 3 had with what Ward 3 needed.

---

## What This Module Does

1. **Tracks beds available by ward in real time**, derived directly from the EHR's own admission/discharge events — not a separate manual count
2. **Tracks staff on duty and equipment/oxygen status**, as current as the last check-in allows
3. **Projects when a department will run out of capacity**, early enough that someone can act rather than only react
4. **Writes bed assignments back into the EHR**, so a doctor sees the bed number without leaving the patient's chart

---

## Part 1: What It Tracks

| Metric | Source | Updates | Automatic? |
| --- | --- | --- | --- |
| Beds available by ward | EHR admission/discharge events | Real-time | Yes — byproduct of the admission flow |
| Staff on duty per department | Shift roster system, or manual entry if none exists | Per shift | Depends on whether a roster system already exists |
| Oxygen cylinder levels | Manual check-in by ward staff | Per check | No — no sensor planned for v1 |
| Equipment status (ventilators, monitors) | Manual check-in by ward staff | Per check | No |

Beds are the only metric with a fully automatic source. Everything else depends on someone recording it, which is the actual constraint on how current this dashboard can be — see Part 4 and Open Questions.

---

## Part 2: Bed State Machine

```
                    ┌─────────────┐
                    │  AVAILABLE   │
                    └──────┬──────┘
                           │ admission order confirmed (from EHR)
                           ▼
                    ┌─────────────┐
                    │   RESERVED   │  ← assigned, patient not yet physically in bed
                    └──────┬──────┘
                           │ patient arrives at the bed
                           ▼
                    ┌─────────────┐
                    │   OCCUPIED   │
                    └──────┬──────┘
                           │ discharge recorded in EHR
                           ▼
                    ┌─────────────┐
                    │   CLEANING   │  ← not available until marked ready
                    └──────┬──────┘
                           │ ward staff marks bed ready
                           ▼
                    ┌─────────────┐
                    │  AVAILABLE   │
                    └─────────────┘
```

CLEANING exists as its own state deliberately — a bed with a discharged patient isn't actually usable until someone confirms it's ready, and counting it as AVAILABLE the instant a patient leaves would overstate real capacity at exactly the moment that matters most (a busy ward, high turnover).

---

## Part 3: Predictive Trend Engine

For v1, the "ED full in ~5 hours" figure is a trend projection, not a trained model — the same reasoning a bed manager already does mentally, run continuously instead of once in a while:

```
admission_rate  = admissions in the last 4 hours / 4            (patients/hour)
discharge_rate  = discharges in the last 4 hours / 4            (patients/hour)
net_rate        = admission_rate − discharge_rate               (patients/hour, can be negative)
beds_free_now   = count(beds where status = 'available')

if net_rate <= 0:
    no projected shortage — department is stable or clearing

if net_rate > 0:
    hours_to_full = beds_free_now / net_rate
```

**Worked example:** Emergency Department has 6 beds free. Over the last 4 hours: 10 admissions, 2 discharges.

```
admission_rate = 10 / 4 = 2.5/hr
discharge_rate = 2 / 4 = 0.5/hr
net_rate       = 2.5 − 0.5 = 2.0/hr
hours_to_full  = 6 / 2.0 = 3 hours
```

The dashboard would show "ED full in ~3 hours" — labelled explicitly as an estimate, since it's a straight-line extrapolation of the last 4 hours, not a forecast that accounts for day-of-week patterns or known events. It updates continuously as new admissions and discharges come in, so the estimate moves as the real trend moves rather than staying fixed.

**v2 candidate:** a model that accounts for day-of-week and seasonal patterns (malaria season surges, market-day volume), once there's enough historical data to validate it against what actually happened.

---

## Part 4: Manual Check-In Workflow

Staff, oxygen, and equipment status depend on someone recording them. The check-in should be close to zero-friction or it won't happen reliably on a busy shift:

```
WARD CHECK-IN — Ward 3, Morning Shift
───────────────────────────────────────
  Staff on duty:        [ 4 ]  nurses   [ 1 ]  doctor
  Oxygen cylinders:     [ 6 ]  full     [ 2 ]  in use
  Ventilators:          [ 2 ]  working  [ 0 ]  faulty
  Cardiac monitors:     [ 3 ]  working  [ 1 ]  faulty  → flag for maintenance

  [SUBMIT CHECK-IN]
```

A faulty-equipment flag should route into Internal Comms (Module 9) to whoever handles maintenance requests, rather than sitting inert in a form nobody revisits.

---

## Part 5: Integration Points

- **EHR (Module 4) → Capacity.** An admit order from a signed SOAP note sends a bed request here, moving a bed from AVAILABLE to RESERVED.
- **Capacity → EHR.** Once a bed is assigned, that assignment writes back into the patient's EHR record — the doctor sees the bed number without leaving the chart.
- **Capacity → Internal Comms (Module 9).** A predictive alert, or a faulty-equipment flag from check-in, routes to the relevant inbox rather than living only on a dashboard someone has to remember to check.

---

## Part 6: Data Models

```sql
-- Physical bed inventory
beds (
  id                UUID PRIMARY KEY,
  ward_id           UUID NOT NULL,
  bed_number        VARCHAR NOT NULL,
  status            ENUM('available','reserved','occupied','cleaning','out_of_service'),
  current_visit_id  UUID REFERENCES visits(id),
  updated_at        TIMESTAMP
)

-- Every bed status transition, for the trend engine and for audit
bed_status_log (
  id                UUID PRIMARY KEY,
  bed_id            UUID REFERENCES beds(id),
  from_status       VARCHAR,
  to_status         VARCHAR NOT NULL,
  visit_id          UUID REFERENCES visits(id),
  changed_at        TIMESTAMP NOT NULL
)

-- Per-shift staff count, by department
staff_shifts (
  id                UUID PRIMARY KEY,
  ward_id           UUID NOT NULL,
  shift             ENUM('morning','afternoon','night'),
  shift_date        DATE NOT NULL,
  nurses_on_duty    INTEGER,
  doctors_on_duty   INTEGER,
  source            ENUM('roster_system','manual_entry'),
  recorded_by       UUID,
  recorded_at       TIMESTAMP
)

-- Equipment and oxygen check-ins
equipment_status (
  id                UUID PRIMARY KEY,
  ward_id           UUID NOT NULL,
  equipment_type    ENUM('oxygen_cylinder','ventilator','cardiac_monitor'),
  working_count     INTEGER,
  faulty_count      INTEGER,
  checked_by        UUID,
  checked_at        TIMESTAMP NOT NULL
)

-- Stored trend projections, so the dashboard can show how an estimate has moved over time
capacity_predictions (
  id                UUID PRIMARY KEY,
  ward_id           UUID NOT NULL,
  beds_free_at_calc INTEGER,
  net_rate_per_hour DECIMAL(5,2),
  hours_to_full     DECIMAL(5,2),            -- null if net_rate <= 0
  calculated_at     TIMESTAMP NOT NULL
)
```

---

## Part 7: Nigerian Edge Cases

| Scenario | How This Module Handles It |
| --- | --- |
| **Overflow patients on mattresses, not counted beds** | Flagged as an open question (below) — the bed table assumes a fixed physical inventory, and overflow capacity needs its own representation rather than being silently invisible to the dashboard |
| **Oxygen cylinder swapped mid-shift, count goes stale fast** | Check-in is a snapshot, not continuous monitoring (no sensor in v1) — the dashboard should show "last checked at HH:MM" prominently rather than implying live accuracy it doesn't have |
| **Generator-dependent equipment during a power outage** | Equipment status doesn't currently distinguish "faulty" from "unusable because of an outage" — worth separating so a dashboard doesn't flag a ventilator as broken when it's actually just without power |
| **Small department with no formal shift roster system** | `staff_shifts.source` supports manual entry explicitly as a first-class path, not a workaround, since many departments won't have a roster system to integrate with at launch |
| **A ward that routinely runs at or near capacity as normal, not a crisis** | The trend projection should be read against that ward's normal baseline, not a single universal threshold — worth a per-ward configuration rather than one global "full" definition |

---

## Summary: Key Design Decisions

| Decision | Choice | Reason |
| --- | --- | --- |
| Bed tracking | Derived from EHR admission/discharge events | Zero additional data entry; always as current as the clinical record itself |
| Cleaning as its own state | Yes, between occupied and available | Prevents overstating real capacity the instant a patient is discharged |
| Staff/oxygen/equipment tracking | Manual check-in, not sensors (v1) | No existing sensor infrastructure to build on yet; a dashboard fed by stale manual entries is still better than no visibility at all, as long as it's labelled with its last-checked time |
| Prediction method | Linear trend projection | Matches what a bed manager already estimates mentally; doesn't require training data this hospital doesn't have |
| Prediction labelling | Explicitly an estimate, updates continuously | Avoids presenting an extrapolation as a committed forecast |
| Equipment flagging | Routes to Internal Comms | A flag that only lives on a dashboard nobody re-checks doesn't actually get equipment fixed |

---

## Open Questions / Next Steps

- [ ] Who actually enters staff/oxygen/equipment counts, and how often realistically — a dashboard fed by stale manual entries is worse than no dashboard, since people trust it
- [ ] Refresh frequency for the bed count feed vs. acceptable latency for a bed-manager decision
- [ ] Who has authority to act on a predictive alert, and what their actual options are (divert admissions, call in staff, open overflow beds)
- [ ] Whether a shift roster system already exists to pull staff-on-duty from automatically, instead of manual entry
- [ ] How overflow capacity (mattresses, corridor beds) gets represented without distorting the real bed count
- [ ] Per-ward baseline definitions of "full," since some departments run near capacity as a matter of course
