"""Mock data for development and demos: patients, weeks of visit history and a live queue for today.

    python -m app.mock_data            # fills an empty database (refuses if patients already exist)
    python -m app.mock_data --reset    # wipes patients, visits, queues, notes, lab results, logs; then fills

Everything is deterministic for a given --seed. History is written directly with backdated timestamps, following
the same rules as the live code (ticket numbering per department/day, journey cascade, triage flags, allergy
hard-block, content hash on signed notes). Today's visits are cut at the current time, so the queues show patients
waiting, called, in service and done. Lab orders get results (a few critical) and most prescriptions are
dispensed. The hospital profile is filled in and marked onboarded, with every suggested department and ward, so a
demo database looks like a hospital that is already running. Refuses to run with ARACARE_ENV=production.
"""
import argparse
import hashlib
import json
import logging
import random
from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import delete, select

from .config import settings
from .db import TZ, SessionLocal, local_today, uid, utcnow
from .modules.core.models import AuditLog, Consent, Counter, Facility, Message, OutboxEvent, Staff
from .modules.core.security import next_counter
from .modules.ehr import clinical_rules as rules
from .modules.ehr.models import (AllergyRecord, ClinicalNote, Diagnosis, Icd10, LabOrder, MedicationOrder,
                                 NoteAddendum, Vitals)
from .modules.queues.models import Journey, JourneyStep, QueueState, Ticket
from .modules.queues.service import PREFIX
from .modules.registration import service as reg
from .modules.registration.models import Patient, Visit
from .modules.scribe.models import ScribeSession
from .modules.org.catalogue import SUGGESTED, create_suggested
from .schema import migrate
from .seed import add_demo_staff, seed

try:                                   # AraPulse demo conversations, pages and alerts (optional module)
    from .modules.pulse import demo as pulse_demo
except ImportError:
    pulse_demo = None

log = logging.getLogger("aracare.mock")

# Extra staff on top of the demo accounts from seed.py (same password): (username, name, role, position, department)
MOCK_STAFF = [("reception2", "Tolu Bankole", "reception", "Health Records Officer", "REC"),
              ("nurse2", "Nurse Halima Bello", "nurse", "Senior Nursing Officer", "EMERG"),
              ("nurse3", "Nurse Grace Etim", "nurse", "Ward Sister", "MED"),
              ("nurse4", "Matron Comfort Akpan", "nurse", "Matron", "NURS"),
              ("nurse5", "Nurse Ngozi Okeke", "nurse", "Midwife", "OBG"),
              ("nurse6", "Nurse Aisha Garba", "nurse", "Staff Nurse", "PAED"),
              ("doctor2", "Dr. Funmilayo Adebayo", "doctor", "Consultant", "MED"),
              ("doctor3", "Dr. Musa Abdullahi", "doctor", "Registrar", "EMERG"),
              ("doctor4", "Dr. Ifeoma Chukwu", "doctor", "Senior Registrar", "OBG"),
              ("doctor5", "Dr. Kunle Ajayi", "doctor", "Consultant", "PAED"),
              ("doctor6", "Dr. Bashir Yusuf", "doctor", "House Officer", "SURG"),
              ("lab2", "Emmanuel Okon", "lab", "Lab Technician", "LAB"),
              ("pharmacy2", "Blessing Edet", "pharmacy", "Pharmacy Technician", "PHARM")]
OFF_DUTY = {"doctor6", "nurse6"}       # someone is always off shift

TRIAGE_COUNTERS = ["Triage Bay 1", "Triage Bay 2"]
OPD_COUNTERS = ["Consulting Room 1", "Consulting Room 2", "Consulting Room 3"]

# ------------------------------------------------------------------ people
ETHNIC = {
    "yoruba": {
        "surnames": ["Adeyemi", "Ogunleye", "Balogun", "Adebayo", "Olawale", "Fashola", "Ogundipe", "Akinola",
                     "Oyelaran", "Adewale", "Ajayi", "Babatunde", "Oladipo", "Afolabi", "Odunsi", "Ilesanmi",
                     "Ogunbiyi", "Adekunle", "Oyewole", "Salami", "Lawal", "Bankole", "Durojaiye", "Ayodele"],
        "male": ["Oluwaseun", "Babajide", "Ayodeji", "Olumide", "Tunde", "Segun", "Dayo", "Kunle", "Femi",
                 "Gbenga", "Damilola", "Tobi", "Wale", "Kayode", "Rotimi", "Adewale", "Ibrahim", "Taiwo"],
        "female": ["Funmilayo", "Adunni", "Folake", "Yetunde", "Bukola", "Titilayo", "Abimbola", "Kemi",
                   "Bisola", "Omolara", "Morenike", "Temitope", "Simisola", "Ronke", "Iyabo", "Kehinde"],
        "states": ["Lagos", "Ogun", "Oyo", "Osun", "Ondo", "Ekiti", "Kwara"],
    },
    "igbo": {
        "surnames": ["Okafor", "Eze", "Nwosu", "Okonkwo", "Chukwu", "Obi", "Nwachukwu", "Okeke", "Onyeka",
                     "Uchenna", "Ibe", "Okoro", "Nnaji", "Anyanwu", "Ezeh", "Nwankwo", "Udeh", "Ogbonna",
                     "Agu", "Iwu", "Mbah", "Onuoha"],
        "male": ["Chinedu", "Emeka", "Obinna", "Ikechukwu", "Chukwuemeka", "Nnamdi", "Uche", "Kelechi",
                 "Chibuzor", "Ifeanyi", "Somto", "Ebuka", "Chidi", "Tochukwu", "Onyekachi", "Kenechukwu"],
        "female": ["Ngozi", "Chioma", "Adaeze", "Amaka", "Ifeoma", "Nneka", "Chinwe", "Uju", "Ebere",
                   "Chiamaka", "Obiageli", "Ogechi", "Nkechi", "Ijeoma", "Kosisochukwu", "Ada"],
        "states": ["Anambra", "Enugu", "Imo", "Abia", "Ebonyi"],
    },
    "hausa": {
        "surnames": ["Abdullahi", "Bello", "Mohammed", "Usman", "Garba", "Sani", "Danjuma", "Yusuf",
                     "Ibrahim", "Aliyu", "Suleiman", "Musa", "Abubakar", "Shehu", "Rabiu", "Tijani", "Lawan"],
        "male": ["Abubakar", "Musa", "Sani", "Usman", "Aminu", "Yakubu", "Haruna", "Bashir", "Kabiru",
                 "Nasiru", "Umar", "Lawal", "Ismail", "Mustapha", "Idris", "Jibril"],
        "female": ["Aisha", "Fatima", "Halima", "Zainab", "Hauwa", "Maryam", "Hadiza", "Amina", "Safiya",
                   "Rukayya", "Bilkisu", "Khadija", "Hafsat", "Jamila", "Asmau"],
        "states": ["Kano", "Kaduna", "Katsina", "Sokoto", "Bauchi", "Niger", "Kebbi"],
    },
    "south_south": {
        "surnames": ["Etim", "Bassey", "Okon", "Effiong", "Ekpo", "Ikpe", "Udo", "Akpan", "Edet", "Inyang",
                     "Ogbe", "Omoregie", "Osagie", "Igbinedion", "Tamuno", "Briggs", "Peters", "Douglas"],
        "male": ["Emmanuel", "Godwin", "Uduak", "Aniekan", "Ekene", "Osaro", "Efosa", "Ita", "Daniel",
                 "Samuel", "Victor", "Joseph", "Ime", "Kingsley", "Precious", "Ebiere"],
        "female": ["Grace", "Blessing", "Mfon", "Uduak", "Comfort", "Osas", "Ivie", "Ekaette", "Esther",
                   "Patience", "Mercy", "Joy", "Iniobong", "Eno", "Imaobong", "Tamara"],
        "states": ["Akwa Ibom", "Cross River", "Rivers", "Edo", "Delta", "Bayelsa"],
    },
}
ETHNIC_WEIGHTS = {"yoruba": 50, "igbo": 25, "hausa": 13, "south_south": 12}
PHONE_PREFIXES = ["0803", "0806", "0813", "0816", "0703", "0706", "0805", "0807", "0815", "0705", "0802",
                  "0808", "0812", "0701", "0902", "0907", "0809", "0817", "0818", "0909", "0908", "0810"]
HMOS = [("Hygeia HMO", "HYG"), ("AXA Mansard Health", "AXA"), ("Reliance HMO", "RHM"), ("Avon HMO", "AVN"),
        ("Leadway Health", "LWH"), ("NHIA", "NHIA"), ("Clearline HMO", "CLH"), ("Total Health Trust", "THT")]
BLOOD_GROUPS = ["O+"] * 50 + ["A+"] * 21 + ["B+"] * 20 + ["AB+"] * 3 + ["O-"] * 3 + ["A-", "B-", "AB-"]
ALLERGIES = [  # (allergen as reception writes it, reaction, severity, weight)
    ("Penicillin", "Generalised rash and itching", "moderate", 30),
    ("Sulfa drugs", "Stevens-Johnson syndrome (2019)", "life_threatening", 10),
    ("NSAIDs", "Worsens asthma, wheeze", "severe", 10),
    ("Chloroquine", "Severe itching", "mild", 15),
    ("Groundnut", "Lip swelling", "severe", 8),
    ("Seafood", "Hives", "moderate", 8),
    ("Cotrimoxazole", "Skin peeling", "severe", 6),
    ("Ciprofloxacin", "Tendon pain", "moderate", 5),
    ("Latex", "Contact dermatitis", "mild", 3),
    ("Ceftriaxone", "Anaphylaxis", "life_threatening", 3),
]

