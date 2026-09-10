# AraCare — Patient Registration & Check-In
### Deep Dive: New Patients, Returning Patients, Identification & Data Policy

---

## The Core Philosophy

> In Nigeria, the hospital card IS the patient's identity. AraCare replaces the
> physical card with something better — but never removes the *feeling* of having
> a card. People trust what they can hold, show, or reference.

The design goal:
- **Minimal physical objects** — no expensive NFC cards by default
- **Phone number is the primary key** — works on any phone, any network
- **Face photo is the silent identifier** — staff can visually confirm without asking
- **WhatsApp/SMS delivers the "digital card"** — everyone has it, it never gets lost
- **Fallback for everything** — because Nigeria

---

## Part 1: The New Patient

### Who is a "new patient"?

Someone who has never been registered in this hospital's AraCare system before.
They walk up to the reception desk, usually with no prior hospital record here.

They may:
- Have records in another hospital (no integration yet — Phase 3 problem)
- Have an NHIA/HMO card from their employer
- Be completely uninsured (majority)
- Be unconscious/unable to speak (emergency path — different flow)
- Be a child brought by a parent/guardian
- Be elderly and illiterate
- Be a sophisticated Lagos professional with a smartphone

The registration system must handle all of these.

---

### Step 1: The "Card" Payment — Digitized

Currently a patient walks up and pays ₦200–500 for a physical card. This has two purposes:
1. **Revenue** for the hospital
2. **Identity token** for the patient

In AraCare, the payment still happens — but what they receive is different.

**What they pay for → What they now get:**

| Old System | AraCare |
|-----------|---------|
| ₦200–500 cash for physical card | ₦300–800 registration fee (same ballpark) |
| Physical card with handwritten number | Permanent digital patient profile (Patient ID) |
| A paper folder created in back office | A digital medical record, ready from day one |
| Card easy to lose, damage, fade | Identity tied to phone number and face — can never be "lost" |

The fee is configurable per hospital. The point is: **they're paying for their permanent digital identity in this hospital**, not for a piece of plastic.

---

### Step 2: What Information Do We Collect?

We collect in **three tiers** — mandatory, recommended, and progressive (collected over visits).

#### Tier 1: MANDATORY (Can't proceed without these)

| Field | Why It's Mandatory | Notes |
|-------|------------------|-------|
| **Full Name** | Primary identifier | Surname + First + Middle (optional) |
| **Phone Number** | The digital card. The universal key. | Can be guardian's for children/elderly |
| **Date of Birth** | Differentiates patients with same name | Even approximate year is acceptable |
| **Gender** | Clinical relevance (dosing, conditions, ANC routing) | Male / Female / Other |
| **Patient Category** | Routes them to correct queue and billing | Adult / Child (u-18) / Infant |

> That's it for mandatory. 5 fields. A receptionist should complete this in under 60 seconds.
> Everything else is collected progressively. Don't make registration a 10-minute interview.

#### Tier 2: RECOMMENDED (Collect now if patient is cooperative)

| Field | Why Important | Notes |
|-------|--------------|-------|
| **Next of Kin Name** | Emergency contact | Especially critical for elderly/minors |
| **Next of Kin Phone** | Emergency contact | Different from patient's number |
| **State / LGA of Origin** | Disease surveillance, epidemiology | Not address — just state |
| **NHIA/HMO Number** | Billing routing — major operational impact | Check their HMO card if they have one |
| **HMO Provider** | Determines which billing track applies | Dropdown of registered HMOs |
| **Known Allergies** | Patient safety — critical if they get admitted | Penicillin, sulfa drugs, etc. |
| **Blood Group** | Emergency situations | If they know it |

#### Tier 3: PROGRESSIVE (Collected on first clinical visit, not at reception)

These are collected by the nurse/doctor during triage or consultation — not by the receptionist:

- Chronic conditions (hypertension, diabetes, asthma, HIV status)
- Current medications
- Past surgeries
- Family medical history
- Alcohol/tobacco use
- Pregnancy status (if applicable)
- Immunization history (especially for children)

> Receptionists are administrative staff. They should not be asking about HIV status or
> chronic conditions. That is a clinical conversation, done in private with a nurse.

---

### Step 3: The Photo — Yes, Take It. Here's How.

