# AraCare — The Billing Engine
### Deep Dive: From First Charge to Final Receipt

---

## The Problem We're Actually Solving

Nigerian hospital billing fails in four specific places.
Understanding these is what makes the engine design make sense.

### Failure 1: Unbilled Services (The Biggest One)
A patient sees the doctor, who orders a malaria test and prescribes
Artemether-Lumefantrine. The lab runs the test. The pharmacist dispenses
the drugs. But the cashier only has a handwritten slip from the doctor.
The lab charge was never communicated. The exact drug quantity was guessed.

**Result:** Hospital provides ₦4,500 worth of services.
Cashier collects ₦1,200. Nobody knows the difference.

### Failure 2: Patients Walk Out
In the current system, there is nothing between "you are discharged" and the exit door.
A patient who has received consultation + lab + drugs can simply walk past the cashier.
There is no electronic gate, no flag, no alert. The cashier finds out later when counting.

**Result:** 5–15% of daily revenue evaporates. In a 200-patient/day hospital,
that is ₦50,000–₦150,000 per day, every day.

### Failure 3: HMO Claim Rejection
HMO patients are meant to pay nothing (or a small co-pay). But if the hospital:
- Uses the wrong tariff code
- Doesn't have a pre-authorization code for a procedure
- Submits the claim after the HMO's deadline
- Has incomplete clinical documentation

The HMO rejects the claim. The hospital ate the cost of care with no reimbursement.

### Failure 4: Internal Fraud
Cashiers manually collect payments. Cash is cash.
A cashier can collect ₦5,000 from a patient, enter ₦3,000 in the book,
pocket ₦2,000. With paper receipts and no real-time reconciliation,
this is nearly impossible to detect.

---

## What the Billing Engine Does

AraCare's billing engine addresses all four failures:

1. **Every service automatically creates a charge** — no human entry
2. **The cashier is the last gate in the Journey** — payment is structurally required
3. **HMO claims are auto-generated** with correct codes, pre-auth tracking, and deadline alerts
4. **Every transaction is digital and audited** — cashier can't take money without a record

---

## Part 1: Payment Tracks — Not All Patients Pay the Same Way

Before an invoice is created, AraCare assigns the patient to a **payment track**.
This determines how their bill is calculated, who pays, and how.

```
PAYMENT TRACK DECISION at Check-in:

  Does patient have verified HMO/NHIA card?
  ├── YES → HMO Track (Section 3)
  └── NO
      ├── Is patient a hospital staff member?
      │   ├── YES → Staff Track (discounted)
      │   └── NO
      │       ├── Is this service government-subsidized?
      │       │   (e.g., ANC, immunization, under-5 care in govt hospitals)
      │       │   ├── YES → Government Subsidy Track (zero or reduced cost)
      │       │   └── NO
      │       │       ├── Has admin approved a waiver/charity?
      │       │       │   ├── YES → Waiver Track
      │       │       │   └── NO → Out-of-Pocket Track (most common)
```

| Track | Who | Pricing Used | Who Pays | Invoice Behavior |
|-------|-----|-------------|---------|-----------------|
| `OUT_OF_POCKET` | Uninsured patients (~60–70% of Nigerian patients) | Hospital standard fee schedule | Patient pays 100% | Full invoice, payment at cashier |
| `HMO` | NHIA/HMO enrollees | HMO-specific tariff (usually lower) | HMO pays most, patient pays co-pay | Invoice split: co-pay now, claim later |
| `STAFF` | Hospital employees and dependants | Discounted rate (configurable) | Staff salary deduction or direct payment | Discounted invoice |
| `GOVERNMENT` | Services covered by government programs (BHCPF, free maternal, free immunization) | Zero or subsidized | Government fund | Reduced/zero patient bill, facility claims from government |
| `WAIVER` | Charity/hardship cases — admin-approved | Partial or full waiver | Hospital absorbs cost | Discounted/voided invoice with audit trail |

---

## Part 2: The Invoice Lifecycle

Every visit produces exactly **one invoice**. It goes through these states:

```
DRAFT
  │  Created automatically when patient checks in
  │  No charges yet — just the container
  │
  ▼
ACCUMULATING
  │  Charges flow in automatically as services are rendered
  │  (consultation → lab → pharmacy → procedures)
  │  Invoice is visible to cashier in real-time
  │  Patient can view their running total (optional)
  │
  ▼
PENDING_PAYMENT
  │  All clinical journey steps are COMPLETED
  │  System calculates final total
  │  Applies any deposit already paid
  │  Shows outstanding balance to cashier
  │  Cashier ticket created in queue (last journey step)
  │
  ▼
  ├── PARTIALLY_PAID → Patient paid some but not all (hospital allows installment)
  │       → Outstanding balance flagged on patient account
  │       → Required to settle before next non-emergency visit
  │
  ├── PAID → Full payment received → receipt issued → journey complete
  │
  ├── HMO_PENDING → Co-pay collected from patient, HMO claim submitted
  │       → Invoice stays open until HMO pays or rejects
  │       → On HMO payment → PAID
  │       → On HMO rejection → DISPUTED (handled separately)
  │
  ├── WAIVED → Admin has approved full or partial waiver
  │       → Audit record created with reason and approver
  │
  └── CANCELLED → Visit cancelled before any services rendered
                  (patient left before seeing doctor)
```

---

## Part 3: Automatic Charge Creation — The Core Engine

This is the most important architectural decision.

**Old way:** Patient collects paper slips from doctor, lab, pharmacy.
Brings them to cashier. Cashier manually adds up charges from paper.
Errors everywhere. Services missed. Fraud easy.

**AraCare way:** Every clinical action in the system automatically creates
a charge line on the invoice. The cashier sees everything in real-time.
They collect money — they don't calculate it.

### How Each Department Creates Charges

```
DEPARTMENT          TRIGGER                     CHARGE CREATED
────────────────────────────────────────────────────────────────
Reception           Patient checks in           Registration/consultation fee
                    (visit type determines fee)

Triage              Nurse marks triage done     Triage fee (if applicable,
                                                usually bundled with consult)

OPD Doctor          Marks consultation done     Consultation fee
                    (visit type: new/follow-up  (fee differs based on visit type)
                     determines price tier)

OPD Doctor          Orders lab test             Lab test fee (from lab price list)
                    (clicks "+ Request Lab")

OPD Doctor          Issues prescription         Drug charges NOT created here yet
                    (clicks "+ Prescribe")      (only when pharmacy dispenses)

Laboratory          Marks test as processed     Lab processing charge confirmed
                    and result ready            (if different from order charge)

Pharmacy            Marks prescription as       Drug charges created:
                    dispensed                   (quantity × unit price per drug)
                                                Consumables (syringes, etc.)
                                                if applicable

Procedure nurse     Records procedure done      Procedure fee
                    (injection, dressing,       (from procedure price list)
                     IV insertion, etc.)

Radiology           Marks imaging done          Imaging fee

Admission clerk     Records bed assignment      Daily bed/ward fee
                    (if inpatient)
```

### The Charge Line Item

Every charge is a line item on the invoice:

```
Example invoice for Mrs. Chioma Okonkwo — Visit 29 Aug 2026:

LINE  DEPT       SERVICE                    QTY   UNIT PRICE   TOTAL
───────────────────────────────────────────────────────────────────────
1     Reception  Consultation (New Visit)    1     ₦1,500      ₦1,500
2     OPD        Doctor consultation fee     1     ₦2,500      ₦2,500
3     Lab        Malaria RDT                 1     ₦800        ₦800
4     Lab        FBC (Full Blood Count)      1     ₦1,500      ₦1,500
5     Pharmacy   Artemether-Lumefantrine     1     ₦1,200      ₦1,200
6     Pharmacy   Paracetamol 500mg x12       1     ₦350        ₦350
───────────────────────────────────────────────────────────────────────
                                SUBTOTAL                       ₦7,850
                                Deposit paid at check-in      -₦2,000
                                BALANCE DUE                    ₦5,850
```

The cashier sees this. The patient sees this. Nothing is hidden.
Nothing was manually entered by the cashier.

---

## Part 4: The Deposit Model — Leakage Prevention

This is the most effective tool against revenue leakage.

### How It Works

At check-in, the receptionist collects a **refundable deposit** from the patient.

