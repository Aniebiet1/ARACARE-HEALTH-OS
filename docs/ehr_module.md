# AraCare — The Electronic Health Record (EHR)
### Deep Dive: The Clinical Core of the Entire System

---

## What the EHR Is in This System

Every module we have designed so far either **feeds into** or **feeds out of** the EHR:

```
Queue Engine  ──────────────▶  EHR  ◀──────────── Patient Registration
                               │
              ┌────────────────┼─────────────────┐
              ▼                ▼                 ▼
         Billing Engine   Monitoring        Inventory/Pharmacy
         (charges from    (vitals feed in)  (drug stock reduces
          clinical orders)                   when prescribed)
              │                ▼                 │
              └────────────▶ Patient ◀───────────┘
                             Record
                           (permanent)
```

The EHR is where clinical work actually happens:
- The doctor's workspace for consultation
- The nurse's workspace for vitals and medication recording
- The source of every charge that hits the billing engine
- The source of every lab order and pharmacy request
- The permanent longitudinal record of everything that happened to a patient

---

## The Most Important Design Constraint

Nigerian doctors see **30 to 80 patients per day**.

A simple malaria consultation must be completable in the EHR in **under 3 minutes**.
A hypertension follow-up: under 2 minutes.
A complex new presentation: 5–7 minutes.

If the EHR is slow, cluttered, or requires many clicks, doctors will abandon it.
They will go back to paper. Everything falls apart.

This means:
- **Speed over completeness** — ask for the minimum, infer the rest
- **Clinical templates** — one click to load the malaria template
- **Common drugs pre-built** — type "ACT" and get Artemether-Lumefantrine with correct adult dosing
- **Offline always** — network delay cannot cause a consultation to freeze
- **Keyboard shortcuts** — experienced doctors should rarely need a mouse

---

## Part 1: Who Uses the EHR and What They See

The EHR is not one interface — it is **role-specific workstations** built on one shared data model.

| User | Their Workspace | What They Do |
|------|----------------|-------------|
| **Doctor** | Full clinical workstation | Consultation, diagnosis, orders, prescriptions, referrals |
| **Nurse (OPD)** | Triage & vital signs station | Record vitals, triage assessment, nursing notes |
| **Nurse (Ward)** | Inpatient nursing station | Medication administration, observation, shift notes |
| **Lab Technician** | Lab order queue + result entry | Process test orders, record results |
| **Pharmacist** | Prescription dispensing queue | View prescriptions, dispense, record |
| **Admin/Records** | Patient overview (read-only clinical) | View history, generate summaries |

Each role sees **only what they need**. A pharmacist sees the prescription.
They do not see the diagnosis that led to it (unless relevant — e.g., allergy check).
A lab tech sees the test ordered and clinical notes. Not the full history.

---

## Part 2: The Patient Chart — What the Doctor Sees

When a doctor calls a patient and they arrive at the consulting room,
the doctor opens the patient's chart on their workstation.

This is what loads — the **patient chart overview**:

```
┌─────────────────────────────────────────────────────────────────────┐
│  BELLO YUSUF, Male, 45 yrs  │  ARC-LAG-2026-004521  │  [Photo]    │
│  Blood Group: A+             │  Last Visit: 12 Jun 2026            │
├─────────────────────────────────────────────────────────────────────┤
│  ⚠ ALERTS                                                          │
│  🔴 ALLERGY: Penicillin — Severe rash and throat swelling          │
│  🟡 Hypertension — on Amlodipine 5mg daily (since Mar 2024)       │
│  🟡 Type 2 Diabetes — HbA1c: 8.2% (Jun 2026, above target)        │
├─────────────────────────────────────────────────────────────────────┤
│  TABS:  [TODAY'S VISIT]  [HISTORY]  [LAB RESULTS]  [MEDICATIONS]  │
│         [VITALS TREND]   [DOCUMENTS] [ANC] *(if applicable)*       │
└─────────────────────────────────────────────────────────────────────┘
```

**Key principle:** The **red allergy alert** and **active chronic conditions**
are ALWAYS visible at the top. A doctor should never be able to prescribe
Amoxicillin to a penicillin-allergic patient without seeing a hard warning.

---

## Part 3: The Triage Workstation — Nurse's First Stop

Before the patient reaches the doctor, the nurse records vitals at triage.
This is the nurse's workstation — designed to be completed in 3–5 minutes per patient.

```
TRIAGE STATION — OPD-045 | OKONKWO ADAEZE, F, 28yrs
──────────────────────────────────────────────────────
VITALS (required):
  Blood Pressure:  [120] / [80]  mmHg     ← Normal ✓
  Temperature:     [38.4] °C               ← ⚠ Fever flagged
  Pulse Rate:      [92]  bpm               ← Normal ✓
  Respiratory Rate:[18]  breaths/min       ← Normal ✓
  SpO2:            [98]  %                 ← Normal ✓
  Weight:          [62]  kg
  Height:          [163] cm  →  BMI: 23.3  ← Normal ✓

PAEDIATRIC EXTRAS (shown if patient is u-5):
  MUAC:   [  ] cm     Temp method: [Axilla / Tympanic / Rectal]
  
ADDITIONAL (quick-select):
  Pain Score:  [0][1][2][3][4][5][6][7][8][9][10]
  
CHIEF COMPLAINT (nurse records what patient says):
  [Patient reports headache and fever since yesterday. ________]

NURSE'S TRIAGE ASSESSMENT:
  Priority: [🟢 Normal]  [🟠 High]  [🔴 Emergency]
  
  [SAVE & SEND TO QUEUE]
```

When the nurse saves:
- Vitals are written to the patient's record for this visit
- Abnormal values are flagged (fever > 37.5°C, SpO2 < 94%, etc.)
- Doctor receives a preview showing vitals before patient arrives
- Any values in critical range → automatic emergency alert to duty doctor