# ------------------------------------------------------------------ clinical scenarios
LABS = {
    "LAB-MAL": "Malaria RDT", "LAB-MP": "Malaria parasite (thick film)", "LAB-FBC": "Full Blood Count",
    "LAB-TYP": "Typhoid (Widal)", "LAB-FBS": "Fasting Blood Sugar", "LAB-HBA1C": "HbA1c",
    "LAB-UA": "Urinalysis", "LAB-UMCS": "Urine M/C/S", "LAB-CXR": "Chest X-ray", "LAB-PCV": "Packed Cell Volume",
    "LAB-EUC": "Electrolytes, Urea, Creatinine", "LAB-LIP": "Lipid profile", "LAB-HIV": "HIV screening",
    "LAB-HBSAG": "Hepatitis B surface antigen", "LAB-VDRL": "VDRL", "LAB-GXT": "Blood group & genotype",
    "LAB-SAFB": "Sputum AFB / GeneXpert", "LAB-SMCS": "Stool microscopy", "LAB-HPY": "H. pylori antigen",
}

# Lab results: test -> (normal, abnormal, critical or None); each a function of the random generator.
LAB_RESULTS = {
    "LAB-MAL": (lambda r: "Negative", lambda r: "Positive (P. falciparum)", None),
    "LAB-MP": (lambda r: "No malaria parasites seen",
               lambda r: f"P. falciparum seen ({r.choice(['+', '++', '+++'])})",
               lambda r: f"P. falciparum ++++, parasitaemia {r.randint(5, 12)}%"),
    "LAB-FBC": (lambda r: f"Hb {r.uniform(12, 15.5):.1f} g/dL, WBC {r.uniform(4, 10):.1f} x10^9/L, "
                          f"Platelets {r.randint(160, 380)} x10^9/L",
                lambda r: f"Hb {r.uniform(9, 11):.1f} g/dL, WBC {r.uniform(11.5, 18):.1f} x10^9/L (neutrophilia), "
                          f"Platelets {r.randint(140, 300)} x10^9/L",
                lambda r: f"Hb {r.uniform(4.2, 5.9):.1f} g/dL, Platelets {r.randint(18, 45)} x10^9/L"),
    "LAB-TYP": (lambda r: "O and H titres below 1:80", lambda r: "O 1:160, H 1:160", None),
    "LAB-FBS": (lambda r: f"{r.uniform(3.9, 5.6):.1f} mmol/L", lambda r: f"{r.uniform(7.2, 13.5):.1f} mmol/L",
                lambda r: f"{r.uniform(25, 33):.1f} mmol/L"),
    "LAB-HBA1C": (lambda r: f"{r.uniform(4.8, 5.9):.1f}%", lambda r: f"{r.uniform(7.0, 10.5):.1f}%", None),
    "LAB-UA": (lambda r: "Protein nil, glucose nil, blood nil",
               lambda r: "Protein ++, leucocytes ++, nitrites positive", None),
    "LAB-UMCS": (lambda r: "No significant growth",
                 lambda r: "E. coli >10^5 CFU/ml, sensitive to nitrofurantoin and ceftriaxone", None),
    "LAB-CXR": (lambda r: "Clear lung fields, normal heart size", lambda r: "Right lower zone consolidation",
                lambda r: "Large left pneumothorax with mediastinal shift"),
    "LAB-PCV": (lambda r: f"{r.randint(34, 45)}%", lambda r: f"{r.randint(24, 30)}%",
                lambda r: f"{r.randint(11, 15)}%"),
    "LAB-EUC": (lambda r: f"Na {r.randint(135, 144)}, K {r.uniform(3.6, 4.9):.1f}, Urea {r.uniform(2.8, 6.5):.1f} "
                          f"mmol/L, Creatinine {r.randint(60, 105)} umol/L",
                lambda r: f"Urea {r.uniform(8, 14):.1f} mmol/L, Creatinine {r.randint(140, 260)} umol/L",
                lambda r: f"K {r.uniform(6.6, 7.4):.1f} mmol/L, Creatinine {r.randint(520, 780)} umol/L"),
    "LAB-LIP": (lambda r: f"Total cholesterol {r.uniform(3.8, 5.0):.1f}, LDL {r.uniform(2.0, 3.0):.1f} mmol/L",
                lambda r: f"Total cholesterol {r.uniform(6.2, 7.8):.1f}, LDL {r.uniform(4.1, 5.2):.1f} mmol/L",
                None),
    "LAB-HIV": (lambda r: "Non-reactive", lambda r: "Reactive: referred for confirmation and counselling", None),
    "LAB-HBSAG": (lambda r: "Negative", lambda r: "Positive", None),
    "LAB-VDRL": (lambda r: "Non-reactive", lambda r: "Reactive 1:8", None),
    "LAB-GXT": (lambda r: f"{r.choice(['O', 'A', 'B'])} Rh D positive, genotype {r.choice(['AA', 'AA', 'AS'])}",
                lambda r: f"{r.choice(['O', 'A', 'B'])} Rh D positive, genotype SS", None),
    "LAB-SAFB": (lambda r: "MTB not detected", lambda r: "MTB detected, rifampicin resistance not detected", None),
    "LAB-SMCS": (lambda r: "No ova or cysts seen", lambda r: "Ova of Ascaris lumbricoides seen", None),
    "LAB-HPY": (lambda r: "Negative", lambda r: "Positive", None),
}
SLOW_LABS = {"LAB-UMCS": (24, 60), "LAB-SAFB": (20, 48)}     # hours: cultures and GeneXpert batches

# Each drug: (adult, child) as (name, dose, frequency, days, route). child=None means not for under-12s.
DRUGS = {
    "al": (("Artemether-Lumefantrine 80/480mg", "1 tab", "BD", 3, "oral"),
           ("Artemether-Lumefantrine 20/120mg dispersible", "weight-based", "BD", 3, "oral")),
    "pcm": (("Paracetamol 500mg", "1 g", "TDS", 3, "oral"), ("Paracetamol syrup 120mg/5ml", "10 ml", "TDS", 3, "oral")),
    "cipro": (("Ciprofloxacin 500mg", "500 mg", "BD", 7, "oral"), None),
    "azith": (("Azithromycin 500mg", "500 mg", "OD", 3, "oral"),
              ("Azithromycin suspension 200mg/5ml", "10 mg/kg", "OD", 3, "oral")),
    "amox": (("Amoxicillin 500mg", "500 mg", "TDS", 7, "oral"),
             ("Amoxicillin suspension 250mg/5ml", "5 ml", "TDS", 5, "oral")),
    "augmentin": (("Amoxicillin-Clavulanate 625mg", "625 mg", "BD", 7, "oral"),
                  ("Amoxicillin-Clavulanate suspension 228mg/5ml", "5 ml", "BD", 5, "oral")),
    "cefuroxime": (("Cefuroxime 500mg", "500 mg", "BD", 7, "oral"),
                   ("Cefuroxime suspension 125mg/5ml", "5 ml", "BD", 5, "oral")),
    "amlo": (("Amlodipine 10mg", "10 mg", "OD", 30, "oral"), None),
    "lisino": (("Lisinopril 10mg", "10 mg", "OD", 30, "oral"), None),
    "hctz": (("Hydrochlorothiazide 25mg", "25 mg", "OD", 30, "oral"), None),
    "metformin": (("Metformin 500mg", "1 g", "BD", 30, "oral"), None),
    "glib": (("Glibenclamide 5mg", "5 mg", "OD", 30, "oral"), None),
    "ors": (("Oral Rehydration Salts", "1 sachet in 1L water", "after each loose stool", 3, "oral"),
            ("Oral Rehydration Salts", "100 ml", "after each loose stool", 3, "oral")),
    "zinc": (None, ("Zinc sulphate 20mg dispersible", "20 mg", "OD", 10, "oral")),
    "metro": (("Metronidazole 400mg", "400 mg", "TDS", 5, "oral"),
              ("Metronidazole suspension 200mg/5ml", "5 ml", "TDS", 5, "oral")),
    "omep": (("Omeprazole 20mg", "20 mg", "BD", 14, "oral"), None),
    "antacid": (("Magnesium trisilicate", "15 ml", "TDS", 7, "oral"), None),
    "folic": (("Folic acid 5mg", "5 mg", "OD", 30, "oral"), ("Folic acid 5mg", "5 mg", "OD", 30, "oral")),
    "ferrous": (("Ferrous sulphate 200mg", "200 mg", "BD", 30, "oral"),
                ("Ferrous sulphate syrup", "5 ml", "OD", 30, "oral")),
    "salb": (("Salbutamol inhaler 100mcg", "2 puffs", "PRN", 30, "inhaled"),
             ("Salbutamol syrup 2mg/5ml", "5 ml", "TDS", 5, "oral")),
    "pred": (("Prednisolone 5mg", "40 mg", "OD", 5, "oral"), ("Prednisolone 5mg", "1 mg/kg", "OD", 3, "oral")),
    "ibu": (("Ibuprofen 400mg", "400 mg", "TDS", 5, "oral"), ("Ibuprofen syrup 100mg/5ml", "5 ml", "TDS", 3, "oral")),
    "diclo": (("Diclofenac 50mg", "50 mg", "BD", 5, "oral"), None),
    "cetirizine": (("Cetirizine 10mg", "10 mg", "OD", 7, "oral"), ("Cetirizine syrup 5mg/5ml", "5 ml", "OD", 5, "oral")),
    "clotrim": (("Clotrimazole 1% cream", "apply thinly", "BD", 14, "topical"),
                ("Clotrimazole 1% cream", "apply thinly", "BD", 14, "topical")),
    "hydrocort": (("Hydrocortisone 1% cream", "apply thinly", "BD", 7, "topical"),
                  ("Hydrocortisone 1% cream", "apply thinly", "BD", 5, "topical")),
    "chloramph": (("Chloramphenicol 0.5% eye drops", "1 drop", "QDS", 5, "eye"),
                  ("Chloramphenicol 0.5% eye drops", "1 drop", "QDS", 5, "eye")),
    "nitrofur": (("Nitrofurantoin 100mg", "100 mg", "BD", 5, "oral"), None),
    "hydroxyurea": (("Hydroxyurea 500mg", "500 mg", "OD", 30, "oral"), ("Hydroxyurea 500mg", "15 mg/kg", "OD", 30, "oral")),
    "fluids": (("Normal saline 0.9%", "1 L", "8-hourly", 1, "iv"), ("Normal saline 0.9%", "20 ml/kg", "stat", 1, "iv")),
    "artesunate": (("Artesunate injection", "2.4 mg/kg", "0, 12, 24h", 1, "iv"),
                   ("Artesunate injection", "3 mg/kg", "0, 12, 24h", 1, "iv")),
    "sp": (("Sulfadoxine-Pyrimethamine (IPTp)", "3 tabs", "stat", 1, "oral"), None),
    "fefol": (("Ferrous sulphate + Folic acid (Fefol)", "1 cap", "OD", 30, "oral"), None),
    "tt": (("Tetanus toxoid", "0.5 ml", "stat", 1, "im"), None),
    "vitc": (("Vitamin C 100mg", "200 mg", "TDS", 7, "oral"), ("Vitamin C syrup", "5 ml", "OD", 7, "oral")),
}
# when the allergy check blocks a drug, these are tried in order
ALTERNATIVES = {"amox": ["azith", "cefuroxime"], "augmentin": ["azith", "cefuroxime"], "cefuroxime": ["azith"],
                "ibu": ["pcm"], "diclo": ["pcm"], "cipro": ["azith"], "sp": []}