```
DEPOSIT LOGIC at Check-in:

  Visit type = Emergency → No deposit required (care first, billing after)
  Visit type = HMO → No deposit required (HMO covers it, co-pay collected at end)
  Visit type = Government subsidized → No deposit

  Visit type = Out-of-pocket OPD (new) → Collect ₦2,000 deposit
  Visit type = Out-of-pocket OPD (follow-up) → Collect ₦1,000 deposit
  Visit type = Admission/inpatient → Collect ₦10,000–₦50,000 deposit
  (all amounts are configurable by hospital admin)
```

**What happens to the deposit:**
- Logged as a payment against the invoice (partial payment)
- Held until visit completes
- At cashier: deducted from final bill automatically
- If bill < deposit: patient gets a refund (cash back or credit to their account)
- If bill > deposit: patient pays the difference

**Why this fixes leakage:**
The patient has already paid something. They are financially anchored.
Psychologically, people who have paid a deposit are far more likely
to complete payment than those who owe nothing yet.
Also — if they walk out, the hospital keeps the deposit as partial recovery.

**Configurable thresholds:**
Admin can set deposit amounts per visit type. High-risk visit types
(admission, surgery) have higher deposits. Follow-ups may have none.

---

## Part 5: The HMO Billing Track

### Verification at Check-in

When a patient presents an HMO card:

```
Receptionist scans or types HMO ID number

System checks:
  1. Is this HMO provider in our accredited list?
  2. Is this enrollee's card active (not expired)?
  3. Is this patient registered on our facility's panel? (capitation model)
  4. Does this visit type require pre-authorization from the HMO?

RESULT A: All clear → patient on HMO track, proceed
RESULT B: Card expired → patient informed, given option to pay out-of-pocket
RESULT C: Pre-authorization needed → staff calls HMO, records auth code
RESULT D: Provider not accredited → patient pays out-of-pocket
```

**HMO verification in Phase 1:** Manual check via phone call + entering details.
**HMO verification in Phase 2:** API integration with major HMO portals (Hygeia, Reliance, Total Health, etc.)

### HMO Tariff vs Standard Tariff

Every HMO has a negotiated price list (tariff schedule) with the hospital.
These are usually lower than the standard rates.

```
SERVICE                STANDARD PRICE   HYGEIA TARIFF   RELIANCE TARIFF
───────────────────────────────────────────────────────────────────────
Consultation (GP)      ₦2,500           ₦1,800          ₦2,000
Malaria RDT            ₦800             ₦600            ₦700
FBC                    ₦1,500           ₦1,200          ₦1,100
Artemether 80mg tabs   ₦1,200           ₦900            ₦1,000
```

AraCare stores a separate tariff schedule per HMO. When an HMO patient
receives a service, the HMO tariff price is used — not the standard price.

### The HMO Invoice Split

An HMO patient's invoice has two parts:
1. **Patient responsibility** — co-pay (if any) + services not covered by the plan
2. **HMO responsibility** — what the HMO will pay the hospital for

```
Mrs. Aisha Bello — HMO: Hygeia — Visit 29 Aug 2026

LINE  SERVICE              HMO TARIFF   HMO COVERS   PATIENT PAYS
───────────────────────────────────────────────────────────────────
1     Consultation         ₦1,800       ₦1,800       ₦0
2     Malaria RDT          ₦600         ₦600         ₦0
3     FBC                  ₦1,200       ₦1,200       ₦0
4     Artemether tabs      ₦900         ₦900         ₦0
5     Vitamins (not covered) ₦1,500      ₦0          ₦1,500 ← out-of-plan
───────────────────────────────────────────────────────────────────
       TOTAL               ₦6,000       ₦4,500       ₦1,500

Patient pays ₦1,500 at cashier today.
Hospital submits claim to Hygeia for ₦4,500.
```

### HMO Claim Submission

After the patient's visit:

```
CLAIM LIFECYCLE:
  1. DRAFT — auto-generated from invoice when visit completes
             Contains: patient ID, HMO ID, ICD-10 diagnosis codes,
             service codes, dates, tariff amounts, pre-auth codes
  
  2. INTERNAL REVIEW — billing officer reviews before submission
             Checks: all codes correct? pre-auth attached?
             documentation complete? within submission window?
  
  3. SUBMITTED — sent to HMO (via portal, API, or exported file)
             Deadline tracked: most HMOs require submission within 30–90 days
  
  4. IN REVIEW — HMO is processing
             System sends reminder if no response in 14 days
  
  5. APPROVED — HMO agrees to pay
             Amount may differ from submitted (partial approvals common)
  
  6. PAID — HMO payment received and reconciled
  
  7. QUERIED — HMO asks for more info
             Staff responds to query within system, resubmit
  
  8. REJECTED — HMO refuses to pay
             Reason captured: missing pre-auth / incorrect code / excluded service
             → Dispute workflow activated (appeal, rebill, or write off)
```

### HMO Dashboard for Billing Officer

```
┌──────────────────────────────────────────────────────────────────┐
│  HMO CLAIMS TRACKER                          FRI 29 AUG 2026    │
├──────────────────────────────────────────────────────────────────┤
│  DRAFT         23 claims   ₦345,000    [Review & Submit All]    │
│  SUBMITTED     67 claims   ₦1.2M       [Follow Up]              │
│  IN REVIEW     41 claims   ₦890,000    Avg: 8 days pending      │
│  QUERIED        8 claims   ₦156,000    ⚠ ACTION NEEDED          │
│  APPROVED      34 claims   ₦620,000    Payment expected: 3 days │
│  REJECTED      12 claims   ₦215,000    ⚠ APPEAL REQUIRED        │
│  PAID         189 claims   ₦3.4M       This month               │
├──────────────────────────────────────────────────────────────────┤
│  ⚠ 3 claims expire in 5 days — submit now to avoid forfeiture   │
└──────────────────────────────────────────────────────────────────┘
```

---

## Part 6: The Cashier Interface

The cashier is the final human in the billing journey.
Their job in AraCare: **verify identity, collect money, issue receipt**.
They do NOT calculate anything. They do NOT enter line items.

### Cashier Screen

```
┌──────────────────────────────────────────────────────────────────┐
│  INVOICE #INV-20260829-00234          CASH-033                  │
│  OKONKWO ADAEZE | ARC-LAG-2026-004521 | 29 Aug 2026            │
├─────────────────────────────────────────┬────────────────────────┤
│  LINE ITEMS                             │  PAYMENT SUMMARY       │
│                                         │                        │
│  ✅ Consultation (New)      ₦1,500     │  Subtotal:   ₦7,850   │
│  ✅ Doctor fee              ₦2,500     │  Discount:   ₦0        │
│  ✅ Malaria RDT             ₦800       │  Total:      ₦7,850   │
│  ✅ FBC                     ₦1,500     │                        │
│  ✅ Artemether tabs         ₦1,200     │  Deposit pd: -₦2,000  │
│  ✅ Paracetamol x12         ₦350       │                        │
│                                         │  BALANCE DUE           │
│  All services verified ✓               │  ₦5,850               │
├─────────────────────────────────────────┴────────────────────────┤
│  COLLECT PAYMENT                                                 │
│                                                                  │
│  [💵 CASH]  [💳 POS/CARD]  [📱 TRANSFER]  [📞 USSD]           │
│                                                                  │
│  [⚠ APPLY DISCOUNT — requires admin PIN]                       │
│  [📋 PAYMENT PLAN — requires admin approval]                    │
└──────────────────────────────────────────────────────────────────┘
```

### Payment Collection Flows

**Cash:**
```
Cashier enters amount received: [₦6,000]
System calculates change: ₦150
[CONFIRM PAYMENT] → Receipt printed + SMS sent → Journey complete
```

**POS / Card:**
```
[POS/CARD] → System generates transaction reference
Cashier taps amount on Paystack Terminal (physical POS device)
Patient inserts/taps card
Paystack webhook fires → payment confirmed in system automatically
Receipt printed → Journey complete
```

**Bank Transfer (Virtual Account):**
```
[TRANSFER] → System generates unique virtual account for this invoice
              (via Paystack/Flutterwave virtual account API)
Screen shows: "Transfer ₦5,850 to:
              Account: 0123456789
              Bank: Wema Bank
              Reference: INV-20260829-00234"
Patient opens their banking app or dials USSD
Paystack webhook fires when transfer lands → payment confirmed automatically
Cashier doesn't have to verify manually — system does it
```