---

## Part 4: The SOAP Note — The Doctor's Core Workflow

The clinical note is in **SOAP format**. This is the international standard,
and Nigerian medical training uses it. Each section has structured and free-text fields.

```
TODAY'S VISIT — OKONKWO ADAEZE — 29 Aug 2026 | OPD-045 | Dr. Emeka Eze

VITALS (from triage — pre-populated, read-only here):
  BP: 120/80 | Temp: 38.4°C ⚠ | Pulse: 92 | RR: 18 | SpO2: 98% | Wt: 62kg

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
S — SUBJECTIVE (what the patient tells you)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Chief Complaint: [Fever and headache for 2 days          ]
  
  History of Presenting Complaint:
  [Fever started suddenly 2 days ago. Associated with headache,
   body aches, and chills. No cough, vomiting, or diarrhoea.
   No recent travel. Last malaria episode: 4 months ago.     ]

  Review of Systems:
  [Quick checkboxes: Cough □  Vomiting □  Diarrhoea □
   Urinary symptoms □  Chest pain □  Shortness of breath □
   Joint pain ☑  Rash □  Loss of appetite ☑               ]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
O — OBJECTIVE (what you find on examination)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  General: [Conscious, alert, febrile, mildly ill-looking    ]
  
  Quick-select findings:
  Pallor: [None / Mild / Moderate / Severe]
  Jaundice: [None / Present]
  Lymphadenopathy: [None / Cervical / Axillary / Inguinal]
  
  Abdominal: [Soft, non-tender. Mild splenomegaly.           ]
  Other systems: [Cardiovascular: S1S2 normal. Respiratory: clear.]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
A — ASSESSMENT (your diagnosis)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Search: [malaria                   🔍]
  
  Results:
  ● B54   — Unspecified malaria
  ● B50.0 — P. falciparum malaria with cerebral complications
  ● B50.9 — P. falciparum malaria, unspecified     ← [ADD]
  ● B51   — P. vivax malaria
  
  Active diagnoses for this visit:
  1. B50.9 — Plasmodium falciparum malaria [PRIMARY] [REMOVE]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
P — PLAN (what you're going to do)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  [+ REQUEST LAB]   [+ PRESCRIBE]   [+ REFER]   [+ ADMIT]

  Lab Orders:
  ● Malaria RDT — STAT     [remove]
  ● FBC        — Routine   [remove]

  Prescriptions:
  ● Artemether-Lumefantrine 80/480mg
    4 tabs stat, then 4 tabs at 8h, 24h, 36h, 48h, 60h
    (weight-based auto-calculated: 62kg → adult dose confirmed)
    [remove]
  ● Paracetamol 1000mg — 3x daily for 3 days  [remove]

  Follow-up: [3 days if no improvement  ]
  Additional notes: [Advised to complete full ACT course. Rest. ]

  [SIGN & SAVE NOTE]   [SAVE DRAFT]
```

When doctor clicks **SIGN & SAVE NOTE**:
1. Note is cryptographically signed with doctor's credentials
2. Diagnoses (ICD-10 codes) are committed to patient's problem list
3. Lab orders are sent to the lab queue → LAB ticket created
4. Prescriptions are sent to pharmacy → PHARM ticket created
5. Charges are automatically generated in billing engine
6. Note becomes **immutable** — only addendum possible (no editing after signing)

---

## Part 5: Clinical Templates — The Speed Engine

For the most common Nigerian diagnoses, AraCare has pre-built templates.
Doctor selects a template, it pre-fills the SOAP note with common findings,
common lab orders, and standard treatment. Doctor adjusts what's different,
then signs.

### Template: Uncomplicated Malaria (most common OPD presentation)
```
Auto-fills:
  S: "Fever, headache, body aches, chills" — doctor edits duration
  O: "Febrile, mild pallor" — doctor edits
  A: B50.9 (P. falciparum, unspecified) — pre-selected
  P: 
    Labs: Malaria RDT (STAT), FBC
    Rx: Artemether-Lumefantrine (weight-based dose auto-calculated)
        Paracetamol 1g TDS x3 days
    Follow-up: 3 days if not improving / RDT at 3 days
```

### Template: Hypertension Follow-up
```
Auto-fills:
  S: "Routine BP review. [Any symptoms?]"
  O: "BP: [from today's vitals — auto-pulled]"
     "Currently on: [current medications — auto-pulled]"
  A: I10 — Essential hypertension
  P:
    Labs: U&E, Creatinine (if >3 months since last), Lipid profile (if due)
    Rx: [Current medications — refill options shown]
    Target BP: <130/80 mmHg
    Follow-up: 4–8 weeks
```

### Template: Typhoid Fever
```
Auto-fills:
  S: "Sustained fever, headache, abdominal discomfort, constipation/diarrhoea"
  O: "Febrile, coated tongue, mild abdominal tenderness"
  A: A01.0 — Typhoid fever
  P:
    Labs: Widal test, Blood culture (if available), FBC
    Rx: Ciprofloxacin 500mg BD x 7–10 days OR Azithromycin 1g stat then 500mg OD x6 days
        (Amoxicillin shown greyed out if patient has penicillin allergy)
```

### Template: ANC Booking Visit (First ANC)
```
  Full ANC booking form opens (Section 7 below)
```

### Template: Under-5 Well-Baby Visit
```
  Growth chart opens, immunization due list shown, standard checks displayed
```

### Template: Sickle Cell Crisis
```
Auto-fills:
  S: "Painful crisis — site: [___], severity: [pain score]"
  A: D57.0 — Sickle cell anaemia with crisis
  P:
    Labs: FBC, Blood film, Blood group/crossmatch if severe
    Rx: IV fluids (normal saline), Strong analgesia (Diclofenac/Tramadol)
        Folic acid 5mg daily
    Admit if: severe pain, Hb < 6g/dL, fever with crisis
```

