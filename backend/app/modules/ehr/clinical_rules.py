"""Pure clinical logic: no DB, easy to unit-test and to defend."""

# drug_class -> generic/brand names that belong to it (small, extensible slice of the NEML)
DRUG_CLASSES = {
    "penicillin": ["amoxicillin", "ampicillin", "penicillin", "augmentin", "amoxiclav", "co-amoxiclav",
                   "amoxicillin-clavulanate", "flucloxacillin", "cloxacillin", "piperacillin"],
    "sulfonamide": ["cotrimoxazole", "co-trimoxazole", "septrin", "sulfamethoxazole", "sulphadoxine",
                    "fansidar", "sulfadoxine-pyrimethamine"],
    "nsaid": ["ibuprofen", "diclofenac", "naproxen", "aspirin", "piroxicam", "ketorolac"],
    "cephalosporin": ["ceftriaxone", "cefuroxime", "cefixime", "cefalexin", "ceftazidime", "rocephin"],
    "macrolide": ["azithromycin", "erythromycin", "clarithromycin"],
    "quinolone": ["ciprofloxacin", "levofloxacin", "ofloxacin"],
}


def drug_class_of(name: str) -> str | None:
    n = name.lower()
    for cls, members in DRUG_CLASSES.items():
        if any(m in n for m in members):
            return cls
    return None


def allergy_conflicts(drug_name: str, allergies) -> list:
    """Hard-block check. Matches by drug class (amoxicillin vs 'penicillin' allergy) or by name."""
    cls = drug_class_of(drug_name)
    hits = []
    for a in allergies:
        if (a.drug_class and cls and a.drug_class.lower() == cls) or \
           (a.allergen_name and a.allergen_name.lower() in drug_name.lower()):
            hits.append(a)
    return hits


def bmi(weight_kg, height_cm):
    if weight_kg and height_cm:
        return round(weight_kg / ((height_cm / 100) ** 2), 1)
    return None


def flag_vitals(v: dict) -> tuple[list[dict], bool]:
    """Returns (flags, is_critical). Thresholds follow the EHR spec (fever>37.5, SpO2<94 ...)."""
    flags, critical = [], False

    def add(field, label, level):
        nonlocal critical
        flags.append({"field": field, "label": label, "level": level})
        critical = critical or level == "critical"

    t, sp, hr, rr = v.get("temperature"), v.get("spo2"), v.get("pulse_rate"), v.get("respiratory_rate")
    sys_, dia = v.get("bp_systolic"), v.get("bp_diastolic")
    if t is not None:
        if t >= 39.5 or t < 35.0:
            add("temperature", f"Temperature {t}°C", "critical")
        elif t > 37.5:
            add("temperature", f"Fever {t}°C", "abnormal")
    if sp is not None:
        if sp < 90:
            add("spo2", f"SpO2 {sp}%", "critical")
        elif sp < 94:
            add("spo2", f"Low SpO2 {sp}%", "abnormal")
    if sys_ is not None:
        if sys_ >= 180 or (dia or 0) >= 120 or sys_ < 80:
            add("bp", f"BP {sys_}/{dia}", "critical")
        elif sys_ >= 140 or (dia or 0) >= 90 or sys_ < 90:
            add("bp", f"BP {sys_}/{dia}", "abnormal")
    if hr is not None:
        if hr > 130 or hr < 40:
            add("pulse_rate", f"Pulse {hr}", "critical")
        elif hr > 100 or hr < 50:
            add("pulse_rate", f"Pulse {hr}", "abnormal")
    if rr is not None:
        if rr > 30 or rr < 8:
            add("respiratory_rate", f"RR {rr}", "critical")
        elif rr > 20 or rr < 12:
            add("respiratory_rate", f"RR {rr}", "abnormal")
    return flags, critical


