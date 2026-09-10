# AraCare — Inventory & Drug Management System
### Deep Dive: Real-Time Pharmacy, Stock Control, Cold-Chain & Anti-Pilferage Architecture

---

## 1. The Operational Ground Truth: What Breaks in Nigerian Hospital Pharmacies

In a typical Nigerian hospital, the pharmacy and medical stores represent between **40% and 60% of total cash turnover**. Yet, it is often the most vulnerable operational leak in the entire institution.

### The 6 Critical Failure Modes AraCare Eliminates

```
┌─────────────────────────────────────────────────────────────────────────┐
│ 1. THE "OUT-OF-STOCK" PARADOX                                           │
│    Patients are sent out to "buy drugs outside" at private chemist      │
│    shops because the hospital ran out of basic IV fluids, oxytocin,     │
│    or malaria ACTs. The hospital loses revenue and clinical control.   │
├─────────────────────────────────────────────────────────────────────────┤
│ 2. THE SILENT LEAK (Pilferage & Side-Pocketing)                         │
│    Packs of expensive antibiotics, surgical mesh, or injectables        │
│    "disappear" from shelves. Staff sell their own private stock         │
│    inside the hospital premises or pocket cash for off-book drugs.      │
├─────────────────────────────────────────────────────────────────────────┤
│ 3. EXPIRED DRUG LOSSES (No FEFO Enforcement)                            │
│    Storekeepers place newly delivered cartons at the front of the       │
│    shelf. Older stock at the back expires silently. Millions of Naira   │
│    in inventory are written off annually.                               │
├─────────────────────────────────────────────────────────────────────────┤
│ 4. COLD-CHAIN BREAKAGE (NEPA & Generator Gaps)                          │
│    Power cuts overnight. The pharmacy fridge warms past 8°C. Insulin,   │
│    oxytocin, and vaccines degrade. Staff don't know the temperature was │
│    exceeded and dispense ineffective biologics to patients.             │
├─────────────────────────────────────────────────────────────────────────┤
│ 5. CONTROLLED SUBSTANCES AUDIT FAILURES                                 │
│    Narcotics (Pentazocine, Morphine, Diazepam, Tramadol) logged in      │
│    ragged paper "DD Books" with missing pages, failing NAFDAC and       │
│    NDLEA statutory compliance audits.                                   │
├─────────────────────────────────────────────────────────────────────────┤
│ 6. MULTI-STORE DISCONNECTION                                            │
│    The Main Store, OPD Pharmacy, Emergency Cabinet, Theatre Store,      │
│    and Labour Ward operate as disconnected silos with no live balance.  │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Multi-Location Inventory Hierarchy

A hospital is not a single store. Inventory exists in multiple physical zones with distinct access levels and security protocols.

```
                      ┌──────────────────────────────┐
                      │    CENTRAL MEDICAL STORE     │
                      │  (Bulk warehouse / Receiving)│
                      └──────────────┬───────────────┘
                                     │  Internal Transfer (Requisition + GRN)
            ┌────────────────────────┼────────────────────────┐
            ▼                        ▼                        ▼
┌───────────────────────┐┌───────────────────────┐┌───────────────────────┐
│     OPD PHARMACY      ││  INPATIENT PHARMACY   ││   ACCIDENT & EMERGENCY│
│  (High-volume walk-in ││  (Ward unit-dose carts││     EMERGENCY CRASH   │
│   dispensing point)   ││   & discharge packs)  ││       CABINETS        │
└───────────────────────┘└───────────────────────┘└───────────────────────┘
            │                        │                        │
            ▼                        ▼                        ▼