**Why templates matter:** A nurse-to-patient ratio of 1:30 means the doctor
is cognitively exhausted by patient 25. Templates reduce cognitive load,
reduce omission errors, and keep the consultation moving.

---

## Part 6: Lab Orders and Results

### The Lab Technician's Workstation

After a doctor creates a lab order, it appears in the lab queue:

```
LAB QUEUE — 29 AUG 2026                    Active techs: 2

  LAB-018  |  OKONKWO ADAEZE  |  Malaria RDT [STAT] + FBC [Routine]
            |  Ordered: 10:23 AM  |  Ordered by: Dr. Eze
            |  Clinical note: "Fever 38.4°C, day 2"
            |  [COLLECT SPECIMEN]  [MARK PROCESSING]  [ENTER RESULTS]

  LAB-019  |  BELLO YUSUF  |  U&E, Creatinine [Routine]
            |  Ordered: 10:41 AM  |  Ordered by: Dr. Eze
            |  [COLLECT SPECIMEN]
```

### Entering Results

```
ENTER RESULTS — LAB-018 — OKONKWO ADAEZE

  Malaria RDT:
    Result: [POSITIVE ●]  [NEGATIVE]
    Parasite: [P. falciparum ●] [P. vivax] [Mixed] [Indeterminate]
    Parasite density: [+] [++] [+++] [++++]
    
  FBC:
    Haemoglobin:    [10.2]  g/dL    Reference: 12–16  ← ⚠ LOW
    WBC:            [11.5]  x10⁹/L  Reference: 4–11   ← ⚠ HIGH
    Platelets:      [95]    x10⁹/L  Reference: 150–400 ← ⚠ LOW
    Haematocrit:    [31]    %
    
    [SAVE & RELEASE RESULTS]
```

When results are saved:
- Doctor receives a **notification** on their workstation: "Lab results available: OPD-045"
- Results appear in the patient's chart under Lab Results
- Abnormal values are **highlighted in red** (Hb 10.2 flagged as LOW)
- Critical values (e.g., Hb < 6g/dL, Platelet < 20) trigger an **urgent alert** to doctor
- Results are automatically appended to the SOAP note's Objective section (if note still in draft)
- Billing charge for the test is confirmed/finalized

### Result History and Trending

For chronic disease patients, results trend over time:

```
HAEMOGLOBIN TREND — BELLO YUSUF (Diabetic)

  Date        HbA1c    Trend
  ─────────────────────────
  Mar 2025    7.8%     —
  Jun 2025    8.0%     ↑
  Sep 2025    7.9%     ↓
  Dec 2025    8.4%     ↑
  Mar 2026    8.1%     ↓
  Jun 2026    8.2%     → (target: <7.0%)

  ⚠ Above target for 5 consecutive readings.
  Consider: medication adjustment or diabetes educator referral.
```

---

## Part 7: Prescription Management

### The Drug Catalogue

AraCare's drug catalogue is based on:
- Nigeria Essential Medicines List (NEML)
- NAFDAC Greenbook (all registered drugs)
- Hospital's own formulary (drugs they stock)

Each drug entry includes:
- Generic name (primary) + common brand names
- Available formulations (tablet, syrup, injection, cream, etc.)
- Standard adult dose
- Weight-based paediatric dose formula
- Contraindications and interactions
- NAFDAC registration number
- Whether it's on the hospital's stock list

### Drug Interaction Checking

When a doctor adds a new prescription, the system checks:
1. **Against patient's known allergies** → hard block if allergy match
2. **Against current medications** → warning if known interaction
3. **Against patient's conditions** → warning if contraindicated

```
⚠ DRUG INTERACTION WARNING

  You are prescribing: Ciprofloxacin 500mg
  
  Patient's current medication: Warfarin 5mg daily
  
  Interaction: Ciprofloxacin significantly increases Warfarin effect,
  risking bleeding. Monitor INR closely or consider alternative antibiotic.
  
  [ACKNOWLEDGE AND PROCEED]   [CHOOSE ALTERNATIVE]
```

For allergy conflicts, it is a **hard block** — doctor cannot proceed
without explicitly acknowledging and documenting their clinical reasoning.

### Paediatric Weight-Based Dosing

When a prescription is ordered for a child:

```
PRESCRIBE — AMARA CHUKWU, Female, 4 yrs, 16 kg

  Drug: Artemether-Lumefantrine 20/120mg (paediatric)
  
  Weight-based dose calculator:
    Patient weight: 16 kg
    Dose per kg: 1.7 mg/kg Artemether
    Calculated dose: ~27 mg Artemether per dose
    
  Tablet formulation options:
    → 1 tablet (20mg Artemether) — RECOMMENDED for 5–14 kg
    → 2 tablets would be for 15–24 kg range ← [AUTO-SELECTED ●]
    
  Regimen: 2 tabs stat, 2 tabs at 8h, 24h, 36h, 48h, 60h
  
  [CONFIRM DOSE]   [MANUAL OVERRIDE — requires clinical note]
```

The system auto-selects the correct paediatric dose band and confirms.
If the doctor overrides to a higher dose, they must document why.
Under-dosing errors and over-dosing errors are both prevented this way.

### The Pharmacy Queue

After prescription is signed, pharmacist sees:

```
PHARMACY QUEUE — 29 AUG 2026

  PHARM-022  |  OKONKWO ADAEZE  |  ARC-LAG-2026-004521
              |  
              |  PRESCRIPTIONS:
              |  1. Artemether-Lumefantrine 80/480mg
              |     4 tabs stat, then at 8h, 24h, 36h, 48h, 60h
              |     Total: 24 tablets
              |     📦 In stock: 47 tabs  ✓
              |  
              |  2. Paracetamol 500mg
              |     2 tabs TDS x3 days  →  Total: 18 tabs
              |     📦 In stock: 340 tabs ✓
              |  
              |  ⚠ ALLERGY ON RECORD: Penicillin
              |     (no penicillin in this prescription — safe ✓)
              |  
              |  [DISPENSE ALL]   [PARTIAL DISPENSE]   [OUT OF STOCK]
```

When pharmacist clicks "DISPENSE ALL":
- Pharmacy stock is decremented in the inventory module
- Each drug is tied to the patient's visit record
- Billing charge is confirmed
- Patient's PHARM journey step moves to COMPLETED
- System cascades to next step (Cashier queue created)

---

## Part 8: Referrals and Admissions

### Internal Referral
Doctor clicks "+ REFER" and selects internal department:

```
INTERNAL REFERRAL — OKONKWO ADAEZE

  Refer to: [Cardiology ▼]
  Urgency:  [Routine ●]  [Urgent]  [Emergency]
  
  Reason: [Palpitations with exertion. ECG shows irregular rhythm.
            Please review for possible AF.                          ]
  
  Clinical summary: [auto-populated from current note]
  
  [SEND REFERRAL]
```

This creates a new journey step for the Cardiology queue.
Patient gets SMS: "You have been referred to the Cardiology clinic.
Your queue number is CARD-007. Please proceed to Block B."

### External Referral Letter

Doctor clicks "+ REFER" → "External facility":

```
EXTERNAL REFERRAL — BELLO YUSUF

  Referring to: [Lagos University Teaching Hospital (LUTH)    ]
  Department:   [Nephrology                                   ]
  
  [GENERATE REFERRAL LETTER]
  
  ─── GENERATED LETTER PREVIEW ──────────────────────────────────
  
  Date: 29 August 2026
  
  To: The Consultant Nephrologist,
  Lagos University Teaching Hospital
  
  Dear Colleague,
  
  RE: MR. BELLO YUSUF | DOB: 12/05/1981 | ARC-LAG-2026-004521
  
  I am referring this 45-year-old male hypertensive diabetic patient
  for specialist nephrology review.
  
  PRESENTING CONCERN: Worsening renal function on routine monitoring.
  Creatinine has risen from 112 to 187 μmol/L over 6 months.
  
  BACKGROUND: Known hypertension (since 2019), Type 2 Diabetes (since 2021).
  Current medications: Amlodipine 5mg OD, Metformin 500mg BD, Lisinopril 5mg OD.
  
  RECENT INVESTIGATIONS: [auto-inserted from patient's record]
  - Creatinine: 187 μmol/L (Jun 2026)
  - eGFR: 38 mL/min/1.73m²
  
  Please review and advise on further management.
  
  Yours sincerely,
  Dr. Emeka Eze (MBBS, FMCP)
  General Hospital Ikeja
  Tel: 0801234567
  ──────────────────────────────────────────────────────────────
  
  [PRINT LETTER]   [SEND ELECTRONICALLY]   [SAVE TO RECORD]
```

The referral letter auto-populates from the patient's EHR.
Doctor reviews, edits if needed, and prints or saves.
A copy is stored in the patient's document record.

### Admission Orders

When a patient needs to be admitted:

```
ADMISSION ORDERS — OKONKWO ADAEZE

  Admitting diagnosis: B50.0 — P. falciparum malaria, severe
  Ward: [Female Medical Ward ▼]    Bed: [Assigned by capacity module]
  
  ADMISSION ORDERS:
  
  Investigations:
  ☑ Urgent FBC, Blood film
  ☑ Blood culture x2
  ☑ RFT, LFT, Blood glucose
  ☑ Urinalysis
  
  IV Access: [IV line to be inserted immediately]
  
  Fluid Orders:
  [Normal saline 0.9% — 1L over 8 hours    ]
  
  Medications:
  [Artesunate IV 2.4mg/kg at 0, 12, 24hrs then daily   ]
  [Paracetamol 1g IV/oral TDS for fever                 ]
  
  Nursing Orders:
  [Hourly vitals monitoring. IV site care. Strict input/output chart.]
  
  Diet: [Normal ward diet — no restrictions              ]
  
  [CONFIRM ADMISSION]
```

On confirmation:
- Bed management module assigns a bed
- Capacity dashboard updates (beds available decreases by 1)
- Ward nurse receives inpatient admission notification
- Inpatient billing track begins (daily bed fees)

---

## Part 9: The ANC Module

Antenatal care is a critical area for Nigeria — maternal mortality is
one of the highest in the world. The ANC module is a structured,
purpose-built section of the EHR specifically for pregnant patients.

### The ANC Profile (Booking)

When a pregnant patient presents for first ANC visit, a full ANC profile is created:

```
ANC BOOKING — IBRAHIM FATIMA, F, 26 yrs

OBSTETRIC HISTORY:
  LMP (Last Menstrual Period): [15 Jun 2026]
  EDD (Estimated Delivery Date): [22 Mar 2027] ← auto-calculated (Naegele's rule)
  Gestational Age Today: [11 weeks + 2 days]   ← auto-calculated
  
  Gravida (total pregnancies): [2]
  Para (deliveries ≥24 weeks): [1]   Previous living children: [1]
  Previous miscarriage/abortion: [0]
  Previous CS: [No]    Previous complications: [None]
  
PARTNER INFORMATION:
  Partner name: [Ibrahim Musa]   Partner phone: [08071234567]
  Sickle cell status partner: [AS]

BASELINE INVESTIGATIONS (ordered at booking):
  ☑ Blood group & Rhesus factor
  ☑ Full Blood Count (anaemia screening)
  ☑ HIV rapid test (PMTCT programme)
  ☑ VDRL/RPR (syphilis)
  ☑ Hepatitis B surface antigen
  ☑ Sickle cell genotype
  ☑ Random blood sugar
  ☑ Urinalysis + microscopy
  ☑ Ultrasound scan (dating)    Target: within 2 weeks

BASELINE VITALS: [from today's triage — pre-populated]
  BP: 118/76  Wt: 61kg  Height: 162cm  BMI: 23.2

FIRST INTERVENTIONS:
  ☑ Folic acid 5mg daily (to be continued until 12 weeks)
  ☑ Iron 200mg daily (from 14 weeks)
  ☑ IPTp — SP (Fansidar) — first dose from 13 weeks
  ☑ Tetanus Toxoid vaccination schedule started

RISK FLAGS (auto-calculated + manual):
  ○ None identified at this visit
  (Would auto-flag: age <18 or >35, previous CS, twins, etc.)

ANC VISIT SCHEDULE (auto-generated, 8 contacts minimum):
  Contact 1:  <12 wks  — TODAY ✅
  Contact 2:  20 wks   — ~Oct 2026
  Contact 3:  26 wks   — ~Dec 2026
  Contact 4:  30 wks   — ~Jan 2027
  Contact 5:  34 wks   — ~Feb 2027
  Contact 6:  36 wks   — ~Mar 2027
  Contact 7:  38 wks   — ~Mar 2027
  Contact 8:  40 wks   — ~Mar 2027
  
  [System will SMS appointment reminders 1 week before each contact]
```

### Subsequent ANC Visits

Each follow-up ANC visit has a structured quick-assessment form:

```
ANC CONTACT 2 — IBRAHIM FATIMA — 20 Weeks

  Gestational Age: 20 weeks  |  Weight: 64kg (+3kg from booking ✓)

  CLINICAL ASSESSMENT:
  BP: [118/74] mmHg              → Normal ✓
  Fundal Height: [20] cm         → Consistent with dates ✓
  Fetal Heart Rate: [148] bpm    → Normal ✓
  Fetal Presentation: [Cephalic] → Expected at 20 weeks
  Fetal Movement felt: [Yes]
  Oedema: [Nil]
  
  INTERVENTIONS DUE THIS VISIT:
  ☑ IPTp-SP (Fansidar 3 tabs) — given today (1st dose)
  ☑ Iron + Folic acid — continued
  ☑ Deworming (Mebendazole) — safe after 1st trimester
  
  ULTRASOUND RESULTS (if done):
  [Normal anatomy survey. Single live fetus. EDD confirmed.]
  
  COUNSELLING DONE:
  ☑ Danger signs (bleeding, severe headache, visual changes, reduced fetal movement)
  ☑ Nutrition in pregnancy
  ☑ Birth preparedness plan
  
  NEXT VISIT: 26 weeks (~14 Dec 2026)
  [SIGN & SAVE]
```

---

## Part 10: Paediatric Module

### Growth Monitoring

Every under-5 visit includes a growth assessment:

```
GROWTH RECORD — AMARA CHUKWU, F, 18 months

  Weight:    [9.8] kg    WHO Z-score: -0.8  → Normal ✓
  Height:    [78] cm     Z-score: -0.6      → Normal ✓
  MUAC:      [14.5] cm                      → Normal ✓
  Head Circ: [46] cm

  GROWTH TREND (last 4 visits):
  
  Age (months)  Weight   WAZ     HAZ    Trend
  ────────────────────────────────────────────
  6             6.2 kg   -0.5   -0.4    ✓
  9             7.1 kg   -0.6   -0.5    ✓
  12            8.3 kg   -0.7   -0.6    ✓
  18            9.8 kg   -0.8   -0.6    → Stable, normal range
  
  ✓ No evidence of acute or chronic malnutrition
```

Flags automatically when Z-score < -2 (moderate) or < -3 (severe malnutrition).

### Immunization Record

```
IMMUNIZATION RECORD — AMARA CHUKWU, F, 18 months

  NIGERIAN IMMUNIZATION SCHEDULE:

  Vaccine            Age Due    Date Given  Batch No.  Next Due
  ─────────────────────────────────────────────────────────────
  BCG + OPV0        Birth       3 Jan 2025  LOT-2401   —
  Penta 1+OPV1+PCV1 6 weeks     14 Feb 2025 LOT-2403   —
  Penta 2+OPV2+PCV2 10 weeks    14 Mar 2025 LOT-2405   —
  Penta 3+OPV3+PCV3 14 weeks    11 Apr 2025 LOT-2407   —
  OPV4+MCV1+YF+Men A 9 months   3 Oct 2025  LOT-2502   —
  Vit A              12 months   3 Jan 2026  —          —
  Vit A (2nd dose)   18 months   ⚠ DUE TODAY            ←
  MCV2               15–18 mths  ⚠ DUE THIS VISIT       ←
  
  ⚠ 2 VACCINES DUE TODAY — please administer and record
  
  [RECORD GIVEN]
```

When vaccines are given and recorded:
- Stock decremented in inventory module
- Next due date calculated and displayed
- SMS reminder scheduled to parent's phone

---

## Part 11: Chronic Disease Management

For patients with long-term conditions (hypertension, diabetes, HIV, sickle cell),
the EHR has a longitudinal management view:

```
CHRONIC DISEASE PANEL — BELLO YUSUF

  ┌─ HYPERTENSION ─────────────────────────────────────────────────┐
  │ Target BP: <130/80 mmHg                                        │
  │                                                                │
  │  Jun 2025  Aug 2025  Oct 2025  Dec 2025  Mar 2026  Jun 2026   │
  │  148/94    142/90    135/88    131/82    128/80    133/86      │
  │     ⚠         ⚠         ⚠         ✓         ✓         ✓      │
  │                                                                │
  │ Current medications: Amlodipine 5mg OD, Lisinopril 5mg OD    │
  │ Last medication change: Mar 2025 (added Lisinopril)           │
  └────────────────────────────────────────────────────────────────┘

  ┌─ TYPE 2 DIABETES ──────────────────────────────────────────────┐
  │ Target HbA1c: <7.0%                                            │
  │                                                                │
  │  Mar 2025  Jun 2025  Sep 2025  Dec 2025  Mar 2026  Jun 2026   │
  │  7.8%      8.0%      7.9%      8.4%      8.1%      8.2%      │
  │   ⚠         ⚠         ⚠         ⚠         ⚠         ⚠       │
  │                                                                │
  │ ⚠ CONSISTENTLY ABOVE TARGET — Consider intensification       │
  │ Current Rx: Metformin 500mg BD                               │
  │ Suggestion: Add Glibenclamide 2.5mg OD or refer to endocrine │
  └────────────────────────────────────────────────────────────────┘
```

The system doesn't make the clinical decision — but it presents
the trend data clearly so the doctor can't miss a pattern
that paper records would never reveal.

---

## Part 12: Document Management

Patients arrive with physical documents: old lab results from another hospital,
X-rays, referral letters, insurance pre-auth forms. AraCare handles these:

### Upload at Reception or Doctor's Room

```
  Document type: [External Lab Report ▼]
  Visit date on doc: [15 Aug 2026]
  Upload: [📷 Take Photo with Webcam]  [📁 Upload File]
  
  Description: [Hepatitis B panel from Diamond Lab, Ikeja]
```

On upload:
- Document stored in encrypted object storage (e.g., AWS S3 or local storage)
- **OCR runs automatically** → extracts text from the image/PDF
- Extracted text is indexed for search
- Key values (e.g., HBsAg: Reactive) are flagged for clinician review
- Document linked to patient's record and this visit

### X-Ray and Imaging

```
  UPLOADED: Chest X-Ray — 29 Aug 2026
  
  [View Full Image]
  
  AI Annotation (Phase 3 — future):
  → System highlights region of interest
  → "Possible haziness in right lower lobe — review recommended"
  → Radiologist must confirm before this appears in record
  
  Current phase: Upload + storage + OCR only
  Radiologist adds report manually as a note
```

---

## Part 13: FHIR Interoperability

All clinical data in AraCare is stored in **HL7 FHIR R4 format** internally.
This means:

| FHIR Resource | What It Stores in AraCare |
|--------------|--------------------------|
| `Patient` | Patient demographics and identifiers |
| `Encounter` | Each visit/episode of care |
| `Condition` | Diagnoses (linked to ICD-10 codes) |
| `Observation` | Vitals, lab results, assessment findings |
| `MedicationRequest` | Prescriptions ordered |
| `MedicationDispense` | Pharmacy dispensing events |
| `DiagnosticReport` | Lab reports |
| `ServiceRequest` | Lab and imaging orders |
| `DocumentReference` | Uploaded documents, OCR text |
| `AllergyIntolerance` | Patient allergy records |
| `ImmunizationRecord` | Vaccination history |
| `CarePlan` | ANC schedule, chronic disease management plans |

**Why FHIR matters for Nigeria:**
- When a patient is referred to LUTH, they can receive a FHIR bundle of the patient's record
- When HMO systems become more sophisticated, claim data can be shared in standard format
- When Nigeria implements a national health record (future), AraCare connects without re-building
- Lab systems that support FHIR can send results directly into AraCare

**In Phase 1:** FHIR used internally for data modelling.
**In Phase 2:** FHIR API exposed for lab system integration.
**In Phase 3:** FHIR for cross-facility patient record sharing.

---

## Part 14: The Data Models