def _w(**kw):
    """Weight by age band (infant/child/adult/elder), with optional female_only and min_age.
    A missing elder weight falls back to adult, a missing infant weight to child."""
    def weight(age, gender):
        if kw.get("female_only") and gender != "female":
            return 0
        if kw.get("min_age") and age < kw["min_age"]:
            return 0
        band = "infant" if age < 1 else "child" if age < 12 else "elder" if age >= 65 else "adult"
        return kw.get(band, kw.get("adult" if band == "elder" else "child", 0))
    return weight


# s/o/a/p are templates; {days}, {vitals}, {control}, {ga}... are filled in. "vitals" shapes the triage numbers.
# Weight-0 scenarios are never drawn at random: scenario() picks them for chronic follow-ups and ANC.
SCENARIOS = {
    "malaria": dict(
        weight=_w(adult=30, child=34, infant=10, elder=18), template="MALARIA_UNCOMPLICATED",
        complaints=["Fever and headache for {days} days", "Hotness of body and body pains", "Fever, chills and weakness",
                    "Fever and vomiting for {days} days", "Body weakness and loss of appetite"],
        vitals={"fever": (37.8, 39.4)},
        s="Fever, headache, generalised body aches and chills for {days} days. Loss of appetite. No cough, no "
          "diarrhoea. Took paracetamol at home with partial relief.",
        o="Febrile, mildly pale, not jaundiced, well hydrated. {vitals}. Chest clear. Abdomen soft, no hepatosplenomegaly.",
        a="Uncomplicated falciparum malaria.",
        p="Malaria RDT positive at point of care. Artemether-Lumefantrine (weight-based) for 3 days with fatty meal. "
          "Paracetamol for fever. Use ITN. Return immediately if vomiting, confusion or convulsion.",
        dx=["B50.9"], labs=["LAB-MAL", "LAB-FBC"], drugs=["al", "pcm"]),
    "severe_malaria": dict(
        weight=_w(adult=1, child=3, infant=1), emergency=True,
        complaints=["High fever, convulsion at home", "Fever, unable to sit or stand, very weak",
                    "Fever and repeated vomiting, drowsy"],
        vitals={"fever": (39.6, 40.4), "pulse": (125, 145), "rr": (28, 36)},
        s="High grade fever for {days} days, repeated vomiting, unable to keep oral drugs down. Drowsy since morning.",
        o="Very ill-looking, prostrate, pale, dehydrated. {vitals}. No neck stiffness.",
        a="Severe malaria with prostration. Rule out cerebral involvement.",
        p="Admit for IV artesunate, IV fluids, check blood glucose and PCV urgently. Strict input/output chart.",
        dx=["B50.0", "D64.9"], labs=["LAB-MP", "LAB-FBC", "LAB-PCV", "LAB-EUC"], drugs=["artesunate", "fluids", "pcm"]),
    "typhoid": dict(
        weight=_w(adult=10, child=5, elder=4), template="TYPHOID",
        complaints=["Persistent fever for {days} days", "Fever and stomach pain", "Fever, headache and constipation"],
        vitals={"fever": (37.9, 39.2)},
        s="Step-ladder fever for {days} days with frontal headache, abdominal discomfort and constipation. "
          "Treated for malaria at a chemist last week without improvement.",
        o="Febrile, coated tongue. {vitals}. Mild right iliac fossa tenderness, no guarding.",
        a="Enteric (typhoid) fever, clinically suspected.",
        p="Widal and FBC. Ciprofloxacin 500mg BD for 7 days. Oral fluids, food and water hygiene counselling. "
          "Review in 1 week or earlier if abdominal pain worsens.",
        dx=["A01.0"], labs=["LAB-TYP", "LAB-FBC"], drugs=["cipro", "pcm"]),
    "urti": dict(
        weight=_w(adult=10, child=16, infant=6, elder=5),
        complaints=["Catarrh and cough for {days} days", "Sore throat and running nose", "Cough and sneezing"],
        vitals={"fever": (37.2, 38.0)},
        s="Rhinorrhoea, sore throat and dry cough for {days} days. No breathlessness. Feeding/eating well.",
        o="Not in distress. {vitals}. Pharynx injected, no exudate. Chest clear.",
        a="Acute upper respiratory tract infection, likely viral.",
        p="Supportive care: warm fluids, steam inhalation, paracetamol. Antibiotics not indicated. "
          "Return if breathing becomes fast or fever persists beyond 3 days.",
        dx=["J06.9"], labs=[], drugs=["pcm", "cetirizine", "vitc"]),
    "pneumonia": dict(
        weight=_w(adult=2, child=6, infant=4, elder=5),
        complaints=["Cough and fast breathing", "Cough, fever and chest pain", "Difficulty in breathing and fever"],
        vitals={"fever": (38.0, 39.3), "spo2": (89, 95), "rr": (24, 34), "pulse": (100, 128)},
        s="Productive cough for {days} days, fever, pleuritic chest pain and breathlessness on exertion.",
        o="Tachypnoeic. {vitals}. Reduced air entry and coarse crepitations at the right base.",
        a="Community-acquired pneumonia.",
        p="Chest X-ray, FBC. Oral amoxicillin-clavulanate; oxygen if SpO2 below 92%. "
          "Review in 48 hours; admit if not improving.",
        dx=["J18.9"], labs=["LAB-CXR", "LAB-FBC"], drugs=["augmentin", "pcm"]),
    "gastro": dict(
        weight=_w(adult=6, child=10, infant=8, elder=4),
        complaints=["Watery stooling and vomiting", "Diarrhoea for {days} days", "Stomach cramps and loose stools"],
        vitals={"pulse": (98, 118), "fever": (37.0, 38.2)},
        s="Watery, non-bloody stools about 6 times a day for {days} days with vomiting. Reduced urine output.",
        o="Some dehydration: dry mucosa, sunken eyes. {vitals}. Abdomen soft, hyperactive bowel sounds.",
        a="Acute gastroenteritis with some dehydration.",
        p="ORS after each loose stool; zinc for children. Stool microscopy if persistent. Return if blood in stool, "
          "unable to drink or lethargic.",
        dx=["A09"], labs=["LAB-SMCS"], drugs=["ors", "zinc", "metro"]),
    "uti": dict(
        weight=_w(adult=8, elder=4, female_only=True, min_age=12),
        complaints=["Painful urination", "Burning sensation when passing urine", "Frequent urination and lower abdominal pain"],
        vitals={"fever": (36.8, 37.9)},
        s="Dysuria, frequency and suprapubic discomfort for {days} days. No loin pain, no vaginal discharge.",
        o="Not toxic. {vitals}. Mild suprapubic tenderness, no renal angle tenderness.",
        a="Uncomplicated lower urinary tract infection.",
        p="Urinalysis and urine M/C/S. Nitrofurantoin 100mg BD for 5 days. Increase fluid intake. "
          "Review with culture result.",
        dx=["N39.0"], labs=["LAB-UA", "LAB-UMCS"], drugs=["nitrofur", "pcm"]),
    "hypertension": dict(
        weight=_w(adult=4, elder=10, min_age=35), template="HYPERTENSION_FOLLOWUP",
        complaints=["Headache and dizziness", "Routine BP check", "Neck pain and blurred vision"],
        vitals={"bp": (145, 176, 92, 108)},
        s="Occipital headache and dizziness for {days} days. Not on any regular medication. Adds salt to food. "
          "No chest pain, no weakness of limbs.",
        o="{vitals}. Heart sounds normal. No pedal oedema. Fundi not examined.",
        a="Essential hypertension, newly diagnosed.",
        p="Start amlodipine 10mg daily. EUC and lipid profile. Low-salt diet, exercise, weight reduction. "
          "Home BP log. Review in 2 weeks.",
        dx=["I10"], labs=["LAB-EUC", "LAB-LIP"], drugs=["amlo"]),
    "htn_followup": dict(
        weight=lambda age, g: 0, template="HYPERTENSION_FOLLOWUP",
        complaints=["Routine BP review", "Came for drug refill", "BP check and drug refill"],
        vitals={"bp": (128, 158, 80, 98)},
        s="Routine hypertension review. Taking amlodipine daily, missed doses twice this month. No headache, "
          "no chest pain, no palpitations.",
        o="{vitals}. No pedal oedema. Chest clear.",
        a="Essential hypertension, {control}.",
        p="Continue amlodipine 10mg; add hydrochlorothiazide 25mg if BP stays above target. Target <130/80. "
          "Adherence counselling. Review in 4-6 weeks.",
        dx=["I10"], labs=[], drugs=["amlo", "hctz"]),
    "diabetes": dict(
        weight=lambda age, g: 0,
        complaints=["Diabetes clinic review", "Frequent urination and thirst", "Sugar check and drug refill"],
        vitals={"bp": (124, 150, 78, 94)},
        s="Type 2 diabetes review. On metformin. Occasional polyuria. No hypoglycaemic episodes. "
          "Diet adherence fair.",
        o="{vitals}. Feet: intact sensation, no ulcers. Random blood sugar at clinic 9.8 mmol/L.",
        a="Type 2 diabetes mellitus, suboptimal control.",
        p="HbA1c, FBS, EUC. Continue metformin 1g BD, add glibenclamide 5mg daily. Diet counselling, foot care. "
          "Review in 4 weeks with results.",
        dx=["E11.9"], labs=["LAB-HBA1C", "LAB-FBS", "LAB-EUC"], drugs=["metformin", "glib"]),
    "sickle_crisis": dict(
        weight=lambda age, g: 0,
        complaints=["Severe bone pains", "Joint pains and fever", "Chest and leg pain, known SS"],
        vitals={"fever": (37.4, 38.6), "pulse": (102, 124), "pain": (7, 9)},
        s="Known HbSS. Severe pains in the lower limbs and back for {days} days, worse with cold weather. "
          "Not taking folic acid regularly.",
        o="In painful distress, pale, mildly icteric. {vitals}. No hepatosplenomegaly.",
        a="Sickle cell anaemia in vaso-occlusive crisis.",
        p="Analgesia, IV fluids, PCV and FBC. Continue folic acid and hydroxyurea. Admit if pain not controlled "
          "in 4 hours or PCV drops.",
        dx=["D57.0"], labs=["LAB-PCV", "LAB-FBC"], drugs=["fluids", "pcm", "folic", "hydroxyurea"]),
    "asthma": dict(
        weight=_w(adult=2, child=3),
        complaints=["Wheezing and chest tightness", "Difficulty breathing at night", "Cough and breathlessness"],
        vitals={"spo2": (91, 96), "rr": (22, 28), "pulse": (96, 115)},
        s="Known asthmatic. Wheeze and chest tightness for {days} days, worse at night. Ran out of inhaler.",
        o="Mild respiratory distress, speaking in sentences. {vitals}. Bilateral expiratory rhonchi.",
        a="Acute exacerbation of asthma, mild to moderate.",
        p="Salbutamol nebulisation at clinic with good response. Salbutamol inhaler, short course prednisolone. "
          "Inhaler technique reviewed. Avoid triggers (dust, smoke).",
        dx=["J45.9"], labs=[], drugs=["salb", "pred"]),
    "gastritis": dict(
        weight=_w(adult=7, elder=4, min_age=15),
        complaints=["Upper abdominal pain", "Burning chest pain after meals", "Stomach ulcer pain"],
        vitals={},
        s="Burning epigastric pain for {days} days, worse when hungry and after spicy food. Uses over-the-counter "
          "pain relievers. No vomiting of blood, no black stools.",
        o="Not pale. {vitals}. Epigastric tenderness, no guarding.",
        a="Gastritis / dyspepsia.",
        p="Omeprazole 20mg BD for 2 weeks, antacid PRN. Stop NSAIDs. H. pylori stool antigen. Small frequent meals.",
        dx=["K29.7"], labs=["LAB-HPY"], drugs=["omep", "antacid"]),
    "back_pain": dict(
        weight=_w(adult=6, elder=5, min_age=20),
        complaints=["Low back pain", "Waist pain for {days} days", "Back pain after lifting"],
        vitals={"pain": (4, 7)},
        s="Low back pain for {days} days after lifting a heavy load. No radiation, no numbness, bladder and bowel "
          "normal.",
        o="{vitals}. Paraspinal muscle tenderness, SLR negative, power normal.",
        a="Mechanical low back pain.",
        p="Analgesia, warm compress, back care advice. Physiotherapy referral if not improving in 2 weeks.",
        dx=["M54.5"], labs=[], drugs=["diclo", "pcm"]),
    "conjunctivitis": dict(
        weight=_w(adult=3, child=4, infant=1),
        complaints=["Red eyes and discharge", "Itchy red eyes", "Eye pain with discharge"],
        vitals={},
        s="Red, itchy eyes with sticky discharge for {days} days. Others at home have similar symptoms.",
        o="{vitals}. Bilateral conjunctival injection with mucopurulent discharge. Visual acuity normal.",
        a="Bacterial conjunctivitis.",
        p="Chloramphenicol eye drops QDS for 5 days. Hand hygiene, do not share towels.",
        dx=["H10.9"], labs=[], drugs=["chloramph"]),
    "skin": dict(
        weight=_w(adult=4, child=5, infant=1),
        complaints=["Itchy skin rash", "Ringworm on the body", "Rash on the neck and arms"],
        vitals={},
        s="Itchy, spreading skin lesions for {days} days. No new soaps or drugs.",
        o="{vitals}. Annular scaly plaques with raised edges on the trunk and arms.",
        a="Tinea corporis.",
        p="Clotrimazole cream BD for 2 weeks, continue 1 week after clearing. Cetirizine at night for itching. "
          "Keep skin dry.",
        dx=["B35.9"], labs=[], drugs=["clotrim", "cetirizine"]),
    "anaemia": dict(
        weight=_w(adult=3, child=3, elder=3),
        complaints=["Body weakness and dizziness", "Easy fatigability", "Palpitations and tiredness"],
        vitals={"pulse": (96, 112)},
        s="Easy fatigability, dizziness and palpitations for {days} days. Heavy menses / poor diet reported.",
        o="Pale conjunctivae. {vitals}. Soft flow murmur.",
        a="Anaemia, likely iron deficiency.",
        p="FBC, PCV. Ferrous sulphate and folic acid. Deworm. Diet counselling. Review with results.",
        dx=["D64.9"], labs=["LAB-FBC", "LAB-PCV"], drugs=["ferrous", "folic"]),
    "injury": dict(
        weight=_w(adult=3, child=2, elder=1), emergency_chance=0.4,
        complaints=["Cut on the hand", "Fell from a bike, leg wound", "Injury from a road traffic crash"],
        vitals={"pain": (5, 8), "pulse": (90, 110)},
        s="Sustained a laceration {days} hours ago. No loss of consciousness. Last tetanus vaccination unknown.",
        o="{vitals}. 4 cm clean laceration, no foreign body, distal neurovascular status intact.",
        a="Laceration, uncomplicated.",
        p="Wound cleaned and sutured under local anaesthesia. Tetanus toxoid. Analgesia. Wound review in 3 days, "
          "stitches off in 10 days.",
        dx=["T14.9"], labs=[], drugs=["tt", "pcm"]),
    "anc": dict(
        weight=lambda age, g: 0,
        complaints=["Antenatal clinic visit", "ANC booking", "Routine antenatal check"],
        vitals={"bp": (100, 128, 62, 82)},
        s="G{gravida}P{para}, {ga} weeks by LMP. Feels fetal movements. No vaginal bleeding, no headache, "
          "no leg swelling.",
        o="{vitals}. Fundal height corresponds to dates, cephalic, FHR 140/min. No oedema.",
        a="Normal pregnancy at {ga} weeks.",
        p="IPTp-SP given, haematinics continued. HIV, HBsAg, VDRL, PCV, urinalysis, blood group and genotype. "
          "Sleep under ITN. Next visit in 4 weeks.",
        dx=["Z34.9"], labs=["LAB-PCV", "LAB-UA", "LAB-HIV", "LAB-HBSAG", "LAB-VDRL", "LAB-GXT"],
        drugs=["sp", "fefol", "tt"]),
    "checkup": dict(
        weight=_w(adult=4, elder=3, min_age=18),
        complaints=["Routine medical check-up", "Pre-employment medicals", "General check-up"],
        vitals={},
        s="Requests a general medical examination. No complaints.",
        o="Well. {vitals}. Systemic examination unremarkable.",
        a="General medical examination, no abnormality found.",
        p="FBC, FBS, lipid profile, urinalysis. Lifestyle counselling. Annual review.",
        dx=["Z00.0"], labs=["LAB-FBC", "LAB-FBS", "LAB-LIP", "LAB-UA"], drugs=[]),
}