┌───────────────────────┐┌───────────────────────┐┌───────────────────────┐
│ THEATRE / ICU STORE   ││   LABORATORY STORE    ││  VACCINE COLD STORE   │
│ (Anaesthetics, sutures││ (Reagents, test kits, ││ (Solar direct-drive   │
│  implants, blood)     ││  blood bags, tubes)   ││  monitored fridges)   │
└───────────────────────┘└───────────────────────┘└───────────────────────┘
```

### Transfer Protocol (Maker-Checker Model)
1. **Requisition:** OPD Pharmacist notices Artemether tabs running low on shelf $\rightarrow$ submits digital requisition for 50 packs from Central Store.
2. **Authorization:** Central Store Manager approves the pick list.
3. **Dispatch:** Storekeeper scans the 2D DataMatrix/Barcode of the specific batch being dispatched.
4. **Receipt Confirmation:** OPD Pharmacist scans the received carton. Stock leaves Central Store balance and enters OPD Pharmacy balance **instantaneously**. No manual ledgers.

---

## 3. Master Item & Drug Catalogue Architecture

Every item stocked by the hospital belongs to a standardized global schema aligned with the **Nigeria Essential Medicines List (NEML)** and the **NAFDAC Greenbook**.

```
Item {
  id: UUID
  sku_code: "DRG-AL-80480-TAB"
  generic_name: "Artemether + Lumefantrine"
  brand_name: "Coartem / Amatem / Lonart" (Configurable aliases)
  category: MEDICATION | CONSUMABLE | REAGENT | BIOLOGIC | MEDICAL_GAS
  formulation: TABLET | INJECTION | SYRUP | SUSPENSION | INFUSION | TOPICAL
  strength: "80mg / 480mg"
  unit_of_measure: "Tablet" | "Pack of 6" | "Vial" | "Ampoule" | "Roll"
  is_controlled_substance: BOOLEAN (Triggers Dangerous Drug Protocol)
  is_cold_chain: BOOLEAN (Triggers Temperature Monitoring Protocol)
  storage_condition: ROOM_TEMP_25C | REFRIGERATED_2_8C | FROZEN_MINUS_20C
  nafdac_nrn: "A4-1234" (NAFDAC Registration Number)
  reorder_level: 50 (Minimum threshold across all locations)
  critical_safety_stock: 20 (Absolute emergency minimum)
}
```

### Brand vs Generic Mapping in the Nigerian Context
In Nigeria, doctors frequently prescribe by brand name (e.g. *Rocephin* instead of *Ceftriaxone*, *Augmentin* instead of *Amoxicillin-Clavulanate*, *Lonart* instead of *Artemether-Lumefantrine*).
- AraCare's catalogue maps **all commercial brands** to their underlying **Generic Molecule**.
- When a doctor prescribes *Augmentin 625mg*, the pharmacist's dispensing screen shows:
  - Prescribed: *Augmentin 625mg*
  - Available Equivalents in Stock:
    - *Augmentin 625mg (GSK)* — 12 packs in stock @ ₦12,500
    - *AmoxClav 625mg (Generic/Geneith)* — 85 packs in stock @ ₦4,200
    - *Fleming 625mg (Ranbaxy)* — 40 packs in stock @ ₦6,800
- The patient can choose what fits their budget without requiring a rewritten paper prescription.

---

## 4. Real-Time Dispensing & FEFO Barcode Engine

The dispensing process is completely integrated with the patient's EHR and Billing Invoice.

```
                    ┌───────────────────────────────┐
                    │ DOCTOR SIGNS PRESCRIPTION     │
                    │ IN EHR (MedicationRequest)    │
                    └───────────────┬───────────────┘
                                    │
                                    ▼
                    ┌───────────────────────────────┐
                    │ SYSTEM RESERVES STOCK IN OPD  │
                    │ PHARMACY (Soft Reservation)   │
                    └───────────────┬───────────────┘
                                    │
                                    ▼
                    ┌───────────────────────────────┐
                    │ PHARMACIST WORKSTATION QUEUE  │
                    │ Ticket: PHARM-022 appears     │
                    └───────────────┬───────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│ PHARMACIST SCANS BATCH BARCODE AT DISPENSING DESK                      │
