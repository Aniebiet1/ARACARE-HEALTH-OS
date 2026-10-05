"""Turns a transcript into a STRUCTURED DRAFT. It never writes to the record; a clinician reviews and signs.

Safety design:
  * the LLM may only fill fields it can support with the transcript (prompted to leave others empty)
  * numeric vitals are GROUNDED: any number not literally present in the transcript is dropped
  * suggestions (diagnoses, labs, drugs) are chips the clinician must accept; allergy checks still run on accept
"""
import json
import logging
import re

import httpx
from pydantic import BaseModel, Field, ValidationError

from ...config import settings

log = logging.getLogger("aracare.scribe.structure")


class NurseVitals(BaseModel):
    bp_systolic: int | None = None
    bp_diastolic: int | None = None
    pulse_rate: int | None = None
    respiratory_rate: int | None = None
    temperature: float | None = None
    spo2: int | None = None
    weight_kg: float | None = None
    height_cm: float | None = None
    pain_score: int | None = None


class NurseDraft(BaseModel):
    vitals: NurseVitals = NurseVitals()
    chief_complaint: str = ""
    triage_priority: str = "NORMAL"


class DrugSuggestion(BaseModel):
    drug_name: str
    dose: str | None = None
    frequency: str | None = None
    duration_days: int | None = None


class DoctorDraft(BaseModel):
    subjective: str = ""
    objective: str = ""
    assessment: str = ""
    plan: str = ""
    suggested_diagnoses: list[str] = Field(default_factory=list)   # free-text terms, mapped to ICD-10 later
    suggested_labs: list[str] = Field(default_factory=list)
    suggested_drugs: list[DrugSuggestion] = Field(default_factory=list)


NURSE_SYSTEM = """You are a clinical scribe for a nurse at a Nigerian hospital triage desk.
Extract ONLY what the nurse explicitly says. Never infer, estimate or invent values.
If a value was not stated, return null. Return JSON matching the schema.
- vitals: bp_systolic/bp_diastolic (e.g. 'one twenty over eighty' = 120/80), pulse_rate (bpm), respiratory_rate,
  temperature (Celsius), spo2 (%), weight_kg, height_cm, pain_score (0-10).
- chief_complaint: the patient's main complaint in one short sentence, in the nurse's words.
- triage_priority: NORMAL unless the nurse clearly says high priority (HIGH) or emergency (EMERGENCY)."""

DOCTOR_SYSTEM = """You are a clinical scribe for a doctor at a Nigerian hospital. Convert the consultation dictation into a SOAP note.
Use ONLY information present in the dictation. Do not add findings, history, or drugs that were not mentioned.
Leave a section as an empty string if it was not discussed. Write concise clinical English.
- subjective: history and complaints reported by the patient.
- objective: examination findings and results stated by the doctor.
- assessment: the doctor's impression/diagnosis in words.
- plan: what the doctor says they will do (investigations, treatment, advice, follow-up).
- suggested_diagnoses: diagnosis names as plain text (the system maps them to ICD-10).
- suggested_labs: investigations the doctor asked for.
- suggested_drugs: drugs the doctor stated, with dose/frequency/duration only if stated.
Return JSON matching the schema."""


# --------------------------------------------------------------------- grounding
_NUM = re.compile(r"\d+(?:\.\d+)?")


def _numbers(text: str) -> set[float]:
    return {float(x) for x in _NUM.findall(text)}


def ground_vitals(vitals: NurseVitals, transcript: str) -> tuple[NurseVitals, list[str]]:
    """Drop any numeric value that does not literally appear in the transcript."""
    present, dropped, clean = _numbers(transcript), [], vitals.model_dump()
    for field, val in vitals.model_dump().items():
        if val is not None and float(val) not in present:
            clean[field] = None
            dropped.append(f"{field}={val} (not found in transcript)")
    return NurseVitals(**clean), dropped


# --------------------------------------------------------------------- rule-based fallback
def _num(pattern: str, text: str, cast=float):
    m = re.search(pattern, text, re.I)
    return cast(m.group(1)) if m else None


def rules_nurse(t: str) -> NurseDraft:
    bp = re.search(r"(\d{2,3})\s*(?:over|/|by)\s*(\d{2,3})", t, re.I)
    v = NurseVitals(
        bp_systolic=int(bp.group(1)) if bp else None, bp_diastolic=int(bp.group(2)) if bp else None,
        temperature=_num(r"temp(?:erature)?\D{0,15}(\d{2}(?:\.\d)?)", t),
        pulse_rate=_num(r"(?:pulse|heart rate)\D{0,15}(\d{2,3})", t, int),
        respiratory_rate=_num(r"(?:respiratory rate|respiration|resp rate|\brr\b|breathing)\D{0,15}(\d{2})", t, int),
        spo2=_num(r"(?:sp\s?o\s?2|saturation|oxygen)\D{0,15}(\d{2,3})", t, int),
        weight_kg=_num(r"(\d{2,3}(?:\.\d)?)\s*(?:kg|kilo)", t),
        height_cm=_num(r"(\d{3}(?:\.\d)?)\s*(?:cm|centimet)", t),
        pain_score=_num(r"pain\D{0,15}(\d{1,2})", t, int))
    cc = re.search(r"(?:complain\w*|presents? with|reports?|c/o)\s+(?:of\s+)?([^.]+)", t, re.I)
    priority = "EMERGENCY" if re.search(r"emergency|unconscious|convuls|seizure", t, re.I) else "NORMAL"
    return NurseDraft(vitals=v, chief_complaint=(cc.group(1).strip() if cc else ""), triage_priority=priority)