```sql
-- Clinical note (one per visit encounter — the SOAP note)
clinical_notes (
  id                UUID PRIMARY KEY,
  visit_id          UUID REFERENCES visits(id),
  patient_id        UUID REFERENCES patients(id),
  note_type         ENUM('soap','nursing','procedure','discharge_summary',
                         'referral_note','anc_visit'),
  template_used     VARCHAR,             -- e.g., 'MALARIA_UNCOMPLICATED'
  status            ENUM('draft','signed','amended'),
  subjective        TEXT,
  objective         TEXT,
  assessment        TEXT,
  plan              TEXT,
  authored_by       UUID NOT NULL,      -- doctor/nurse staff_id
  signed_at         TIMESTAMP,
  signed_by         UUID,
  amendment_reason  TEXT,               -- if amended after signing
  amended_at        TIMESTAMP
)

-- Diagnoses (ICD-10 coded)
diagnoses (
  id                UUID PRIMARY KEY,
  visit_id          UUID,
  patient_id        UUID REFERENCES patients(id),
  clinical_note_id  UUID REFERENCES clinical_notes(id),
  icd10_code        VARCHAR NOT NULL,   -- e.g., 'B50.9'
  icd10_description VARCHAR NOT NULL,
  diagnosis_type    ENUM('primary','secondary','complication',
                         'chronic_review','differential'),
  status            ENUM('active','resolved','chronic','ruled_out'),
  diagnosed_by      UUID NOT NULL,
  diagnosed_at      TIMESTAMP NOT NULL,
  resolved_at       TIMESTAMP
)

-- Patient problem list (permanent active conditions)
problem_list (
  id                UUID PRIMARY KEY,
  patient_id        UUID REFERENCES patients(id),
  diagnosis_id      UUID REFERENCES diagnoses(id),
  icd10_code        VARCHAR NOT NULL,
  condition_name    VARCHAR NOT NULL,
  status            ENUM('active','inactive','resolved'),
  onset_date        DATE,
  resolution_date   DATE,
  managing_doctor   UUID
)

-- Vitals (from triage or bedside monitoring)
vitals (
  id                UUID PRIMARY KEY,
  visit_id          UUID REFERENCES visits(id),
  patient_id        UUID REFERENCES patients(id),
  recorded_by       UUID NOT NULL,
  recorded_at       TIMESTAMP NOT NULL,
  source            ENUM('triage','bedside','monitoring_device','manual'),
  bp_systolic       INTEGER,
  bp_diastolic      INTEGER,
  pulse_rate        INTEGER,
  respiratory_rate  INTEGER,
  temperature       DECIMAL(4,1),
  temperature_route ENUM('oral','axillary','tympanic','rectal'),
  spo2              INTEGER,
  weight_kg         DECIMAL(5,2),
  height_cm         DECIMAL(5,1),
  bmi               DECIMAL(4,1),         -- computed
  blood_glucose     DECIMAL(5,1),
  gcs_score         INTEGER,              -- Glasgow Coma Scale
  pain_score        INTEGER,              -- 0–10
  muac_cm           DECIMAL(4,1),         -- for paediatrics
  notes             TEXT
)

-- Lab orders
lab_orders (
  id                UUID PRIMARY KEY,
  visit_id          UUID REFERENCES visits(id),
  patient_id        UUID REFERENCES patients(id),
  journey_step_id   UUID,
  ordered_by        UUID NOT NULL,
  test_code         VARCHAR NOT NULL,
  test_name         VARCHAR NOT NULL,
  panel_tests       TEXT[],             -- for panels: ['Hb', 'WBC', 'Plt']
  priority          ENUM('routine','urgent','stat'),
  clinical_notes    TEXT,
  specimen_type     VARCHAR,
  status            ENUM('ordered','specimen_collected','processing',
                         'resulted','verified','cancelled'),
  ordered_at        TIMESTAMP NOT NULL,
  collected_at      TIMESTAMP,
  resulted_at       TIMESTAMP,
  verified_at       TIMESTAMP,
  resulted_by       UUID,
  verified_by       UUID
)

-- Lab results
lab_results (
  id                UUID PRIMARY KEY,
  lab_order_id      UUID REFERENCES lab_orders(id),
  parameter_name    VARCHAR NOT NULL,   -- e.g., 'Haemoglobin'
  result_value      VARCHAR NOT NULL,   -- text to handle 'Positive', numbers
  result_numeric    DECIMAL(10,3),      -- for numeric results
  unit              VARCHAR,
  reference_low     DECIMAL(10,3),
  reference_high    DECIMAL(10,3),
  interpretation    ENUM('normal','low','high','critical_low',
                         'critical_high','positive','negative','indeterminate'),
  notes             TEXT,
  resulted_at       TIMESTAMP NOT NULL
)

-- Medication orders (prescriptions)
medication_orders (
  id                UUID PRIMARY KEY,
  visit_id          UUID REFERENCES visits(id),
  patient_id        UUID REFERENCES patients(id),
  ordered_by        UUID NOT NULL,
  drug_code         VARCHAR NOT NULL,
  drug_name         VARCHAR NOT NULL,     -- generic name
  brand_name        VARCHAR,
  formulation       VARCHAR,              -- tablet, syrup, injection
  dose              DECIMAL(8,2),
  dose_unit         VARCHAR,              -- mg, mL, IU, tabs
  frequency         VARCHAR,              -- 'twice daily', 'every 8 hours'
  route             ENUM('oral','iv','im','sc','topical','inhaled','rectal'),
  duration_days     INTEGER,
  quantity_to_dispense INTEGER,
  is_generic        BOOLEAN DEFAULT TRUE,
  indication        VARCHAR,              -- brief clinical reason
  special_instructions TEXT,
  status            ENUM('ordered','sent_to_pharmacy','dispensed',
                         'partially_dispensed','cancelled'),
  dispensed_quantity INTEGER,
  ordered_at        TIMESTAMP NOT NULL,
  dispensed_at      TIMESTAMP
)

-- Allergy records
allergy_records (
  id                UUID PRIMARY KEY,
  patient_id        UUID REFERENCES patients(id),
  allergen_type     ENUM('drug','food','environmental','latex','other'),
  allergen_name     VARCHAR NOT NULL,
  drug_class        VARCHAR,             -- e.g., 'penicillin', 'sulfonamide'
  reaction          TEXT NOT NULL,
  severity          ENUM('mild','moderate','severe','anaphylaxis'),
  verified          BOOLEAN DEFAULT FALSE,
  recorded_by       UUID NOT NULL,
  recorded_at       TIMESTAMP NOT NULL
)

-- Referral orders
referral_orders (
  id                UUID PRIMARY KEY,
  visit_id          UUID REFERENCES visits(id),
  patient_id        UUID REFERENCES patients(id),
  referred_by       UUID NOT NULL,
  referral_type     ENUM('internal','external'),
  to_department     VARCHAR,            -- internal
  to_facility       VARCHAR,            -- external
  to_specialty      VARCHAR,
  urgency           ENUM('routine','urgent','emergency'),
  reason            TEXT NOT NULL,
  clinical_summary  TEXT,
  status            ENUM('ordered','sent','acknowledged','seen','completed'),
  ordered_at        TIMESTAMP NOT NULL,
  acknowledged_at   TIMESTAMP,
  completed_at      TIMESTAMP
)

-- ANC profile (one per pregnancy)
anc_profiles (
  id                UUID PRIMARY KEY,
  patient_id        UUID REFERENCES patients(id),
  facility_id       UUID NOT NULL,
  lmp               DATE NOT NULL,
  edd               DATE NOT NULL,         -- auto-calculated
  gravida           INTEGER NOT NULL,
  para              INTEGER NOT NULL,
  previous_cs       BOOLEAN DEFAULT FALSE,
  previous_complications TEXT,
  partner_sickle_cell VARCHAR,
  blood_group       VARCHAR,
  rhesus_factor     ENUM('positive','negative','unknown'),
  hiv_status        ENUM('negative','positive','unknown','not_tested'),
  sickle_cell_status VARCHAR,
  risk_level        ENUM('low','moderate','high'),
  risk_flags        TEXT[],
  outcome           ENUM('ongoing','delivered','miscarriage','stillbirth',
                         'ectopic','transferred'),
  delivery_date     DATE,
  delivery_mode     ENUM('svd','cs','assisted'),
  booking_date      DATE NOT NULL,
  created_by        UUID NOT NULL
)

-- ANC visits (one per contact — 8 minimum)
anc_visits (
  id                UUID PRIMARY KEY,
  anc_profile_id    UUID REFERENCES anc_profiles(id),
  visit_id          UUID REFERENCES visits(id),
  contact_number    INTEGER NOT NULL,     -- 1 through 8+
  gestational_age_weeks INTEGER,
  weight_kg         DECIMAL(5,2),
  bp_systolic       INTEGER,
  bp_diastolic      INTEGER,
  fundal_height_cm  DECIMAL(4,1),
  fetal_heart_rate  INTEGER,
  presentation      VARCHAR,
  fetal_movement    BOOLEAN,
  oedema            ENUM('none','mild','moderate','severe'),
  urine_protein     ENUM('negative','trace','1plus','2plus','3plus'),
  iptp_given        BOOLEAN DEFAULT FALSE,
  iptp_dose_number  INTEGER,
  tt_given          BOOLEAN DEFAULT FALSE,
  tt_dose_number    INTEGER,
  iron_folate_given BOOLEAN DEFAULT FALSE,
  counselling_done  TEXT[],
  next_visit_date   DATE,
  notes             TEXT,
  attended_by       UUID NOT NULL,
  visit_date        DATE NOT NULL
)

-- Growth records (paediatric)
growth_records (
  id                UUID PRIMARY KEY,
  patient_id        UUID REFERENCES patients(id),
  visit_id          UUID REFERENCES visits(id),
  recorded_at       DATE NOT NULL,
  age_months        INTEGER,
  weight_kg         DECIMAL(5,2),
  height_cm         DECIMAL(5,1),
  head_circumference_cm DECIMAL(4,1),
  muac_cm           DECIMAL(4,1),
  waz               DECIMAL(4,2),       -- weight-for-age Z-score
  haz               DECIMAL(4,2),       -- height-for-age Z-score
  whz               DECIMAL(4,2),       -- weight-for-height Z-score
  nutritional_status ENUM('normal','mam','sam','overweight','obese'),
  recorded_by       UUID NOT NULL
)

-- Immunization records
immunization_records (
  id                UUID PRIMARY KEY,
  patient_id        UUID REFERENCES patients(id),
  visit_id          UUID REFERENCES visits(id),
  vaccine_name      VARCHAR NOT NULL,
  dose_number       INTEGER,
  administered_at   DATE NOT NULL,
  administered_by   UUID NOT NULL,
  lot_number        VARCHAR,
  site              VARCHAR,            -- left deltoid, right thigh, etc.
  next_due_date     DATE,
  notes             TEXT
)

-- Uploaded documents
patient_documents (
  id                UUID PRIMARY KEY,
  patient_id        UUID REFERENCES patients(id),
  visit_id          UUID,
  document_type     ENUM('lab_report','imaging','referral_letter',
                         'consent_form','insurance_doc','other'),
  description       VARCHAR,
  file_url          VARCHAR NOT NULL,   -- encrypted storage path
  file_type         VARCHAR,            -- pdf, jpg, png, dcm
  file_size_bytes   INTEGER,
  ocr_text          TEXT,              -- extracted text
  uploaded_by       UUID NOT NULL,
  uploaded_at       TIMESTAMP NOT NULL
)

-- Audit log (every view of sensitive records)
ehr_audit_log (
  id                UUID PRIMARY KEY,
  patient_id        UUID NOT NULL,
  record_type       VARCHAR NOT NULL,   -- 'clinical_note', 'lab_result', etc.
  record_id         UUID NOT NULL,
  action            ENUM('view','create','edit','sign','print','export'),
  performed_by      UUID NOT NULL,
  performed_at      TIMESTAMP NOT NULL,
  ip_address        VARCHAR,
  device_info       VARCHAR
)
```

---

## Summary: Key Design Decisions

| Decision | Choice | Reason |
|---------|--------|--------|
| Note format | SOAP with structured fields | International standard, Nigerian training uses it |
| Clinical templates | Pre-built for top Nigerian diagnoses | Speed — 30–80 patients/day requires it |
| Allergy alerts | Hard block for allergy conflicts | Patient safety — non-negotiable |
| Drug catalogue | NEML + NAFDAC Greenbook | Nigeria-specific, clinically appropriate |
| Paediatric dosing | Weight-based auto-calculator | Prevents dosing errors in under-5s |
| Lab results | Routed back to ordering doctor | Closes the loop — no missed results |
| ANC | 8-contact WHO schedule, structured form | Nigerian maternal mortality context |
| ICD-10 coding | Required on every diagnosis | HMO claim requirement |
| Interoperability | FHIR R4 internally | Future-proof, enables data sharing |
| Document handling | Upload + OCR + structured storage | Replaces the physical folder completely |
| Audit logging | Every record access logged | NDPA 2023 compliance |
| Role-based views | Distinct workstations per role | Correct information, correct person, correct time |
| Chronic disease | Longitudinal trend panels | Patterns visible that paper records hide |
| Offline | All workstations work without internet | Nigerian infrastructure reality |