**USSD (for patients without smartphones):**
```
[USSD] → System generates Paystack USSD code
Patient dials: *737*000*5850#  (example)
Enters their bank PIN
Transaction confirmed via webhook
No internet needed on patient's phone — just GSM network
```

---

## Part 7: Discount and Waiver Controls

These are where fraud happens in manual systems.
AraCare makes every discount an audited event.

### Who Can Discount What

```
CASHIER:
  → Cannot apply any discount without authorization
  → The "Apply Discount" button requires an admin PIN

SUPERVISOR (on-site admin):
  → Can approve discounts up to 30% of invoice value
  → Reason must be selected from dropdown + free text
  → Their staff ID is recorded against the discount

HOSPITAL DIRECTOR / FINANCE ADMIN:
  → Can approve any discount or full waiver
  → Required for: charity cases, VIP discounts, write-offs
  → Two-factor: their system login + their PIN

SYSTEM (automatic):
  → Applies pre-configured staff discount automatically
  → Applies government subsidy rates automatically
  → These are not "discounts" — they are priced correctly from the start
```

### Every Discount Creates an Audit Record

```
discount_audit {
  invoice_id
  original_amount        ₦7,850
  discount_amount        ₦2,000
  discount_reason        "Charity case — patient unable to pay"
  approved_by            Dr. Emeka Eze (Staff ID: STF-0023)
  approved_at            2026-08-29 16:34:07
  final_amount           ₦5,850
}
```

The finance dashboard shows every discount ever given, by whom, on what, for what reason.
Unusual patterns (same cashier giving many discounts, discounts at shift end, etc.)
are auto-flagged for review.

---

## Part 8: Defaulter Management

### What Happens When a Patient Doesn't Pay in Full

```
Patient has ₦7,850 bill. They can only pay ₦3,000 today.

OPTION A (if hospital allows partial payment):
  → Cashier records ₦3,000 payment
  → Invoice status: PARTIALLY_PAID
  → Outstanding balance: ₦4,850 flagged on patient account
  → Patient signs a written payment undertaking (printed from system)
  → Next visit check-in: system shows ⚠ "Outstanding balance: ₦4,850"
  → Receptionist is prompted to collect outstanding before new consultation
     (can be overridden for emergencies)

OPTION B (hospital requires full payment):
  → Cashier cannot close invoice without full payment
  → Options presented: USSD, transfer, ask family to send money
  → If truly unable to pay → escalate to admin for waiver decision
  → NEVER detain patient (illegal in Nigeria) — but record the debt
```

### The Defaulter Flag

```
patient_flags table:
  patient: OKONKWO ADAEZE (ARC-LAG-2026-004521)
  flag_type: OUTSTANDING_BALANCE
  amount: ₦4,850
  since: 29 Aug 2026
  notes: "Patient paid ₦3,000 of ₦7,850. Balance ₦4,850 outstanding."
```

At next check-in, receptionist screen shows:

```
⚠ OUTSTANDING BALANCE — ₦4,850
   From visit: 29 Aug 2026
   
   [COLLECT NOW — POS/CASH/TRANSFER]
   [Patient cannot pay — escalate to admin]
   [Emergency visit — override and proceed]
```

**Important:** Emergency visits are NEVER blocked by an outstanding balance.
Nigerian law prohibits withholding emergency care for non-payment.
The flag is for information only in emergency mode.

---

## Part 9: The Fee Schedule (Price List)

Every hospital that runs AraCare configures their own fee schedule.
This is the master price list that drives all automatic charge creation.