│                                                                        │
│ Scenario A: Correct Batch Scanned (Expires 11/2026)                    │
│   → System confirms match, updates status to "DISPENSED"              │
│                                                                        │
│ Scenario B: Pharmacist scans Batch B28 (Expires 2028), but Batch B26   │
│             (Expires 2026) is still on shelf:                          │
│   → ⚠️ FEFO VIOLATION WARNING: "Batch B26 expires in 62 days. Please   │
│     dispense from Shelf Row 3 first."                                  │
│   → Override requires explicit reason and Pharmacist PIN.              │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│ ATOMIC TRANSACTION EXECUTION:                                          │
│ 1. Stock ledger decremented by exact units dispensed.                  │
│ 2. Patient invoice line items locked & finalized.                      │
│ 3. Batch lot number linked to patient medical history (Recall Trail).  │
│ 4. Patient gets SMS: "Medications dispensed. Instructions: Take 2 tabs │
│    twice daily after food."                                            │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 5. Dangerous Drugs & Controlled Substances (NDLEA/NAFDAC Register)

For narcotics and high-abuse drugs (*Pentazocine, Morphine, Fentanyl, Pethidine, Diazepam, Tramadol, Ketamine*), standard dispensing rules are overridden by the **Digital DD Protocol**.

### The 2-Factor Witness Workflow
1. **Prescription Check:** Doctor must enter their private clinical PIN to authorize a narcotic order.
2. **Dispense Authorization:** 
   - Pharmacist enters PIN.
   - Administering Ward Nurse enters PIN at the bedside.
3. **Ampoule/Vial Waste Logging:**
   - Example: Doctor orders *Diazepam 5mg IV stat*.
   - Available ampoule size: *10mg / 2mL*.
   - The nurse administers 5mg (1mL).
   - System prompts: *"Log Discard of 5mg Remaining"*.
   - Discard must be witnessed and co-signed by a second registered nurse PIN.
4. **Statutory Report Generation:**
   - One-click export of the **NAFDAC / NDLEA Form D Annual Narcotic Return** with complete transaction hashes, patient IDs, prescribing physicians, and serial numbers.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ 🔒 CONTROLLED SUBSTANCES AUDIT LOG                                         │
├─────────────┬─────────────┬───────────┬─────────────┬───────────┬───────────┤
│ DATE/TIME   │ DRUG        │ PATIENT   │ PRESCRIBER  │ DISPENSER │ WITNESS   │
├─────────────┼─────────────┼───────────┼─────────────┼───────────┼───────────┤
│ 29/08 14:10 │ Pentazocine │ ARC-00452 │ Dr. Eze     │ Pharm Ada │ Nurse Joy │
│             │ 30mg Amp    │ (Post-Op) │ (PIN: ****) │(PIN: ****)│(PIN: ****)│
└─────────────┴─────────────┴───────────┴─────────────┴───────────┴───────────┘
```

---

## 6. Cold-Chain & Environmental Monitoring (IoT Layer)

Medications like **Oxytocin** (vital for preventing maternal postpartum haemorrhage), **Insulin**, **Hepatitis B Vaccines**, and **Tetanus Toxoid** lose potency when exposed to temperatures outside $2^\circ\text{C} - 8^\circ\text{C}$.

### The Hardware-Software Bridge
- Wireless BLE/WiFi temperature and humidity data loggers (e.g. ESP32 + DS18B20 digital probes) placed inside each pharmacy refrigerator and vaccine cold-box.
- Sensor transmits temperature readings to the local AraCare gateway every **60 seconds**.

```
┌─────────────────────────────────────────────────────────────────────────┐
│ ❄️ REFRIGERATOR #2 (MATERNITY WARD OXYTOCIN & VACCINE FRIDGE)           │
│ Current Temp: 4.2°C  | Status: NORMAL (Range: 2.0°C – 8.0°C)            │
│ Power Source: Inverter / Solar Backup | Last reading: 12 seconds ago   │
└─────────────────────────────────────────────────────────────────────────┘
```

### Real-Time Excursion Escalation Matrix
If the temperature rises above $8.0^\circ\text{C}$ for longer than 15 minutes:

```
T + 15 min ──▶ Push notification to Duty Pharmacist & Ward In-Charge
               "⚠️ Temp Alert: Refrigerator #2 is at 8.9°C. Check door/power."