TEMPLATES = {
    "MALARIA_UNCOMPLICATED": {
        "label": "Uncomplicated malaria",
        "subjective": "Fever, headache, body aches and chills for [__] days. No cough, vomiting or diarrhoea.",
        "objective": "Febrile, mild pallor. Abdomen soft, non-tender.",
        "plan": "Malaria RDT, FBC. Artemether-Lumefantrine (weight-based). Paracetamol. Review in 3 days if not improving.",
        "diagnoses": ["B50.9"],
        "labs": [{"test_code": "LAB-MAL", "test_name": "Malaria RDT", "priority": "stat"},
                 {"test_code": "LAB-FBC", "test_name": "Full Blood Count", "priority": "routine"}],
        "drugs": [{"drug_name": "Artemether-Lumefantrine 80/480mg", "dose": "4 tabs", "frequency": "stat, 8h, 24h, 36h, 48h, 60h", "duration_days": 3},
                  {"drug_name": "Paracetamol 1000mg", "dose": "1 g", "frequency": "TDS", "duration_days": 3}],
    },
    "HYPERTENSION_FOLLOWUP": {
        "label": "Hypertension follow-up",
        "subjective": "Routine BP review. Symptoms: [__]. Adherence: [__].",
        "objective": "BP from today's vitals. Currently on: [medications].",
        "plan": "Continue current antihypertensives. Target BP <130/80. Review in 4-8 weeks.",
        "diagnoses": ["I10"], "labs": [], "drugs": [],
    },
    "TYPHOID": {
        "label": "Typhoid fever",
        "subjective": "Sustained fever, headache, abdominal discomfort, constipation/diarrhoea.",
        "objective": "Febrile, coated tongue, mild abdominal tenderness.",
        "plan": "Widal, FBC. Ciprofloxacin 500mg BD x7-10 days (or azithromycin if contraindicated).",
        "diagnoses": ["A01.0"],
        "labs": [{"test_code": "LAB-TYP", "test_name": "Typhoid (Widal)", "priority": "routine"}],
        "drugs": [{"drug_name": "Ciprofloxacin 500mg", "dose": "500 mg", "frequency": "BD", "duration_days": 7}],
    },
}

ICD10_SEED = [
    ("B50.9", "Plasmodium falciparum malaria, unspecified", "malaria falciparum fever"),
    ("B50.0", "P. falciparum malaria with cerebral complications", "severe malaria cerebral"),
    ("B54", "Unspecified malaria", "malaria"),
    ("B51.9", "Plasmodium vivax malaria without complication", "malaria vivax"),
    ("A01.0", "Typhoid fever", "typhoid enteric widal"),
    ("I10", "Essential (primary) hypertension", "hypertension high blood pressure bp"),
    ("E11.9", "Type 2 diabetes mellitus without complications", "diabetes sugar dm"),
    ("J06.9", "Acute upper respiratory infection, unspecified", "cold catarrh cough urti"),
    ("J18.9", "Pneumonia, unspecified organism", "pneumonia chest infection"),
    ("J45.9", "Asthma, unspecified", "asthma wheeze"),
    ("A09", "Infectious gastroenteritis and colitis", "diarrhoea vomiting gastroenteritis"),
    ("N39.0", "Urinary tract infection, site not specified", "uti urinary burning"),
    ("D57.0", "Sickle-cell anaemia with crisis", "sickle cell crisis pain"),
    ("D64.9", "Anaemia, unspecified", "anaemia pallor"),
    ("K29.7", "Gastritis, unspecified", "gastritis ulcer epigastric"),
    ("R51", "Headache", "headache"),
    ("R50.9", "Fever, unspecified", "fever pyrexia"),
    ("R05", "Cough", "cough"),
    ("M54.5", "Low back pain", "back pain"),
    ("L30.9", "Dermatitis, unspecified", "rash skin eczema"),
    ("O80", "Single spontaneous delivery", "delivery labour"),
    ("Z34.9", "Supervision of normal pregnancy, unspecified", "anc pregnancy antenatal"),
    ("Z00.0", "General medical examination", "check up medical"),
    ("B20", "HIV disease", "hiv"),
    ("A15.9", "Respiratory tuberculosis, unspecified", "tb tuberculosis"),
    ("E66.9", "Obesity, unspecified", "obesity overweight"),
    ("T14.9", "Injury, unspecified", "injury trauma wound"),
    ("K35.8", "Acute appendicitis, other and unspecified", "appendicitis"),
    ("H10.9", "Conjunctivitis, unspecified", "red eye conjunctivitis"),
    ("B35.9", "Dermatophytosis, unspecified", "ringworm fungal"),
]