```
service_price_list:
  
  Code        Service Name                Category     Std Price    Notes
  ─────────────────────────────────────────────────────────────────────────
  CONS-NEW    Consultation (New Patient)  Consultation ₦1,500
  CONS-FLW    Consultation (Follow-up)   Consultation ₦800
  CONS-EMG    Emergency Consultation     Consultation ₦3,000
  LAB-MAL     Malaria RDT                Laboratory   ₦800
  LAB-FBC     Full Blood Count           Laboratory   ₦1,500
  LAB-LFT     Liver Function Test        Laboratory   ₦3,500
  LAB-RFT     Renal Function Test        Laboratory   ₦3,200
  LAB-TYP     Typhoid (Widal)            Laboratory   ₦600
  LAB-HIV     HIV Rapid Test             Laboratory   ₦500      (often subsidized)
  PROC-INJ    Injection (IM/IV)          Procedure    ₦300
  PROC-DRS    Dressing                   Procedure    ₦500
  PROC-IVL    IV Line insertion          Procedure    ₦800
  DRUG-...    (from pharmacy catalogue)  Pharmacy     varies
  BED-GEN     General ward bed/day       Admission    ₦3,500
  BED-PRV     Private room/day           Admission    ₦12,000
```

HMO tariffs are stored separately per HMO provider as a mapping:
`{service_code} → {hmo_tariff_price}` for each accredited HMO.

Admin can update prices. Price changes apply to new invoices only —
not to open invoices already in ACCUMULATING state.

---

## Part 10: End-of-Day Reconciliation

Every cashier closes out their shift with a reconciliation report.

### Cashier Close-Out

```
CASHIER CLOSE-OUT — CASHIER 3 (AMAKA IBRAHIM)
Date: 29 Aug 2026 | Shift: 8:00 AM – 4:00 PM

TRANSACTIONS SUMMARY:
  Invoices processed:    47
  Total invoiced:        ₦312,500
  
  Collected by method:
    Cash:                ₦145,000   (28 transactions)
    POS/Card:            ₦87,500    (11 transactions)
    Bank Transfer:       ₦52,000    (6 transactions)
    USSD:                ₦18,000    (2 transactions)
  
  Total collected:       ₦302,500
  
  Discounts given:       ₦3,000     (2 — both admin-approved)
  Partial payments:      ₦7,000     (2 patients — outstanding flagged)
  
  Expected cash in drawer:  ₦145,000
  Actual cash in drawer:    [  enter  ]  → system flags variance
  
  POS terminal report:  [auto-pulled from Paystack Terminal API]
  Transfer confirmations: [auto-matched via webhook records]
  
  [SUBMIT CLOSE-OUT]  [FLAG DISCREPANCY]
```

Variance between expected and actual cash triggers a flag to the finance supervisor.
This is where internal fraud gets caught — daily, automatically.

---

## Part 11: Data Models