T + 30 min ──▶ SMS + Audible Siren at Nurse Station
               "🚨 CRITICAL COLD-CHAIN BREACH: Ref #2 at 10.4°C for 30 mins."
               Auto-notifies Facilities / Generator Operator.

T + 60 min ──▶ Quarantine Protocol Triggered:
               System marks all biologics in Ref #2 as "QUARANTINE_HOLD".
               Prevents staff from dispensing compromised oxytocin/insulin
               until potency is verified or stocks safely transferred.
```

---

## 7. Anti-Pilferage & Blind Cycle Count Protocol

Traditional inventory audits fail because staff know how many boxes "should" be on the shelf and simply write down the expected number. AraCare implements **Blind Perpetual Auditing**.

```
┌───────────────────────────────────────────────────────────────────────┐
│ 📋 BLIND STOCK AUDIT PROMPT (System-Triggered Daily at Shift Change) │
│                                                                       │
│ Auditor: Pharmacist Kalu                                              │
│ Location: OPD Pharmacy — Shelf B2                                     │
│ Target Item: Ceftriaxone 1g Injectable                                │
│                                                                       │
│ [Enter Physical Count Present on Shelf: _____ ]                       │
│                                                                       │
│ (System DOES NOT display expected quantity to the user)               │
└───────────────────────────────────┬───────────────────────────────────┘
                                    │
                                    ▼
┌───────────────────────────────────────────────────────────────────────┐
│ SYSTEM RECONCILIATION:                                                │
│ System Expected Count: 140 vials                                      │
│ Physical Count Entered: 122 vials                                     │
│ Variance: -18 vials (Discrepancy Value: ₦27,000)                      │
│                                                                       │
│ 🚨 INSTANT DISCREPANCY ACTIONS:                                       │
│ 1. Discrepancy logged with timestamp and user ID.                     │
│ 2. Automated audit alert dispatched to Head of Pharmacy & Auditor.    │
│ 3. Shift handover cannot close without supervisor sign-off code.      │
└───────────────────────────────────────────────────────────────────────┘
```

---

## 8. Predictive Procurement & Seasonal Forecasting

In Nigeria, drug consumption follows dramatic seasonal and logistical rhythms. Reactive ordering causes catastrophic stockouts during supply chain disruptions.

### The Nigerian Predictive Model
$$\text{Reorder Point (ROP)} = (\text{Average Daily Consumption} \times \text{Supplier Lead Time in Days}) + \text{Safety Stock}$$

```
DISEASE BURDEN PATTERNS BUILT INTO ARACARE:

1. RAINY SEASON SURGE (May – October)
   → Malaria incidence multiplies by 3.5x
   → System automatically inflates ROP for:
     - Artemether-Lumefantrine, Artesunate IV, RDT test kits, Paracetamol.

2. HARMATTAN DUST SEASON (December – February)
   → Respiratory infections, asthma, eye irritation spike.
   → System auto-adjusts ROP for:
     - Salbutamol inhalers, Prednisolone, Cough syrups, Eye drops.

3. SUPPLY LEAD TIME BUFFERS (Logistics Realities)
   → Lagos/Ogun pharmaceutical manufacturing hubs to Northern/Eastern states:
     Lead time factored as 14–21 days due to transport/customs delays.
   → System triggers PO recommendations 3 weeks before stock reaches red line.
```

### The Purchase Order (PO) to Goods Received Note (GRN) Flow
```
1. Low Stock Alert
   ↓
2. Draft PO Generated automatically (with recommended quantities & preferred vendor)
   ↓
3. Procurement Officer & MD Approval
   ↓