**Should we take a patient photo?** Yes. Strongly recommend it. Here's why:

1. **Staff recognition** — When "Adaeze Okonkwo OPD-045" is called, the nurse sees Adaeze's face on their tablet. They can spot her in the waiting room immediately.
2. **Identity verification** — A family member can't collect results/medication using someone else's ID if the photo doesn't match.
3. **Unconscious patient** — If someone collapses and is brought in, their face can be matched against the database to pull their medical history instantly.
4. **No-card fallback** — Patient forgets their phone, can't remember their number. Receptionist takes their photo → matches against database → identity confirmed.
5. **Fraud prevention** — Stops people from sharing "cards" (a real problem with HMO abuse in Nigeria).

**How to capture it:**
- Webcam attached to the reception desk computer (cheap USB webcam, ₦5,000–₦15,000)
- Tablet front camera at the self-service kiosk (if it exists)
- Receptionist takes it in under 5 seconds: patient faces camera, receptionist clicks "Capture"
- Photo appears on screen for patient to see and approve ("Is this okay?")

**What it's NOT:**
- Not real-time facial recognition scanning a crowd
- Not used for surveillance
- Not shared outside the hospital
- Not sold or used for any purpose except patient identification within AraCare

**Consent handling (NDPA 2023 compliance):**

Before capture, screen shows (or receptionist reads aloud):

> "We would like to take your photo to help identify you on future visits
> and improve your safety if you ever need emergency care. Your photo will
> be stored securely and only used by this hospital's staff.
> Do you agree?"

Patient's choice is recorded with timestamp in the database. If they say No:
- Registration continues normally
- Phone number + name become the primary identifiers
- They'll be asked again on next visit (consent can change)
- A small icon appears on their profile so staff know not to ask why there's no photo

---

### Step 4: What Do They Leave With? (The "Digital Card")

No physical card required. Here's what the patient gets:

#### Option A: SMS (works on ALL phones, even basic Nokia)
```
Your AraCare Patient ID: ARC-LAG-2026-004521
Name: OKONKWO ADAEZE
Hospital: General Hospital Ikeja

Show this message or give your phone number at reception on your next visit.
Save this message. Do not share your Patient ID with others.
```

#### Option B: WhatsApp (if they have it)
- Text version of their Patient ID
- QR code image they can screenshot and keep
- Hospital name and instructions
- They can screenshot the QR code. On next visit: show phone, scan QR, done.

#### Option C: Printed Paper Slip (for patients who want something physical)
A small receipt (thermal printer — already in most hospitals, ₦2 per slip):
```
┌──────────────────────────────┐
│  GENERAL HOSPITAL IKEJA      │
│  PATIENT REGISTRATION SLIP   │
├──────────────────────────────┤
│  Name: OKONKWO ADAEZE        │
│  ID:   ARC-LAG-2026-004521   │
│  DOB:  12/03/1995            │
│  Date: 29/08/2026            │
│                              │
│  [QR CODE HERE]              │
│                              │
│  Keep this slip or give your │
│  phone number at reception.  │
└──────────────────────────────┘
```

This is NOT a card. It's a receipt. But it gives patients the psychological
comfort of having "something."