```sql
-- The master invoice — one per visit
invoices (
  id                UUID PRIMARY KEY,
  invoice_number    VARCHAR UNIQUE,         -- INV-20260829-00234
  visit_id          UUID REFERENCES visits(id),
  patient_id        UUID REFERENCES patients(id),
  facility_id       UUID NOT NULL,
  payment_track     ENUM('out_of_pocket','hmo','staff','government','waiver'),
  hmo_provider      VARCHAR,               -- if HMO track
  status            ENUM('draft','accumulating','pending_payment',
                         'partially_paid','paid','hmo_pending',
                         'waived','cancelled','disputed'),
  subtotal          DECIMAL(12,2) DEFAULT 0,
  total_discount    DECIMAL(12,2) DEFAULT 0,
  total             DECIMAL(12,2) DEFAULT 0,
  amount_paid       DECIMAL(12,2) DEFAULT 0,
  amount_outstanding DECIMAL(12,2) DEFAULT 0,
  hmo_responsibility DECIMAL(12,2) DEFAULT 0,
  patient_responsibility DECIMAL(12,2) DEFAULT 0,
  created_at        TIMESTAMP,
  finalized_at      TIMESTAMP,
  paid_at           TIMESTAMP
)

-- Individual charge lines — created automatically by departments
invoice_line_items (
  id                UUID PRIMARY KEY,
  invoice_id        UUID REFERENCES invoices(id),
  journey_step_id   UUID,                  -- which step created this charge
  service_code      VARCHAR NOT NULL,
  service_name      VARCHAR NOT NULL,
  category          ENUM('registration','consultation','lab','pharmacy',
                         'procedure','imaging','admission','consumable'),
  quantity          DECIMAL(8,2) DEFAULT 1,
  unit_price        DECIMAL(10,2) NOT NULL,
  discount          DECIMAL(10,2) DEFAULT 0,
  subtotal          DECIMAL(10,2) NOT NULL,
  hmo_covered_amount DECIMAL(10,2) DEFAULT 0,
  patient_amount    DECIMAL(10,2) NOT NULL, -- what patient actually owes
  created_by_dept   VARCHAR NOT NULL,
  created_by_staff  UUID,
  created_at        TIMESTAMP NOT NULL
)

-- Payment transactions — one per payment event
payments (
  id                UUID PRIMARY KEY,
  invoice_id        UUID REFERENCES invoices(id),
  patient_id        UUID REFERENCES patients(id),
  amount            DECIMAL(12,2) NOT NULL,
  payment_method    ENUM('cash','pos','bank_transfer','ussd','hmo_payment',
                         'waiver','staff_deduction','partial_credit'),
  status            ENUM('pending','confirmed','failed','refunded'),
  reference_number  VARCHAR,               -- for digital payments
  gateway_reference VARCHAR,               -- Paystack/Flutterwave ref
  collected_by      UUID,                  -- cashier staff_id
  cashier_session_id UUID,
  is_deposit        BOOLEAN DEFAULT FALSE,
  payment_at        TIMESTAMP,
  notes             TEXT
)

-- Pre-payment deposits at check-in
deposits (
  id                UUID PRIMARY KEY,
  visit_id          UUID REFERENCES visits(id),
  patient_id        UUID REFERENCES patients(id),
  invoice_id        UUID REFERENCES invoices(id),
  amount            DECIMAL(10,2) NOT NULL,
  payment_method    ENUM('cash','pos','bank_transfer','ussd'),
  collected_by      UUID,
  applied_at        TIMESTAMP,            -- when deducted from final bill
  refunded_amount   DECIMAL(10,2),
  refunded_at       TIMESTAMP
)

-- HMO claim tracking
hmo_claims (
  id                UUID PRIMARY KEY,
  invoice_id        UUID REFERENCES invoices(id),
  patient_id        UUID REFERENCES patients(id),
  hmo_provider      VARCHAR NOT NULL,
  hmo_enrollee_id   VARCHAR NOT NULL,
  pre_auth_code     VARCHAR,
  claim_reference   VARCHAR UNIQUE,        -- HMO's reference number
  status            ENUM('draft','internal_review','submitted','in_review',
                         'queried','approved','rejected','paid','appealed'),
  submitted_amount  DECIMAL(12,2),
  approved_amount   DECIMAL(12,2),
  paid_amount       DECIMAL(12,2),
  rejection_reason  TEXT,
  query_notes       TEXT,
  submission_deadline DATE,
  submitted_at      TIMESTAMP,
  approved_at       TIMESTAMP,
  paid_at           TIMESTAMP
)

-- Service price catalogue
service_price_list (
  id                UUID PRIMARY KEY,
  facility_id       UUID NOT NULL,
  service_code      VARCHAR NOT NULL,
  service_name      VARCHAR NOT NULL,
  category          VARCHAR NOT NULL,
  standard_price    DECIMAL(10,2) NOT NULL,
  is_active         BOOLEAN DEFAULT TRUE,
  effective_from    DATE,
  UNIQUE(facility_id, service_code)
)

-- HMO tariff schedules (per HMO, per service)
hmo_tariffs (
  id                UUID PRIMARY KEY,
  facility_id       UUID NOT NULL,
  hmo_provider      VARCHAR NOT NULL,
  service_code      VARCHAR NOT NULL,
  tariff_price      DECIMAL(10,2) NOT NULL,
  coverage_type     ENUM('full','partial','excluded'),
  patient_co_pay    DECIMAL(10,2) DEFAULT 0,
  effective_from    DATE
)

-- Discount audit trail
discount_records (
  id                UUID PRIMARY KEY,
  invoice_id        UUID REFERENCES invoices(id),
  line_item_id      UUID,                 -- null if full invoice discount
  original_amount   DECIMAL(12,2),
  discount_amount   DECIMAL(12,2),
  discount_type     ENUM('hardship','vip','staff','government','error_correction','other'),
  reason_notes      TEXT NOT NULL,
  approved_by       UUID NOT NULL,        -- staff_id of approver
  approved_at       TIMESTAMP NOT NULL
)

-- Patient outstanding balance flags
patient_balance_flags (
  id                UUID PRIMARY KEY,
  patient_id        UUID REFERENCES patients(id),
  invoice_id        UUID REFERENCES invoices(id),
  outstanding_amount DECIMAL(12,2) NOT NULL,
  is_active         BOOLEAN DEFAULT TRUE,
  flagged_at        TIMESTAMP,
  cleared_at        TIMESTAMP,
  notes             TEXT
)

-- Cashier shift reconciliation
cashier_sessions (
  id                UUID PRIMARY KEY,
  facility_id       UUID NOT NULL,
  cashier_id        UUID NOT NULL,
  session_date      DATE NOT NULL,
  shift             ENUM('morning','afternoon','night'),
  opened_at         TIMESTAMP,
  closed_at         TIMESTAMP,
  expected_cash     DECIMAL(12,2),
  actual_cash_entered DECIMAL(12,2),
  cash_variance     DECIMAL(12,2),
  total_pos         DECIMAL(12,2),
  total_transfer    DECIMAL(12,2),
  total_ussd        DECIMAL(12,2),
  total_collected   DECIMAL(12,2),
  invoices_count    INTEGER,
  is_variance_flagged BOOLEAN DEFAULT FALSE,
  supervisor_reviewed_by UUID
)
```