4. PO sent to Supplier (Email / WhatsApp PDF)
   ↓
5. Delivery arrives at Central Store
   ↓
6. Storekeeper creates GRN (Goods Received Note):
   - Scans barcodes, inputs batch numbers, expiry dates, purchase price
   ↓
7. System reconciles GRN against original PO (checks for short deliveries or price changes)
   ↓
8. Accounts Payable entry generated in Finance Module
```

---

## 9. Comprehensive Database Schema

```sql
-- Master Item Definition
CREATE TABLE inventory_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    facility_id UUID NOT NULL,
    sku_code VARCHAR(50) UNIQUE NOT NULL,
    generic_name VARCHAR(255) NOT NULL,
    brand_name VARCHAR(255),
    category VARCHAR(50) NOT NULL, -- MEDICATION, CONSUMABLE, REAGENT, BIOLOGIC, MEDICAL_GAS
    formulation VARCHAR(50),       -- TABLET, INJECTION, SYRUP, INFUSION
    strength VARCHAR(50),
    unit_of_measure VARCHAR(50) NOT NULL, -- TAB, VIAL, AMP, PACK, BOTTLE
    nafdac_nrn VARCHAR(50),        -- NAFDAC Reg Number
    is_controlled BOOLEAN DEFAULT FALSE,
    is_cold_chain BOOLEAN DEFAULT FALSE,
    storage_temp_min DECIMAL(4,1) DEFAULT 15.0,
    storage_temp_max DECIMAL(4,1) DEFAULT 25.0,
    reorder_level INTEGER NOT NULL DEFAULT 50,
    safety_stock INTEGER NOT NULL DEFAULT 20,
    unit_cost_price DECIMAL(12,2) NOT NULL DEFAULT 0.00,
    unit_selling_price DECIMAL(12,2) NOT NULL DEFAULT 0.00,
    hmo_tariff_price DECIMAL(12,2) DEFAULT 0.00,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Physical Store Locations
CREATE TABLE stock_locations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    facility_id UUID NOT NULL,
    location_name VARCHAR(100) NOT NULL, -- Central Store, OPD Pharmacy, Emergency Cabinet
    location_code VARCHAR(30) UNIQUE NOT NULL,
    location_type VARCHAR(50) NOT NULL, -- WAREHOUSE, DISPENSARY, WARD_CABINET, THEATRE
    in_charge_staff_id UUID NOT NULL,
    is_active BOOLEAN DEFAULT TRUE
);

-- Batches & Lot Numbers (FEFO Tracking Core)
CREATE TABLE stock_batches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    item_id UUID NOT NULL REFERENCES inventory_items(id),
    location_id UUID NOT NULL REFERENCES stock_locations(id),
    batch_number VARCHAR(100) NOT NULL,
    manufacture_date DATE,
    expiry_date DATE NOT NULL,
    quantity_received INTEGER NOT NULL,
    quantity_remaining INTEGER NOT NULL,
    quantity_reserved INTEGER DEFAULT 0, -- Soft-locks for active prescriptions
    unit_cost DECIMAL(12,2) NOT NULL,
    barcode_data VARCHAR(255),
    status VARCHAR(30) DEFAULT 'ACTIVE', -- ACTIVE, QUARANTINE, EXPIRED, RECALLED, DEPLETED
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT positive_stock CHECK (quantity_remaining >= 0),
    UNIQUE(item_id, location_id, batch_number)
);