_SECTION_CUES = [("objective", r"on examination|examination|o/e|exam\b|findings?"),
                 ("assessment", r"assessment|impression|diagnosis|diagnosed|i think|likely"),
                 ("plan", r"plan|treatment|prescribe|start|will give|advice|review in|follow[- ]up|send for|order")]


def rules_doctor(t: str) -> DoctorDraft:
    """Cheap sentence router: used only if no local LLM is running. Clearly labelled as rules-based."""
    out = {"subjective": [], "objective": [], "assessment": [], "plan": []}
    for sent in re.split(r"(?<=[.!?])\s+", t.strip()):
        for sect, cue in _SECTION_CUES:
            if re.search(cue, sent, re.I):
                out[sect].append(sent)
                break
        else:
            out["subjective"].append(sent)
    drugs = []
    for m in re.finditer(r"\b(artemether[- ]lumefantrine|paracetamol|amoxicillin|ciprofloxacin|azithromycin|"
                         r"metformin|amlodipine|lisinopril|ibuprofen|diclofenac|ceftriaxone|coartem|augmentin)\b",
                         t, re.I):
        name = m.group(1).title()
        if not any(d.drug_name.lower() == name.lower() for d in drugs):
            drugs.append(DrugSuggestion(drug_name=name))
    labs = [n for n, pat in (("Malaria RDT", r"malaria (?:rdt|test)|\brdt\b"), ("Full Blood Count", r"\bfbc\b|full blood count"),
                             ("Typhoid (Widal)", r"widal"), ("Urinalysis", r"urinalysis"))
            if re.search(pat, t, re.I)]
    dx = [d for d in ("malaria", "typhoid", "hypertension", "diabetes", "pneumonia", "asthma", "urinary tract infection")
          if re.search(d, t, re.I)]
    return DoctorDraft(subjective=" ".join(out["subjective"]), objective=" ".join(out["objective"]),
                       assessment=" ".join(out["assessment"]), plan=" ".join(out["plan"]),
                       suggested_diagnoses=dx, suggested_labs=labs, suggested_drugs=drugs)


# --------------------------------------------------------------------- local LLM (Ollama)
def llm_engine_name() -> str:
    return "rules" if settings.llm_engine == "rules" else f"ollama:{settings.ollama_model}"


def _ollama(role: str, transcript: str, context: str) -> dict:
    schema = (NurseDraft if role == "nurse" else DoctorDraft).model_json_schema()
    r = httpx.post(f"{settings.ollama_url}/api/chat", timeout=settings.ollama_timeout, json={
        "model": settings.ollama_model, "stream": False, "format": schema,
        "think": False,  # thinking models (qwen3) otherwise burn the timeout reasoning before the JSON
        "options": {"temperature": 0, "num_ctx": 4096},
        "messages": [{"role": "system", "content": NURSE_SYSTEM if role == "nurse" else DOCTOR_SYSTEM},
                     {"role": "user", "content": f"CONTEXT (do not copy into the note unless dictated):\n{context}\n\n"
                                                 f"DICTATION:\n{transcript}"}]})
    r.raise_for_status()
    return json.loads(r.json()["message"]["content"])


def build_draft(role: str, transcript: str, context: str = "") -> tuple[dict, list[str], str]:
    """Returns (draft_dict, dropped_notes, engine_used). Never raises on model failure: falls back to rules."""
    model_cls = NurseDraft if role == "nurse" else DoctorDraft
    draft, engine = None, "rules"
    if settings.llm_engine != "rules":
        try:
            draft, engine = model_cls(**_ollama(role, transcript, context)), llm_engine_name()
        except (httpx.HTTPError, ValidationError, KeyError, json.JSONDecodeError) as e:
            if settings.llm_engine == "ollama":
                log.warning("Ollama failed (%s); using rule-based fallback", e)
            engine = "rules (local LLM unavailable)"
    if draft is None:
        draft = rules_nurse(transcript) if role == "nurse" else rules_doctor(transcript)
    dropped: list[str] = []
    if role == "nurse":
        draft.vitals, dropped = ground_vitals(draft.vitals, transcript)
        if draft.triage_priority not in ("NORMAL", "HIGH", "EMERGENCY"):
            draft.triage_priority = "NORMAL"
    return draft.model_dump(), dropped, engine