---

## Part 12: Nigerian Edge Cases

| Scenario | How AraCare Handles It |
|----------|----------------------|
| **Patient says "I'll pay later / tomorrow"** | Partial or zero payment recorded. Outstanding flagged. Written undertaking printed for them to sign. Flagged at next check-in. |
| **HMO card presented but expired** | System flags expiry. Patient given options: (1) pay out-of-pocket, (2) call HMO to confirm coverage verbally while staff enter extension date. |
| **HMO rejects claim after patient left** | Claim moves to DISPUTED. Billing officer reviews and either: re-submits with correction, appeals, or converts to patient bill (with patient notification). |
| **Same drug, different prices (branded vs generic)** | Both options in pharmacy catalogue. Doctor specifies or pharmacist selects. Patient can be shown price difference and choose. |
| **Emergency patient, no money** | Emergency care proceeds. Invoice in DRAFT. Social services/admin notified. Waiver process begins. Patient not detained. |
| **Patient claims they already paid (cash, no receipt)** | Dispute workflow. Finance supervisor reviews cashier session records. If cash cannot be accounted for, investigation opened. |
| **POS machine down** | Fallback to bank transfer (virtual account) or USSD. Cash always available as last resort. Invoice stays open until payment confirmed. |
| **Government-run hospital, some services are free** | Service marked as `government_subsidized = true` in price list. Zero patient charge. Facility submits claim to BHCPF or state health ministry separately. |
| **Doctor adds a service not in the price list** | Miscellaneous charge workflow: doctor enters service name + amount, triggers admin approval. Admin approves → charge added. Creates audit record. |
| **Patient asks for itemized receipt** | System prints full itemized breakdown at any point — during or after visit. Patient can also receive via SMS (summary) or WhatsApp (detailed). |

---

## Summary: Key Design Decisions

| Decision | Choice | Reason |
|---------|--------|--------|
| Charge creation | Automatic from clinical depts | Eliminates cashier entry errors and unbilled services |
| Invoice structure | One per visit | Unified view, single payment point |
| Deposit model | Configurable, collected at check-in | Anchors patient financially, reduces walk-outs |
| Cashier role | Collect only — not calculate | Removes the main fraud opportunity |
| Discounts | Always require approval + audit | Every discount leaves a trail |
| Payment methods | Cash, POS, Transfer, USSD | Covers 100% of Nigerian patient types |
| HMO claims | Auto-generated, tracked lifecycle | Reduces rejection from documentation errors |
| Outstanding balances | Flagged, not blocking (emergency exempt) | Legally compliant, compassionate |
| Cashier reconciliation | Daily close-out with variance detection | Catches internal fraud within 24 hours |
| Fee schedule | Hospital-configurable, code-based | Works for private clinics and government hospitals |