-- Immutable Stock Movement Ledger
CREATE TABLE stock_ledger (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    facility_id UUID NOT NULL,
    batch_id UUID NOT NULL REFERENCES stock_batches(id),
    item_id UUID NOT NULL REFERENCES inventory_items(id),
    from_location_id UUID REFERENCES stock_locations(id),
    to_location_id UUID REFERENCES stock_locations(id),
    movement_type VARCHAR(50) NOT NULL, -- RECEIPT_GRN, TRANSFER_IN, TRANSFER_OUT, DISPENSE_PATIENT, ADJUSTMENT_AUDIT, EXPIRY_DISCARD, RETURN
    quantity_delta INTEGER NOT NULL,    -- Positive for additions, negative for deductions
    balance_after INTEGER NOT NULL,
    reference_id UUID,                  -- Links to visit_id, prescription_id, transfer_id, or grn_id
    performed_by UUID NOT NULL,         -- Staff UUID
    witnessed_by UUID,                  -- Witness Staff UUID for DD / Discard
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Controlled Substance (DD Register) Log
CREATE TABLE controlled_substance_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    facility_id UUID NOT NULL,
    batch_id UUID NOT NULL REFERENCES stock_batches(id),
    patient_id UUID NOT NULL,
    visit_id UUID NOT NULL,
    prescription_id UUID NOT NULL,
    prescribing_doctor_id UUID NOT NULL,
    dispensing_pharmacist_id UUID NOT NULL,
    administering_nurse_id UUID,
    witness_staff_id UUID,
    quantity_ordered DECIMAL(8,2) NOT NULL,
    quantity_administered DECIMAL(8,2) NOT NULL,
    quantity_wasted DECIMAL(8,2) DEFAULT 0.00,
    waste_disposal_method VARCHAR(100),
    clinical_indication TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- IoT Cold Chain Temperature Logs
CREATE TABLE cold_chain_temperature_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    device_mac_address VARCHAR(50) NOT NULL,
    location_id UUID NOT NULL REFERENCES stock_locations(id),
    temperature_celsius DECIMAL(4,2) NOT NULL,
    humidity_percentage DECIMAL(4,2),
    is_excursion BOOLEAN DEFAULT FALSE,
    power_source VARCHAR(20) DEFAULT 'GRID', -- GRID, GENERATOR, INVERTER, SOLAR
    battery_level_pct INTEGER,
    recorded_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Blind Cycle Counts / Audits
CREATE TABLE inventory_audits (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    facility_id UUID NOT NULL,
    location_id UUID NOT NULL REFERENCES stock_locations(id),
    item_id UUID NOT NULL REFERENCES inventory_items(id),
    batch_id UUID REFERENCES stock_batches(id),
    expected_system_quantity INTEGER NOT NULL,
    actual_counted_quantity INTEGER NOT NULL,
    variance INTEGER GENERATED ALWAYS AS (actual_counted_quantity - expected_system_quantity) STORED,
    audited_by UUID NOT NULL,
    supervisor_id UUID,
    audit_status VARCHAR(30) DEFAULT 'PENDING_REVIEW', -- MATCHED, DISCREPANCY_FLAGGED, APPROVED_RECONCILED
    reason_notes TEXT,
    audited_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

---

## 10. Summary: Core Design Decisions

| Feature | Design Decision | Operational Rationale |
|---|---|---|
| **Stock Rotation** | Automated FEFO Enforcement via Barcode | Eliminates expired drug waste on pharmacy shelves. |
| **Controlled Drugs** | Dual-PIN digital sign-off + waste logging | 100% compliance with NAFDAC/NDLEA Dangerous Drug audits. |
| **Pilferage Control** | Blind cycle counts + unannounced audit triggers | Eliminates staff falsification of physical inventory counts. |
| **Billing Integration** | Atomic lock: Prescribe $\rightarrow$ Reserve $\rightarrow$ Scan $\rightarrow$ Deduct & Bill | Prevents unbilled medications from leaving the hospital premises. |
| **Cold-Chain Safety** | IoT real-time temperature probes + excursion alarms | Protects high-value maternal oxytocin, insulin, and vaccines during power outages. |
| **Procurement Intelligence**| Seasonal disease forecasting (Malaria/Harmattan) | Eliminates catastrophic stock-outs when lead times stretch to 3 weeks. |
| **Brand Flexibility** | Generic molecule catalogue with commercial brand aliasing | Empowers patient affordability while maintaining clinical integrity. |