#### Option D: Optional NFC Card (premium, at extra cost)
For patients who specifically ask for a physical card (e.g., elderly patients who won't use phones):
- Hospital can offer an NFC card for an extra fee (₦500–₦1,500)
- The card stores ONLY the Patient ID — nothing medical on the card itself
- Medical data stays in the database; card is just a key
- Make this optional and charged separately — not the default

---

### Step 5: The Patient ID Format

```
ARC - [STATE] - [YEAR] - [SEQUENCE]

Example: ARC-LAG-2026-004521
```

| Part | Meaning | Example |
|------|---------|---------|
| `ARC` | AraCare system prefix | Fixed |
| `LAG` | State code (Lagos, ABJ, KAN, PH, etc.) | 3-letter state code |
| `2026` | Year of first registration | Auto-generated |
| `004521` | Sequential number at that facility | Zero-padded to 6 digits |

This ID is **permanent and never changes**, even if the patient:
- Changes their phone number (they update it in system, ID stays)
- Moves to another hospital using AraCare (their record can follow — future phase)
- Loses their slip/card

---

### Step 6: Patients Without Phones

| Patient Type | Solution |
|-------------|---------|
| **Child (under ~10)** | Register with parent/guardian's phone number. Mark as "child account linked to guardian." |
| **Elderly patient with no phone** | Use next of kin's phone number. Flag account as "NOK contact preferred." |
| **Patient with a basic (non-smart) phone** | SMS still works. QR not useful, but SMS with the Patient ID is enough. |
| **Patient with no phone at all** | Give the printed receipt slip. They bring it next visit. Optional NFC card for these patients. |
| **Emergency patient (unconscious, no ID)** | Create temporary "Unknown Patient" record. Assign temp ID (UNK-0001). Staff collect ID after stabilization. Record merged with proper account once identified. |

> Never refuse to register a patient because they don't have a phone.
> The printed receipt is always the final fallback.

---

## Part 2: The Returning Patient

### What Do They Need to Show?

Multiple options, checked in order of convenience:

```
Priority 1 (fastest): Show QR code on phone → Scan → Done (3 seconds)
Priority 2: Tap NFC card on reader → Done (2 seconds)
Priority 3: Give phone number → Receptionist types it → Profile found (10 seconds)
Priority 4: Give Patient ID verbally (ARC-LAG-2026-004521) → Look up (15 seconds)
Priority 5: Give full name + DOB → Search narrows down (20-30 seconds)
Priority 6: Face photo matching (if enrolled) → Camera snap → Auto-match (10 seconds)
```

The system shows **partial matches** when searching by name — not exact spelling required.
"Adeola Balogun" and "Adaeze Balogun" both appear in a search for "Balogun".
Nigerian names have many spelling variants. Build for fuzzy matching.

---

### The Returning Patient Check-In Screen

```
┌─────────────────────────────────────────────────────────────┐
│  OKONKWO ADAEZE                          [Photo thumbnail]  │
│  ID: ARC-LAG-2026-004521   |  DOB: 12 Mar 1995 (31 yrs)   │
│  Phone: 0803xxxxx90         |  Gender: Female               │
│  Last Visit: 14 Aug 2026    |  HMO: No                     │
│  Known Allergy: Penicillin                                  │
│                                                             │
│  [CHECK IN FOR NEW VISIT]  [VIEW HISTORY]  [UPDATE INFO]   │
└─────────────────────────────────────────────────────────────┘
```

Receptionist confirms it's the right person (photo + name verbal confirm),
clicks "Check In for New Visit", selects visit reason, done.
**Entire process: under 20 seconds.**

---

### Returning Patient Fee Structure

| Fee Type | Amount | What It Covers |
|---------|--------|---------------|
| Registration fee (new) | ₦500–₦1,000 | One-time, creates permanent profile |
| Consultation/revisit fee | ₦200–₦500 | Per visit, queue assignment + admin |
| Follow-up fee (within 7 days) | ₦0–₦200 | Discounted — coming back for results |
| HMO visit | ₦0 cash | System generates HMO claim automatically |

---

### Information Update Prompt (every returning visit)

```
QUICK UPDATE CHECK — OKONKWO ADAEZE

Has any of the following changed?
[ ] Phone number       [ ] Address
[ ] Next of kin        [ ] HMO/Insurance status
[ ] Known allergies

[NO CHANGES — PROCEED]  [UPDATE DETAILS]
```

This is how records stay accurate over time without slowing down check-in.

---

## Part 3: Data Storage & NDPA 2023 Compliance

### The Three-Vault Model

Patient data is NOT all the same. We store it in three logical vaults with different access levels.

```
VAULT 1 — IDENTITY DATA (Administrative)
  Who can see:  Reception, Admin, All clinical staff
  Fields:       Name, Phone, DOB, Gender, Patient ID, HMO number
  Encryption:   AES-256 at rest, TLS in transit
  Retention:    Lifetime of record (minimum 10 years)

VAULT 2 — MEDICAL RECORDS (Clinical)
  Who can see:  Doctors, Nurses, Lab, Pharmacy (role-specific views)
  Fields:       Diagnoses, prescriptions, lab results, vitals, notes
  Encryption:   AES-256 at rest, TLS in transit
  Retention:    Min 10 years (adult), until age 25 (children), 20 yrs (psychiatric)

VAULT 3 — BIOMETRIC DATA (Most Sensitive)
  Who can see:  Reception (for ID), Senior clinical staff only
  Fields:       Patient photo, fingerprint hash (if collected)
  Encryption:   AES-256 at rest, separate encryption key from Vault 1 and 2
  Retention:    Until consent withdrawal or account deletion
  Special:      Consent record stored separately with timestamp
```

---

### NDPA 2023 Compliance Requirements

**1. Consent Management — Every consent is an immutable record**

```
patient_consents table:
  id               → UUID
  patient_id       → UUID (FK)
  consent_type     → ENUM: photo, sms_marketing, data_sharing, research
  granted          → BOOLEAN
  granted_at       → TIMESTAMP
  withdrawn_at     → TIMESTAMP (null if still active)
  method           → ENUM: verbal_confirmed, written, digital_signature
  recorded_by      → staff_id UUID
```

When a patient withdraws consent, a new record is created — the old one is NEVER deleted.
This audit trail is what protects AraCare legally.

**2. Data Minimization by Role**
- Receptionist: sees Vault 1 only (name, phone, ID)
- Lab staff: sees the test ordered + result fields only — not full medical history
- Pharmacy: sees the prescription — not the diagnosis that led to it
- Treating doctor: sees all three vaults for their assigned patients

**3. Right to Access**
Patient can request full export of all their data:
- Triggered by request to hospital admin
- System generates PDF report of everything stored
- Delivered within 30 days (NDPA requirement)

**4. Right to Erasure (with medical record caveat)**
Cannot delete clinical records needed for litigation or continuity of care.
AraCare handles this by:
- Deleting biometric data (photo) immediately on request
- Anonymizing identity data (replacing name/phone with "DELETED-004521")
- Retaining the medical record structure — the clinical history exists but is
  disconnected from any identifiable person

**5. Data Breach Response**
NDPA requires notification within 72 hours of a breach.
AraCare must have:
- Automated anomaly detection (unusual bulk data access)
- Clear escalation procedure built into admin dashboard
- Template breach notification letter pre-drafted

**6. Data Protection Officer (DPO)**
Any hospital processing 1,000+ patients per 6 months must appoint a DPO.
AraCare admin dashboard includes:
- DPO assignment and contact management
- Annual data protection audit report (auto-generated)
- NDPC registration status tracking

---

### Data Retention Policy — AraCare Defaults

| Data Type | Retention Period | Basis |
|-----------|----------------|-------|
| Patient identity record | 10 years after last visit | International best practice |
| Clinical/medical records | 10 years after last visit | International best practice |
| Children's records | Until age 25 (18 + 7 years) | Child protection standard |
| Psychiatric/HIV records | 20 years | Higher sensitivity, longer liability |
| Billing/financial records | 7 years | Nigerian tax/financial law |
| Biometric (photo) | Until consent withdrawal | NDPA strict consent requirement |
| Audit logs | 5 years | Compliance and forensics |
| Anonymized records | Indefinitely | No personal data remaining |

---

### Core Database Schema

```sql
-- Core patient identity (Vault 1)
patients (
  id                UUID PRIMARY KEY,
  facility_id       UUID NOT NULL,
  patient_number    VARCHAR UNIQUE,        -- ARC-LAG-2026-004521
  surname           VARCHAR NOT NULL,
  first_name        VARCHAR NOT NULL,
  middle_name       VARCHAR,
  phone_primary     VARCHAR NOT NULL,
  phone_secondary   VARCHAR,
  date_of_birth     DATE NOT NULL,
  gender            ENUM('male','female','other') NOT NULL,
  patient_category  ENUM('adult','child','infant') NOT NULL,
  registration_date TIMESTAMP,
  is_active         BOOLEAN DEFAULT TRUE,
  created_by        UUID               -- staff_id
)

-- Emergency contacts
patient_contacts (
  id                UUID PRIMARY KEY,
  patient_id        UUID REFERENCES patients(id),
  contact_name      VARCHAR NOT NULL,
  contact_phone     VARCHAR NOT NULL,
  relationship      VARCHAR,
  is_primary_emergency BOOLEAN DEFAULT FALSE
)

-- Insurance / HMO
patient_insurance (
  id                UUID PRIMARY KEY,
  patient_id        UUID REFERENCES patients(id),
  hmo_provider      VARCHAR,
  hmo_id            VARCHAR,
  plan_type         VARCHAR,
  enrollment_date   DATE,
  expiry_date       DATE,
  is_verified       BOOLEAN DEFAULT FALSE,
  last_verified_at  TIMESTAMP
)

-- Biometrics (Vault 3 — separate access control)
patient_biometrics (
  id                UUID PRIMARY KEY,
  patient_id        UUID REFERENCES patients(id),
  photo_storage_key VARCHAR,             -- encrypted path to photo
  photo_hash        VARCHAR,             -- for duplicate detection
  consent_id        UUID,
  captured_at       TIMESTAMP,
  captured_by       UUID,               -- staff_id
  is_active         BOOLEAN DEFAULT TRUE
)

-- Consent audit trail
patient_consents (
  id                UUID PRIMARY KEY,
  patient_id        UUID REFERENCES patients(id),
  consent_type      ENUM('photo','sms_marketing','data_sharing','research'),
  granted           BOOLEAN NOT NULL,
  granted_at        TIMESTAMP NOT NULL,
  withdrawn_at      TIMESTAMP,
  method            ENUM('verbal_confirmed','written','digital_signature'),
  recorded_by       UUID               -- staff_id
)

-- Clinical summary (Vault 2 — clinical staff only)
patient_medical_summary (
  patient_id        UUID PRIMARY KEY REFERENCES patients(id),
  blood_group       VARCHAR,
  rhesus_factor     ENUM('positive','negative'),
  allergies         TEXT[],
  chronic_conditions TEXT[],
  current_medications TEXT[],
  updated_at        TIMESTAMP,
  updated_by        UUID               -- clinical_staff_id
)

-- Visit record (one per visit)
visits (
  id                UUID PRIMARY KEY,
  patient_id        UUID REFERENCES patients(id),
  facility_id       UUID NOT NULL,
  visit_date        DATE NOT NULL,
  check_in_time     TIMESTAMP,
  visit_type        ENUM('new_complaint','follow_up','anc','emergency','specialist'),
  registration_fee  DECIMAL(10,2),
  status            ENUM('checked_in','in_progress','completed','abandoned'),
  checked_in_by     UUID               -- staff_id
)
```

---

## Part 4: Nigerian Edge Cases

| Scenario | How AraCare Handles It |
|----------|----------------------|
| "I forgot my phone" | Search name + DOB + face photo match → confirm → proceed |
| "My number changed" | Verify identity via old number (partial) + DOB + photo → update number |
| Child patient | Register under parent's phone → link guardian → flag as paediatric |
| Unconscious patient | Create UNK-[date]-[seq] temp record → emergency queue instantly → merge when identified |
| Patient can't spell their name (illiteracy) | Receptionist phonetically enters it; system stores phonetic variant too |
| Duplicate records found (same person, 2 records) | Admin merge tool consolidates into one → keeps all visit history |
| Patient refuses photo | Consent = false recorded → proceed without photo → asked again next visit |
| Patient refuses phone number | Use NIN or printed receipt as sole identifier → flag account accordingly |
| HMO card present but not verified | Flag as "HMO unverified" → collect details → verify with HMO before billing |

---

## Summary: Key Design Decisions

| Decision | Choice | Reason |
|---------|--------|--------|
| Primary identifier | Phone number | Universal, never lost, works on all phones |
| Secondary identifier | Face photo (optional) | Visual confirmation, emergency ID, anti-fraud |
| Physical card | Optional NFC, extra fee | Minimal physical stuff — but respect patient psychology |
| Default "card" delivery | SMS + WhatsApp QR | 90%+ reachability, free to patient |
| Printed receipt | Always available | Final fallback, costs ₦2 |
| Registration fields (mandatory) | 5 fields only | Speed — under 60 seconds at reception |
| Clinical data collection | Nurse/doctor — not reception | Privacy + role appropriateness |
| Data storage | 3-vault model by sensitivity | NDPA compliance + practical access control |
| Consent for photo | Explicit, recorded, revocable | NDPA biometric data requirements |
| Medical record retention | 10 years minimum | No Nigerian law — use international standard |
| Patient ID format | ARC-[STATE]-[YEAR]-[SEQ] | Permanent, facility-scoped, human-readable |