# ------------------------------------------------------------------ helpers
def _local(day: date, minutes_after_midnight: float) -> datetime:
    """Local clock time on `day` as naive UTC, the way timestamps are stored."""
    dt = datetime.combine(day, time.min, tzinfo=TZ) + timedelta(minutes=minutes_after_midnight)
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


def _age_on(dob: date, day: date) -> int:
    return day.year - dob.year - ((day.month, day.day) < (dob.month, dob.day))


class Generator:
    def __init__(self, db, rnd: random.Random, patients: int, days: int, today_visits: int):
        self.db, self.r = db, rnd
        self.n_patients, self.n_days, self.n_today = patients, days, today_visits
        self.fac = db.scalar(select(Facility))
        self.staff = defaultdict(list)
        for s in db.scalars(select(Staff).where(Staff.is_active)).all():
            self.staff[s.role].append(s)
        self.icd = {c.code: c.description for c in db.scalars(select(Icd10)).all()}
        self.rows = defaultdict(list)                  # model -> objects, flushed in dependency order
        self.phones: set[str] = set()
        self.patients: list[Patient] = []
        self.allergies: dict[str, list[AllergyRecord]] = defaultdict(list)
        self.chronic: dict[str, set[str]] = defaultdict(set)
        self.pregnant: dict[str, dict] = {}
        self.last_visit: dict[str, date] = {}
        self.tickets_by_day = defaultdict(list)        # (day, dept) -> tickets, numbered before each flush
        self.later = []                                # (obj, attr, fn): text that quotes a ticket number
        self.voice_consent: set[str] = set()
        self.now = utcnow()
        self.today = local_today()
        self.counts = defaultdict(int)

    # -------------------------------------------------------------- write helpers
    def add(self, obj):
        self.rows[type(obj)].append(obj)
        return obj

    def flush(self):
        self.number_tickets()
        for obj, attr, fn in self.later:
            setattr(obj, attr, fn())
        self.later.clear()
        order = [Patient, AllergyRecord, Consent, Visit, Journey, JourneyStep, Ticket, Vitals, ScribeSession,
                 ClinicalNote, Diagnosis, NoteAddendum, LabOrder, MedicationOrder, Message, OutboxEvent, AuditLog]
        for model in order:
            objs = self.rows.pop(model, [])
            self.counts[model.__tablename__] += len(objs)
            self.db.add_all(objs)
            self.db.flush()

    def audit(self, at, staff, action, record_type, record_id=None, patient_id=None, detail=None):
        self.add(AuditLog(id=uid(), facility_id=self.fac.id, staff_id=staff.id if staff else None,
                          patient_id=patient_id, action=action, record_type=record_type, record_id=record_id,
                          detail=detail, at=at))

    def event(self, at, event_type, payload):
        """`payload` may be a callable when it quotes a ticket number (numbers are assigned at flush)."""
        ev = self.add(OutboxEvent(id=uid(), facility_id=self.fac.id, event_type=event_type, created_at=at,
                                  payload=None if callable(payload) else payload))
        if callable(payload):
            self.later.append((ev, "payload", payload))

    def sms(self, at, p: Patient, body):
        """`body` may be a callable, like event()."""
        m = self.add(Message(id=uid(), facility_id=self.fac.id, patient_id=p.id, to_phone=p.phone, created_at=at,
                             body="" if callable(body) else body))
        if callable(body):
            self.later.append((m, "body", body))

    def pick(self, role) -> Staff:
        return self.r.choice(self.staff[role])

    # -------------------------------------------------------------- people
    def phone(self) -> str:
        while True:
            p = self.r.choice(PHONE_PREFIXES) + f"{self.r.randrange(10**7):07d}"
            if p not in self.phones:
                self.phones.add(p)
                return p

    def dob(self) -> date:
        x = self.r.random()
        if x < 0.07:
            days = self.r.randint(20, 360)
        elif x < 0.27:
            days = int(self.r.uniform(1, 17.9) * 365.25)
        elif x < 0.85:
            days = int(self.r.triangular(18, 64.9, 32) * 365.25)
        else:
            days = int(self.r.uniform(65, 88) * 365.25)
        return self.today - timedelta(days=days)

    def new_patient(self, created: datetime, family_of: Patient | None = None) -> Patient:
        r = self.r
        if family_of:
            # a child registered on a parent's phone: same surname and number, the usual pattern at reception
            eth = next(k for k, v in ETHNIC.items() if family_of.surname in v["surnames"])
            surname, phone = family_of.surname, family_of.phone
            dob = self.today - timedelta(days=r.randint(60, 12 * 365))
            nok_name = f"{family_of.first_name} {family_of.surname}"
            nok_phone = family_of.phone
        else:
            eth = r.choices(list(ETHNIC_WEIGHTS), weights=list(ETHNIC_WEIGHTS.values()))[0]
            surname, phone, dob = r.choice(ETHNIC[eth]["surnames"]), self.phone(), self.dob()
            nok_name = (f"{r.choice(ETHNIC[eth]['male'] + ETHNIC[eth]['female'])} "
                        f"{r.choice([surname, r.choice(ETHNIC[eth]['surnames'])])}") if r.random() < 0.85 else None
            nok_phone = self.phone() if nok_name else None
        names = ETHNIC[eth]
        gender = "female" if r.random() < 0.53 else "male"
        first = r.choice(names[gender])
        middle = r.choice([n for n in names[gender] if n != first]) if r.random() < 0.55 else None
        hmo, hmo_no = None, None
        if r.random() < 0.33:
            hmo, code = r.choice(HMOS)
            hmo_no = f"{code}/{r.randint(2019, created.year)}/{r.randrange(10**6):06d}"
        year = created.year
        prefix = f"ARC-{self.fac.state_code}-{year}-"
        number = f"{prefix}{next_counter(self.db, f'patient_number:{prefix}'):06d}"
        reception = self.pick("reception")
        if dob >= created.date():
            dob = created.date() - timedelta(days=r.randint(14, 300))
        p = self.add(Patient(id=uid(), facility_id=self.fac.id, patient_number=number, surname=surname,
                             first_name=first, middle_name=middle, phone=phone, date_of_birth=dob, gender=gender,
                             category=reg.category_for(dob), nok_name=nok_name, nok_phone=nok_phone,
                             state_of_origin=r.choice(names["states"]), hmo_provider=hmo, hmo_number=hmo_no,
                             blood_group=r.choice(BLOOD_GROUPS) if r.random() < 0.7 else None,
                             registered_by=reception.id, created_at=created))
        self.patients.append(p)
        age = _age_on(dob, self.today)
        if r.random() < 0.12:
            for allergen, reaction, severity in self._allergies(r.choice([1, 1, 1, 2])):
                a = self.add(AllergyRecord(id=uid(), patient_id=p.id, allergen_name=allergen, reaction=reaction,
                                           severity=severity,
                                           drug_class=rules.drug_class_of(allergen) or allergen.lower(),
                                           recorded_by=reception.id, recorded_at=created))
                self.allergies[p.id].append(a)
        # chronic conditions that bring the patient back for follow-ups
        if age >= 35 and r.random() < (0.35 if age >= 55 else 0.15):
            self.chronic[p.id].add("I10")
        if age >= 40 and r.random() < 0.12:
            self.chronic[p.id].add("E11.9")
        if 2 <= age <= 35 and r.random() < 0.03:
            self.chronic[p.id].add("D57.0")
        if gender == "female" and 18 <= age <= 40 and r.random() < 0.18:
            self.pregnant[p.id] = {"ga": r.randint(12, 30), "gravida": r.randint(1, 5)}
        if r.random() < 0.75:
            self.add(Consent(id=uid(), facility_id=self.fac.id, patient_id=p.id, consent_type="sms", granted=True,
                             recorded_by=reception.id, at=created))
        if r.random() < 0.4:
            self.add(Consent(id=uid(), facility_id=self.fac.id, patient_id=p.id, consent_type="photo", granted=False,
                             recorded_by=reception.id, at=created))
        self.sms(created, p, reg.card_text(p, self.fac.name))
        self.event(created, "PatientRegistered", {"patient_id": p.id, "patient_number": p.patient_number})
        self.audit(created, reception, "create", "patient", p.id, p.id)
        return p

    def _allergies(self, n):
        picked = []
        while len(picked) < n:
            a = self.r.choices(ALLERGIES, weights=[x[3] for x in ALLERGIES])[0]
            if a[:3] not in picked:
                picked.append(a[:3])
        return picked

    # -------------------------------------------------------------- clinical content
    def scenario(self, p: Patient, day: date) -> tuple[str, str]:
        """(scenario key, visit type) for this patient on this day."""
        r, age = self.r, _age_on(p.date_of_birth, day)
        chronic, seen_before = self.chronic[p.id], p.id in self.last_visit
        if p.id in self.pregnant and r.random() < 0.7:
            return "anc", "anc"
        if seen_before and chronic and r.random() < 0.6:
            key = {"I10": "htn_followup", "E11.9": "diabetes", "D57.0": "sickle_crisis",
                   "J45.9": "asthma"}[r.choice(sorted(chronic))]
            return key, "new_complaint" if key in ("sickle_crisis", "asthma") else "follow_up"
        if "D57.0" in chronic and r.random() < 0.3:
            return "sickle_crisis", "new_complaint"
        keys = [k for k in SCENARIOS if SCENARIOS[k]["weight"](age, p.gender) > 0]
        key = r.choices(keys, weights=[SCENARIOS[k]["weight"](age, p.gender) for k in keys])[0]
        sc = SCENARIOS[key]
        if sc.get("emergency") or r.random() < sc.get("emergency_chance", 0):
            return key, "emergency"
        if seen_before and r.random() < 0.12:
            return key, "follow_up"          # review of a recent acute illness
        return key, "new_complaint"

    def vitals_for(self, p: Patient, day: date, spec: dict) -> dict:
        r, age = self.r, _age_on(p.date_of_birth, day)
        u = lambda lo, hi: r.uniform(lo, hi)    # noqa: E731
        if age < 1:
            # no RR and a calm pulse: flag_vitals uses adult limits and would mark every infant critical
            v = dict(pulse_rate=r.randint(110, 128), respiratory_rate=None, weight_kg=round(u(3.5, 10), 1),
                     height_cm=round(u(50, 75)), temperature=round(u(36.4, 37.3), 1), spo2=r.randint(96, 100))
        elif age < 12:
            v = dict(pulse_rate=r.randint(80, 115), respiratory_rate=r.randint(18, 28),
                     weight_kg=round(2 * age + 8 + u(-2, 4), 1), height_cm=round(75 + 6 * age + u(-5, 5)),
                     temperature=round(u(36.4, 37.3), 1), spo2=r.randint(96, 100))
        else:
            male = p.gender == "male"
            sys_ = r.randint(108, 134) + (8 if age >= 50 else 0)
            v = dict(bp_systolic=sys_, bp_diastolic=r.randint(68, 86), pulse_rate=r.randint(62, 92),
                     respiratory_rate=r.randint(14, 19), temperature=round(u(36.3, 37.3), 1), spo2=r.randint(96, 100),
                     weight_kg=round(u(62, 98) if male else u(52, 92), 1),
                     height_cm=round(u(162, 186) if male else u(152, 172)) if age >= 16 else round(u(145, 170)))
        v["pain_score"] = r.randint(0, 3)
        if "fever" in spec:
            v["temperature"] = round(u(*spec["fever"]), 1)
        if "bp" in spec and "bp_systolic" in v:
            v["bp_systolic"], v["bp_diastolic"] = r.randint(*spec["bp"][:2]), r.randint(*spec["bp"][2:])
            if r.random() < 0.04:              # the occasional hypertensive urgency
                v["bp_systolic"], v["bp_diastolic"] = r.randint(182, 196), r.randint(110, 122)
        if "pulse" in spec:
            v["pulse_rate"] = r.randint(*spec["pulse"])
        if "rr" in spec:
            v["respiratory_rate"] = r.randint(*spec["rr"])
        if "spo2" in spec:
            v["spo2"] = r.randint(*spec["spo2"])
        if "pain" in spec:
            v["pain_score"] = r.randint(*spec["pain"])
        if r.random() < 0.08:                  # nurses don't always weigh/measure
            v["height_cm"] = None
        return v

    @staticmethod
    def vitals_text(v: dict) -> str:
        parts = []
        if v.get("temperature") is not None:
            parts.append(f"T {v['temperature']}°C")
        if v.get("bp_systolic"):
            parts.append(f"BP {v['bp_systolic']}/{v['bp_diastolic']} mmHg")
        if v.get("pulse_rate"):
            parts.append(f"PR {v['pulse_rate']}/min")
        if v.get("respiratory_rate"):
            parts.append(f"RR {v['respiratory_rate']}/min")
        if v.get("spo2"):
            parts.append(f"SpO2 {v['spo2']}%")
        return ", ".join(parts)

    def drug_orders(self, p: Patient, keys: list[str], age: int) -> list[dict]:
        out, used = [], set()
        for key in keys:
            for candidate in [key] + ALTERNATIVES.get(key, []):
                spec = DRUGS[candidate][1 if age < 12 else 0]
                if not spec or candidate in used:
                    continue
                name, dose, freq, days, route = spec
                hits = rules.allergy_conflicts(name, self.allergies[p.id])
                if hits and self.r.random() < 0.9:
                    continue                    # the prescriber picks the alternative
                used.add(candidate)
                out.append(dict(drug_name=name, dose=dose, frequency=freq, duration_days=days, route=route,
                                allergy_override_reason=("Benefit outweighs risk; previous reaction mild and "
                                                         "patient monitored after first dose") if hits else None))
                break
        return out

    # -------------------------------------------------------------- one visit
    def visit(self, p: Patient, day: date, checkin_at: datetime, cut: datetime | None = None):
        """Builds a visit's whole timeline from check-in. With `cut` (today), events after that moment don't
        happen yet: the visit is left waiting, called or in service exactly where that moment falls."""
        r, age = self.r, _age_on(p.date_of_birth, day)
        key, vtype = self.scenario(p, day)
        sc = SCENARIOS[key]
        reception = self.pick("reception")
        track = "out_of_pocket"
        if p.hmo_provider and r.random() < 0.85:
            track = "hmo"
        elif r.random() < 0.03:
            track = r.choice(["staff", "government"])
        elif r.random() < 0.01:
            track, reception = "waiver", self.pick("admin")
        v = self.add(Visit(id=uid(), facility_id=self.fac.id, patient_id=p.id, visit_type=vtype, payment_track=track,
                           status="checked_in", checked_in_at=checkin_at, checked_in_by=reception.id))
        j = self.add(Journey(id=uid(), visit_id=v.id, patient_id=p.id, facility_id=self.fac.id,
                             status="in_progress", started_at=checkin_at))
        self.last_visit[p.id] = day
        if vtype == "emergency":
            tier = "EMERGENCY"
        elif vtype == "follow_up":
            tier = "FOLLOW_UP"
        elif vtype == "anc" or age < 5 or age >= 65:
            tier = "HIGH"
        else:
            tier = "NORMAL"
        happened = (lambda t: True) if cut is None else (lambda t: t <= cut)

        self.event(checkin_at, "VisitCheckedIn", {"visit_id": v.id, "patient_id": p.id, "visit_type": vtype,
                                                 "payment_track": track})
        self.audit(checkin_at, reception, "check_in", "visit", v.id, p.id)

        # ---- triage
        wait = {"EMERGENCY": (0, 3), "HIGH": (3, 25), "NORMAL": (5, 55), "FOLLOW_UP": (10, 70)}[tier]
        t_call = checkin_at + timedelta(minutes=r.uniform(*wait))
        t_arrive = t_call + timedelta(minutes=r.uniform(0.3, 2.5))
        t_done = t_arrive + timedelta(minutes=r.uniform(3, 9))
        tri_step = self.add(JourneyStep(id=uid(), journey_id=j.id, step_order=1, department="TRIAGE",
                                        status="active", created_at=checkin_at))
        tri = self.ticket(day, "TRIAGE", v, p, tri_step, tier, checkin_at)
        nurse = self.pick("nurse")
        tri.counter_name = r.choice(TRIAGE_COUNTERS)

        # patients who never answer their triage call
        if r.random() < 0.04 and tier != "EMERGENCY":
            no_show_1 = t_call + timedelta(seconds=settings.call_timeout_seconds)
            if not happened(t_call):
                return v
            tri.status, tri.called_at = "called", t_call
            if not happened(no_show_1):
                return v
            tri.status, tri.no_show_at, tri.no_show_count = "no_show", no_show_1, 1
            cancelled = no_show_1 + timedelta(seconds=settings.noshow_grace_seconds)
            if not happened(cancelled):
                return v
            tri.status, tri.completed_at = "cancelled", cancelled
            tri_step.status, tri_step.completed_at, tri_step.note = "abandoned", cancelled, \
                "no response within grace window"
            j.status, j.completed_at, v.status = "abandoned", cancelled, "abandoned"
            self.event(cancelled, "JourneyAbandoned", {"visit_id": v.id, "deferred": []})
            return v

        if not happened(t_call):
            return v
        tri.status, tri.called_at = "called", t_call
        self.sms(t_call, p, lambda: f"You are NEXT. {tri.ticket_number}. Please go to {tri.counter_name} now.")
        if not happened(t_arrive):
            return v
        tri.status, tri.confirmed_at = "in_service", t_arrive
        if not happened(t_done):
            return v
        vit = self.vitals_for(p, day, sc["vitals"])
        flags, critical = rules.flag_vitals(vit)
        abnormal = any(f["level"] == "abnormal" for f in flags)
        priority = "EMERGENCY" if critical or vtype == "emergency" else \
            "HIGH" if abnormal and r.random() < 0.6 or tier == "HIGH" else "NORMAL"
        complaint = r.choice(sc["complaints"]).format(days=r.randint(2, 6))
        scribe_nurse = r.random() < 0.06
        vitals = self.add(Vitals(id=uid(), visit_id=v.id, patient_id=p.id, recorded_by=nurse.id, recorded_at=t_done,
                                 chief_complaint=complaint, triage_priority=priority, flags=flags,
                                 bmi=rules.bmi(vit.get("weight_kg"), vit.get("height_cm")),
                                 source="ai_scribe" if scribe_nurse else "manual", **vit))
        if scribe_nurse:
            self.scribe(v, p, nurse, "nurse", t_done - timedelta(minutes=2), t_done,
                        f"Patient {p.first_name}, {complaint.lower()}. {self.vitals_text(vit)}.",
                        {"vitals": vit, "chief_complaint": complaint, "triage_priority": priority})
        self.audit(t_done, nurse, "create", "vitals", vitals.id, p.id)
        if critical:
            self.event(t_done, "CriticalVitals", {"visit_id": v.id,
                                                  "flags": [f for f in flags if f["level"] == "critical"]})
        v.status = "in_progress"
        self.event(t_done, "TriageCompleted", {"visit_id": v.id, "triage_priority": priority})
        tri.status, tri.completed_at, tri.priority_tier = "completed", t_done, priority
        tri_step.status, tri_step.completed_at = "completed", t_done
        self.event(t_done, "StepCompleted",
                   lambda: {"ticket": tri.ticket_number, "department": "TRIAGE", "visit_id": v.id})

        # ---- doctor
        opd_step = self.add(JourneyStep(id=uid(), journey_id=j.id, step_order=2, department="OPD-GEN",
                                        status="active", created_at=t_done))
        opd = self.ticket(day, "OPD-GEN", v, p, opd_step, priority, t_done)
        self.sms(t_done, p, lambda: f"Next: Doctor consultation. Queue number: {opd.ticket_number}.")
        wait = {"EMERGENCY": (0, 5), "HIGH": (8, 40), "NORMAL": (15, 95), "FOLLOW_UP": (20, 110)}[priority]
        o_call = t_done + timedelta(minutes=r.uniform(*wait))
        o_arrive = o_call + timedelta(minutes=r.uniform(0.5, 2.8))
        o_done = o_arrive + timedelta(minutes=r.uniform(7, 24))
        doctor = self.pick("doctor")
        opd.counter_name = r.choice(OPD_COUNTERS)

        if r.random() < 0.03 and priority != "EMERGENCY":      # left before seeing the doctor
            no_show_1 = o_call + timedelta(seconds=settings.call_timeout_seconds)
            cancelled = no_show_1 + timedelta(seconds=settings.noshow_grace_seconds)
            if not happened(o_call):
                return v
            opd.status, opd.called_at = "called", o_call
            if not happened(no_show_1):
                return v
            opd.status, opd.no_show_at, opd.no_show_count = "no_show", no_show_1, 1
            if not happened(cancelled):
                return v
            opd.status, opd.completed_at = "cancelled", cancelled
            opd_step.status, opd_step.completed_at, opd_step.note = "abandoned", cancelled, \
                "no response within grace window"
            # the live journey rule: only all-abandoned steps make an abandoned journey
            j.status, j.completed_at, v.status = "completed", cancelled, "completed"
            self.event(cancelled, "JourneyClinicalCompleted", {"visit_id": v.id, "deferred": []})
            return v

        if not happened(o_call):
            return v
        opd.status, opd.called_at = "called", o_call
        self.sms(o_call, p, lambda: f"You are NEXT. {opd.ticket_number}. Please go to {opd.counter_name} now.")
        if not happened(o_arrive):
            return v
        opd.status, opd.confirmed_at = "in_service", o_arrive
        self.audit(o_arrive, doctor, "view", "chart", p.id, p.id)
        self.audit(o_arrive + timedelta(seconds=20), doctor, "view", "visit", v.id, p.id)
        if not happened(o_arrive + timedelta(minutes=5)):
            return v                            # with the doctor, nothing written yet

        # note content
        fill = dict(vitals=self.vitals_text(vit), days=r.randint(2, 6), age=age,
                    control="well controlled" if (vit.get("bp_systolic") or 0) < 140 else "suboptimal control",
                    **({"ga": self.pregnant[p.id]["ga"], "gravida": self.pregnant[p.id]["gravida"],
                        "para": self.pregnant[p.id]["gravida"] - 1} if key == "anc" else {}))
        if key == "anc":
            self.pregnant[p.id]["ga"] = min(40, self.pregnant[p.id]["ga"] + 4)
        subjective = sc["s"].format(**fill)
        if self.allergies[p.id]:
            subjective += " Known allergy: " + ", ".join(a.allergen_name for a in self.allergies[p.id]) + "."
        note = self.add(ClinicalNote(id=uid(), visit_id=v.id, patient_id=p.id, template_used=sc.get("template")
                                     if r.random() < 0.5 else None, status="draft", subjective=subjective,
                                     objective=sc["o"].format(**fill), assessment=sc["a"].format(**fill),
                                     plan=sc["p"].format(**fill), authored_by=doctor.id,
                                     created_at=o_arrive + timedelta(minutes=2)))
        dx_codes = list(sc["dx"])
        for code in sorted(self.chronic[p.id]):          # comorbidities carried onto the note
            if code not in dx_codes and r.random() < 0.5:
                dx_codes.append(code)
        dx_codes = [c for c in dx_codes if c in self.icd]
        for i, code in enumerate(dx_codes):
            self.add(Diagnosis(id=uid(), note_id=note.id, visit_id=v.id, patient_id=p.id, icd10_code=code,
                               icd10_description=self.icd[code], diagnosis_type="primary" if i == 0 else "secondary",
                               diagnosed_by=doctor.id, diagnosed_at=o_arrive + timedelta(minutes=3)))
        for code in sc["dx"]:
            if code in ("I10", "E11.9", "D57.0", "J45.9"):
                self.chronic[p.id].add(code)
        labs = [c for c in sc["labs"] if r.random() < 0.85]
        lab_rows = [self.add(LabOrder(id=uid(), visit_id=v.id, patient_id=p.id, ordered_by=doctor.id, test_code=c,
                                      test_name=LABS[c], priority="stat" if priority == "EMERGENCY" or c == "LAB-MAL"
                                      else "routine", status="ordered", ordered_at=o_arrive + timedelta(minutes=4)))
                    for c in labs]
        med_rows = []
        for d in self.drug_orders(p, sc["drugs"], age):
            m = self.add(MedicationOrder(id=uid(), visit_id=v.id, patient_id=p.id, ordered_by=doctor.id,
                                         instructions="Take after meals" if d["route"] == "oral" and r.random() < 0.3
                                         else None, status="ordered", ordered_at=o_arrive + timedelta(minutes=5), **d))
            med_rows.append(m)
            if m.allergy_override_reason:
                self.audit(m.ordered_at, doctor, "allergy_override", "medication_order", m.id, p.id,
                           detail=m.allergy_override_reason)
            self.audit(m.ordered_at, doctor, "create", "medication_order", m.id, p.id)
        if r.random() < 0.08:
            note.source = "ai_scribe"
            note.scribe_session_id = self.scribe(
                v, p, doctor, "doctor", o_arrive + timedelta(minutes=1), o_arrive + timedelta(minutes=3),
                f"{note.subjective} On examination {note.objective} Impression: {note.assessment} Plan: {note.plan}",
                {"subjective": note.subjective, "objective": note.objective, "assessment": note.assessment,
                 "plan": note.plan, "suggested_diagnoses": [self.icd[c] for c in dx_codes],
                 "suggested_labs": [LABS[c] for c in labs],
                 "suggested_drugs": [{"drug_name": m.drug_name, "dose": m.dose, "frequency": m.frequency,
                                      "duration_days": m.duration_days} for m in med_rows]})
        self.audit(note.created_at, doctor, "edit", "clinical_note", note.id, p.id)
        if not happened(o_done):
            return v

        # ---- sign: same rules and hash as POST /ehr/notes/{id}/sign
        blob = json.dumps({"s": note.subjective, "o": note.objective, "a": note.assessment, "p": note.plan,
                           "dx": sorted(dx_codes), "labs": sorted(l.test_code for l in lab_rows),
                           "rx": sorted(m.drug_name for m in med_rows), "by": doctor.id}, sort_keys=True)
        note.status, note.signed_by, note.signed_at = "signed", doctor.id, o_done
        note.content_hash = hashlib.sha256(blob.encode()).hexdigest()
        for o in lab_rows + med_rows:
            o.status = "sent"
        order = 3
        deferred = []
        for dept, rows_, ev, summary in (("LAB", lab_rows, "LabOrdered", ", ".join(l.test_name for l in lab_rows)),
                                         ("PHARM", med_rows, "Prescribed", ", ".join(m.drug_name for m in med_rows))):
            if not rows_:
                continue
            self.event(o_done, ev, {"visit_id": v.id, "patient_id": p.id, "summary": summary,
                                    **({"tests": [l.test_code for l in lab_rows]} if dept == "LAB" else
                                       {"drugs": [m.drug_name for m in med_rows]})})
            self.add(JourneyStep(id=uid(), journey_id=j.id, step_order=order, department=dept, status="deferred",
                                 created_by="doctor", note=summary, created_at=o_done))
            order += 1
            deferred.append(dept)
        self.event(o_done, "NoteSigned", {"visit_id": v.id, "patient_id": p.id, "note_id": note.id,
                                          "note_type": "soap", "icd10": dx_codes, "source": note.source})
        self.audit(o_done, doctor, "sign", "clinical_note", note.id, p.id,
                   detail=f"hash={note.content_hash[:12]} source={note.source}")
        opd.status, opd.completed_at = "completed", o_done
        opd_step.status, opd_step.completed_at = "completed", o_done
        j.status, j.completed_at, v.status = "completed", o_done, "completed"
        self.event(o_done, "JourneyClinicalCompleted", {"visit_id": v.id, "deferred": deferred})
        self.lab_and_pharmacy(p, lab_rows, med_rows, o_done, priority, happened)
        if r.random() < 0.03:
            later = o_done + timedelta(hours=r.uniform(1, 30))
            if happened(later):
                self.add(NoteAddendum(id=uid(), note_id=note.id, added_by=doctor.id, added_at=later,
                                      text=r.choice(["Lab result reviewed: consistent with working diagnosis. "
                                                     "Plan unchanged.",
                                                     "Patient called back: symptoms improving on treatment.",
                                                     "Correction: duration of symptoms was 5 days, not 3."]),
                                      reason=r.choice(["Result review", "Telephone follow-up", "Correction"])))
                self.audit(later, doctor, "addendum", "clinical_note", note.id, p.id)
        return v

    def lab_and_pharmacy(self, p, lab_rows, med_rows, signed_at, priority, happened):
        """After the note is signed: the lab works the orders (a few come back critical), the pharmacy dispenses."""
        r = self.r
        arrive = signed_at + timedelta(minutes=r.uniform(10, 60))          # walks over, pays, gives the sample
        for o in lab_rows:
            if r.random() < 0.02:
                continue                                                  # never went to the lab
            started = arrive + timedelta(minutes=r.uniform(2, 25))
            hours = SLOW_LABS.get(o.test_code)
            done = started + (timedelta(hours=r.uniform(*hours)) if hours else timedelta(minutes=r.uniform(15, 140)))
            if not happened(started):
                continue
            o.status, o.started_at = "in_progress", started
            if not happened(done):
                continue
            normal, abnormal, critical = LAB_RESULTS.get(o.test_code, (lambda _: "Within normal limits", None, None))
            x = r.random()
            crit_chance = 0.2 if priority == "EMERGENCY" else 0.03
            pos_chance = 0.55 if o.test_code in ("LAB-MAL", "LAB-MP") else 0.25
            if critical and x < crit_chance:
                flag, text = "critical", critical(r)
            elif abnormal and x < crit_chance + pos_chance:
                flag, text = "abnormal", abnormal(r)
            else:
                flag, text = "normal", normal(r)
            scientist = self.pick("lab")
            o.status, o.result_text, o.result_flag = "resulted", text, flag
            o.resulted_by, o.resulted_at = scientist.id, done
            self.event(done, "LabResulted", {"visit_id": o.visit_id, "patient_id": p.id, "order_id": o.id,
                                             "test": o.test_name, "flag": flag})
            self.audit(done, scientist, "result", "lab_order", o.id, p.id, detail=flag)
        dispense_at = signed_at + timedelta(minutes=r.uniform(8, 45))
        if med_rows and r.random() < 0.93 and happened(dispense_at):        # some buy their drugs outside
            pharmacist = self.pick("pharmacy")
            for m in med_rows:
                m.status, m.dispensed_by, m.dispensed_at = "dispensed", pharmacist.id, dispense_at
            self.event(dispense_at, "Dispensed", {"visit_id": med_rows[0].visit_id, "patient_id": p.id,
                                                  "drugs": [m.drug_name for m in med_rows]})
            self.audit(dispense_at, pharmacist, "dispense", "medication_order", med_rows[0].id, p.id,
                       detail=f"{len(med_rows)} items")

    def ticket(self, day, dept, v, p, step, tier, at) -> Ticket:
        t = self.add(Ticket(id=uid(), facility_id=self.fac.id, department=dept, day=day, journey_step_id=step.id,
                            visit_id=v.id, patient_id=p.id, ticket_number="", sequence_number=0, priority_tier=tier,
                            priority_aged=False, status="waiting", issued_at=at, entered_waiting_at=at,
                            no_show_count=0))
        self.tickets_by_day[(day, dept)].append(t)
        return t

    def scribe(self, v, p, staff, role, at, accepted_at, transcript, draft) -> str:
        if p.id not in self.voice_consent:
            self.voice_consent.add(p.id)
            self.add(Consent(id=uid(), facility_id=self.fac.id, patient_id=p.id, consent_type="voice_scribe",
                             granted=True, recorded_by=staff.id, at=at - timedelta(minutes=1)))
        s = self.add(ScribeSession(id=uid(), facility_id=self.fac.id, visit_id=v.id, patient_id=p.id,
                                   staff_id=staff.id, role=role, transcript=transcript, draft=draft, dropped=[],
                                   engine={"asr": f"faster-whisper:{settings.whisper_model}",
                                           "llm": f"ollama:{settings.ollama_model}"},
                                   status="accepted", created_at=at, accepted_at=accepted_at))
        self.audit(at, staff, "scribe_draft", "scribe_session", s.id, p.id)
        self.audit(accepted_at, staff, "scribe_accepted", "scribe_session", s.id, p.id)
        return s.id

    def number_tickets(self):
        """Ticket numbers in issue order per department/day, and the queue counters the live code continues from."""
        for (day, dept), tickets in self.tickets_by_day.items():
            tickets.sort(key=lambda t: t.issued_at)
            for i, t in enumerate(tickets, 1):
                t.sequence_number, t.ticket_number = i, f"{PREFIX.get(dept, dept[:3])}-{i:03d}"
            st = self.db.scalar(select(QueueState).where(QueueState.facility_id == self.fac.id,
                                                         QueueState.department == dept, QueueState.day == day))
            if not st:
                st = QueueState(id=uid(), facility_id=self.fac.id, department=dept, day=day, p1_streak=0, p2_streak=0)
                self.db.add(st)
            st.last_seq = len(tickets)
        self.tickets_by_day.clear()

    # -------------------------------------------------------------- the whole run
    def run(self):
        r = self.r
        first_day = self.today - timedelta(days=self.n_days)
        # about 40% of the patients were registered before the history window and come back during it
        existing = int(self.n_patients * 0.4)
        for at in sorted(_local(first_day - timedelta(days=r.randint(1, 700)), r.uniform(450, 960))
                         for _ in range(existing)):
            p = self.new_patient(at)
            if r.random() < 0.6:
                self.last_visit[p.id] = at.date()         # registered at an earlier visit: can come for follow-up
        self.flush()

        days = [first_day + timedelta(days=i) for i in range(self.n_days)]
        busy = [{0: 1.3, 1: 1.1, 2: 1.0, 3: 1.0, 4: 1.1, 5: 0.45, 6: 0.2}[d.weekday()] for d in days]
        new_budget = self.n_patients - existing
        for day, w in zip(days, busy):
            n_new = round(new_budget * w / sum(busy))
            returning = self.returning(day, max(1, round(r.uniform(10, 20) * w)))
            for p in self.new_patients(day, n_new, lambda: _local(day, r.uniform(450, 900))):   # 07:30-15:00
                self.visit(p, day, p.created_at + timedelta(minutes=r.uniform(1, 4)))
            for p in returning:
                self.visit(p, day, _local(day, r.uniform(450, 900)))
            self.flush()

        # today: arrivals over the last few hours, cut at now, so every queue state shows up
        since_midnight = (self.now - _local(self.today, 0)).total_seconds() / 60
        window = max(1.0, min(240.0, since_midnight - 1))
        n_new = max(2, self.n_today // 4)
        returning = self.returning(self.today, self.n_today - n_new)
        arrival = lambda: self.now - timedelta(minutes=r.uniform(0, window))     # noqa: E731
        for p in self.new_patients(self.today, n_new, arrival):
            self.visit(p, self.today, min(self.now, p.created_at + timedelta(minutes=r.uniform(1, 4))),
                       cut=self.now)
        for p in returning:
            self.visit(p, self.today, arrival(), cut=self.now)
        self.flush()
        self.db.commit()

    def new_patients(self, day: date, n: int, when) -> list[Patient]:
        out = []
        for _ in range(n):
            parent = out[-1] if out and self.r.random() < 0.12 else None
            if parent and _age_on(parent.date_of_birth, day) >= 22:
                out.append(self.new_patient(when(), family_of=parent))
            else:
                out.append(self.new_patient(when()))
        return out

    def returning(self, day: date, n: int) -> list[Patient]:
        """Patients registered before `day` who come back: chronic and ANC patients about monthly, others now
        and then. Weighted sampling without replacement (key = u ** (1/weight))."""
        cands = []
        for p in self.patients:
            if p.created_at >= _local(day, 0):
                continue
            last = self.last_visit.get(p.id)
            regular = bool(self.chronic[p.id]) or p.id in self.pregnant
            if last and (day - last).days < (21 if regular else 10):
                continue
            cands.append((self.r.random() ** (1 / (6 if regular else 1)), p))
        cands.sort(key=lambda t: t[0], reverse=True)
        return [p for _, p in cands[:n]]


# ------------------------------------------------------------------ reset / entry point
MOCK_TABLES = [NoteAddendum, Diagnosis, ClinicalNote, LabOrder, MedicationOrder, Vitals, ScribeSession, AllergyRecord,
               Ticket, JourneyStep, Journey, QueueState, Visit, Consent, Patient, Message, OutboxEvent, AuditLog]


def reset(db):
    if pulse_demo is not None and hasattr(pulse_demo, "reset"):
        pulse_demo.reset(db)            # AraPulse rows point at patients and visits: they go first
    for model in MOCK_TABLES:
        db.execute(delete(model))
    db.execute(delete(Counter).where(Counter.key.like("patient_number:%")))
    db.commit()


PROFILE = {"address": "1 Hospital Road, Alausa", "phone": "0803 000 1234", "email": "info@ghikeja.example.ng",
           "motto": "Quality care, close to home", "facility_type": "general", "ownership": "state",
           "license_number": "LSMOH/HF/2014/0457", "city": "Ikeja", "lga": "Ikeja", "emergency_phone": "0809 112 2112",
           "website": "https://ghikeja.example.ng", "bed_capacity": 184}


def ensure_staff(db, password: str):
    """A demo database looks like a hospital that is already running: full profile, onboarded, every suggested
    department and ward, and every demo account with a position and department."""
    fac = db.scalar(select(Facility))
    for k, v in PROFILE.items():
        if getattr(fac, k) in (None, ""):
            setattr(fac, k, v)
    create_suggested(db, fac.id, [code for code, *_ in SUGGESTED])
    add_demo_staff(db, fac, password, MOCK_STAFF)
    db.flush()
    if fac.onboarded_at is None:
        admin = db.scalar(select(Staff).where(Staff.facility_id == fac.id, Staff.role == "admin")
                          .order_by(Staff.username))
        fac.onboarded_at, fac.onboarded_by = utcnow() - timedelta(days=60), admin.id if admin else None
    for s in db.scalars(select(Staff).where(Staff.username.in_(OFF_DUTY))).all():
        s.on_duty = False
    db.commit()


def main(argv=None):
    ap = argparse.ArgumentParser(description="Fill the database with realistic mock data for testing.")
    ap.add_argument("--reset", action="store_true", help="delete existing patients/visits/queues/notes/logs first")
    ap.add_argument("--patients", type=int, default=400, help="patients registered over the period (default 400)")
    ap.add_argument("--days", type=int, default=42, help="days of completed history before today (default 42)")
    ap.add_argument("--today", type=int, default=30, help="visits checked in today (default 30)")
    ap.add_argument("--seed", type=int, default=2026, help="random seed (same seed, same data)")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    if settings.is_production:
        raise SystemExit("Refusing to write mock data with ARACARE_ENV=production.")
    migrate()
    seed()
    with SessionLocal() as db:
        if db.scalar(select(Patient.id)) is not None:
            if not args.reset:
                raise SystemExit("The database already has patients. Run with --reset to replace them with mock data.")
            reset(db)
        ensure_staff(db, "demo123")
        g = Generator(db, random.Random(args.seed), args.patients, args.days, args.today)
        g.run()
        if pulse_demo is not None and hasattr(pulse_demo, "fill"):
            pulse_demo.fill(db, g.fac)
            db.commit()
        log.info("Mock data written to %s", settings.database_url)
        for table, n in sorted(g.counts.items()):
            log.info("  %-20s %6d", table, n)
        log.info("Staff logins (password demo123): reception, nurse, doctor, lab, pharmacy, admin, plus %s",
                 ", ".join(u for u, *_ in MOCK_STAFF))


if __name__ == "__main__":
    main()
