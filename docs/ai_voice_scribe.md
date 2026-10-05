# AraCare — AI Voice Scribe
### Deep Dive: Clinical Documentation by Voice

---

## The Problem We're Actually Solving

Documentation in a Nigerian ward fails in ways that are structural, not a matter of staff discipline.

### Failure 1: There Is Nowhere to Type

A nurse on a 35-patient ward round has a clipboard, not a desk. Typing a structured SOAP note — Subjective, Objective, Assessment, Plan — means finding a chair, a flat surface, and five uninterrupted minutes that don't exist between 6am and the next emergency. The realistic alternative is a scrawled note on paper, transcribed into the EHR hours later from memory, or never transcribed at all.

**Result:** the EHR shows what was typed, not what happened. A vitals trend that mattered at 3am is missing because nobody had a hand free to write it down at 3am.

### Failure 2: Phone Dictation Doesn't Survive the Ward

Standard voice-to-text (phone keyboard dictation, generic dictation apps) assumes a quiet room and one speaker in clean English. A ward has generator noise, multiple conversations, crying, alarms, and clinicians who code-switch mid-sentence between English, Nigerian Pidgin, and a local language depending on who they're talking to. Generic ASR trained on American or British broadcast speech degrades badly here — not a little worse, often unusable.

**Result:** staff who try voice dictation once, get garbage output, and never try again. The tool has to work the first time or it gets abandoned.

### Failure 3: Handwriting Doesn't Scale Into a Structured Record

Paper notes are legible to the person who wrote them, for a while. They don't produce an ICD-10 code, they don't trigger a lab order, and six months later nobody — including the original author — can reliably read them. A structured EHR entry is what makes the rest of AraCare work (billing, lab orders, pharmacy); a paper slip sitting in a folder doesn't.

**Result:** the gap between "care was given" and "care is recorded" becomes permanent, not just delayed.

---

## What the Voice Scribe Does

1. **The clinician speaks** at the bedside, in whatever mix of English/Pidgin/local language is natural
2. **ASR transcribes it on-device**, so it works without ward connectivity and patient audio doesn't leave the building unprocessed
3. **An LLM drafts a structured SOAP note** from the cleaned transcript plus whatever's already known about the patient
4. **The clinician reviews, corrects, and signs** — exactly as they would a typed note
5. **It saves into the EHR using the identical schema** a typed note uses — nothing downstream can tell the difference

This is not a transcription product and not a chatbot. It is a faster path to the same signed note, for a workflow where typing isn't realistic.

---

## Part 1: The Dictation Session — State Machine

Every recording is a session with exactly one state at a time:

```
                    ┌─────────────┐
                    │    IDLE      │  ← mic armed, waiting for speech
                    └──────┬──────┘
                           │ voice-activity detected
                           ▼
                    ┌─────────────┐
               ┌───▶│  LISTENING   │  ← buffering audio in short chunks
               │    └──────┬──────┘
               │           │ pause > 2s, or clinician taps "done"
               │           ▼
               │    ┌─────────────┐
               │    │ TRANSCRIBING │  ← on-device Whisper pass
               │    └──────┬──────┘
               │           │
               │           ▼
               │    ┌─────────────┐
               │    │  CLEANING    │  ← local vocabulary correction pass
               │    └──────┬──────┘
               │           │
               │           ▼
               │    ┌─────────────┐
               │    │  STRUCTURING │  ← LLM drafts SOAP + ICD-10 suggestion
               │    └──────┬──────┘
               │           │
               │           ▼
               │    ┌─────────────┐
               │    │  IN_REVIEW   │  ← clinician edits against audio playback
               │    └──────┬──────┘
               │           │ clinician signs
      resume   │           ▼
   dictation ──┘    ┌─────────────┐
                     │   SIGNED     │  ← written to EHR, immutable
                     └─────────────┘
```

A clinician can return to LISTENING from IN_REVIEW to add more — a new vitals reading comes in, a lab result arrives mid-exam — without starting a new note. Nothing is SIGNED until the clinician explicitly signs; STRUCTURING never auto-commits.

---

## Part 2: Model Architecture — What Runs Where

| Stage | Model | Runs | Why here |
| --- | --- | --- | --- |
| ASR | Whisper (large-v3 or distil-whisper), quantized via whisper.cpp | On-device | Hospital connectivity is unreliable; raw patient audio shouldn't leave the building before it's even corrected |
| Vocabulary correction | Local phonetic/fuzzy-match dictionary | On-device | Needs to run even with zero connectivity; this is a lookup, not a model |
| SOAP structuring | Claude Haiku 4.5 (Sonnet 5 for multi-problem visits) | Cloud | Text-only by this point — far lower privacy exposure than streaming audio off-site |
| ICD-10 coding | Retrieval over a real code table, called by the LLM as a tool | Cloud | LLMs are unreliable at recalling exact codes from memory; retrieval removes that failure mode entirely |
| Drug/dosage validation | Rule-based lookup against the pharmacy formulary | Cloud or on-device | Deterministic check, not a model — the risk here is exactness, not language understanding |

**What we deliberately did not add:** a dedicated clinical model (BioBERT, ClinicalBERT, BioGPT, Meditron). They're trained on US/UK clinical corpora (MIMIC-III, PubMed), English-only, tuned for research-style entity extraction rather than clean note generation. They wouldn't understand Nigerian Pidgin or local disease vernacular any better than Claude does, and they're worse at the actual job — producing a well-formed note. A second model here would add latency and failure surface without fixing the thing that's actually risky (see Part 5).

---

## Part 3: Transcript Cleanup — The Local Vocabulary Pass

Whisper's base model will mishear terms it hasn't seen much of. A fixed correction dictionary, applied after transcription and before structuring, catches the predictable failures:

| Whisper is likely to output | Should become | Category |
| --- | --- | --- |
| "waste pain" | "waist pain" | Common symptom phrase |
| "body dey hot" | *(kept as-is — Pidgin, not an error)* | Pidgin passthrough |
| "catara" / "catarh" | "catarrh" | Local illness term |
| "artemether lumen" | "Artemether-Lumefantrine" | Drug name |
| "coartem" | "Coartem" (brand) → mapped to generic in structuring | Brand/generic mapping |
| "typhoid like fever" | "typhoid-like fever" | Diagnosis phrasing |

This dictionary is a living artifact — every correction a clinician makes during review (Part 4) is a candidate to add here, so the system gets better at exactly this hospital's speech patterns over time, not a generic benchmark.

---

## Part 4: Structuring — Transcript to SOAP

The LLM receives the cleaned transcript plus context already on file (triage vitals, chief complaint) and returns a structured draft. Example:

**Raw transcript (cleaned):**
> "Patient waist pain for three days, no fever, body dey hot small this morning. BP was one forty over ninety at triage. No vomiting. I'm thinking possible UTI, let's check urinalysis. Start her on ciprofloxacin five hundred mg twice daily for five days, and review in three days."

**Structured draft:**

```
S: Waist pain x3 days. Denies vomiting. Low-grade subjective fever this morning.
O: BP 140/90 (triage). No fever documented on exam.
A: Suspected urinary tract infection (ICD-10: N39.0 — suggested, not committed)
P: Urinalysis ordered. Ciprofloxacin 500mg BD x5 days. Review in 3 days.
```

The ICD-10 code is marked **suggested** until the clinician accepts it — see Part 5. The draft is never auto-signed.

---

## Part 5: Safety Nets

The real risk in this pipeline is exactness, not language understanding — a hallucinated code or a wrong dosage is a patient-safety problem a fluent sentence is not. Two deterministic checks sit around the LLM:

### ICD-10 as retrieval, not memory
The LLM calls a search tool against a real ICD-10 code table instead of generating a code from training data. This eliminates code hallucination as a failure mode entirely — the LLM can only return a code that exists.

### Drug/dosage validation against the formulary
Every medication and dose the LLM extracts into the Plan is checked against pharmacy's actual stock/formulary before the clinician sees it flagged:

| Check | Example catch |
| --- | --- |
| Dose out of adult/pediatric range | 500mg pediatric dose flagged on a 6-year-old |
| Drug not in hospital formulary | A brand name Whisper misheard, resolving to nothing real |
| Frequency outside normal bounds | "qid" transcribed where "bid" was said |
| Known contraindication on file | Drug conflicts with a documented allergy already in the chart |

A flag doesn't block signing — it highlights the line for the clinician to re-check against the audio before they sign.

---

## Part 6: EHR Integration

The signed note lands in Module 4 (EHR) through the identical schema a typed note uses: same fields, same ICD-10 problem-list commit, same cryptographic seal on signing. Lab orders, prescriptions, referrals, and admission requests all fire from the signature exactly as they do for a typed note — this module only changes how the clinician reaches a signed state, never what signing triggers.

---

## Part 7: Data Models

```sql
-- One row per dictation session
voice_sessions (
  id                UUID PRIMARY KEY,
  visit_id          UUID REFERENCES visits(id),
  clinician_id      UUID NOT NULL,
  status            ENUM('idle','listening','transcribing','cleaning',
                         'structuring','in_review','signed','abandoned'),
  device_id         VARCHAR,
  started_at        TIMESTAMP,
  signed_at         TIMESTAMP,
  resulting_note_id UUID REFERENCES clinical_notes(id)
)

-- Raw and cleaned transcript, kept for audit and model improvement
transcripts (
  id                UUID PRIMARY KEY,
  voice_session_id  UUID REFERENCES voice_sessions(id),
  raw_text          TEXT NOT NULL,
  cleaned_text      TEXT NOT NULL,
  asr_confidence    DECIMAL(4,3),           -- 0.000–1.000, segment-averaged
  low_confidence_spans JSONB,               -- [{start, end, text}] surfaced to reviewer
  audio_ref         VARCHAR                 -- local storage pointer, not uploaded
)

-- Structured draft before clinician edits
draft_notes (
  id                UUID PRIMARY KEY,
  voice_session_id  UUID REFERENCES voice_sessions(id),
  subjective        TEXT,
  objective         TEXT,
  assessment        TEXT,
  plan              TEXT,
  suggested_icd10   VARCHAR[],
  drug_flags        JSONB,                  -- [{drug, dose, issue}] from Part 5 checks
  generated_at      TIMESTAMP
)

-- Every edit a clinician makes, kept to improve the vocabulary dictionary (Part 3)
-- and to measure draft quality over time
draft_corrections (
  id                UUID PRIMARY KEY,
  draft_note_id     UUID REFERENCES draft_notes(id),
  field             ENUM('subjective','objective','assessment','plan','icd10','drug'),
  original_text     TEXT,
  corrected_text    TEXT,
  corrected_at      TIMESTAMP
)
```

---

## Part 8: Nigerian Edge Cases

| Scenario | How the Voice Scribe Handles It |
| --- | --- |
| **Clinician switches languages mid-sentence** | Whisper's multilingual decoding handles code-switching natively; the vocabulary pass (Part 3) is tuned per-phrase, not per-language, so it still fires regardless of which language the phrase is in |
| **Generator noise or ward alarms during dictation** | Voice-activity detection buffers only speech segments; low-confidence spans are flagged in the UI rather than silently guessed at |
| **Low-end Android device, poor built-in mic** | Hardware guidance (Part 9, open questions) specifies an external lapel/array mic as a requirement, not an accessory — the built-in mic is the primary failure point in ward testing |
| **No connectivity when the clinician is ready to sign** | ASR and vocabulary cleanup already ran on-device; only the structuring step needs connectivity. A queued draft can be structured on reconnect, or the clinician can type the note directly if they can't wait (see Open Questions) |
| **Clinician dictates in a dialect the vocabulary dictionary hasn't seen** | The draft still generates; a miss just means the clinician corrects more text than usual in review, and that correction feeds back into Part 3's dictionary |
| **Two clinicians round together, both speaking** | A session is bound to one clinician_id; the UI should make starting/stopping unambiguous — this is flagged as an interaction-design question, not a model problem |

---

## Summary: Key Design Decisions

| Decision | Choice | Reason |
| --- | --- | --- |
| ASR | Whisper, on-device, fine-tuned on local audio | Only broadly multilingual/code-switch-tolerant ASR; offline removes the connectivity dependency |
| Structuring model | Claude Haiku 4.5, escalate to Sonnet 5 | SOAP drafting is reasoning about note structure, not entity tagging — a general LLM beats a narrow clinical one |
| Dedicated clinical models (BioBERT etc.) | Rejected | Trained on US/UK data, English-only, weaker at clean note generation than a general LLM |
| ICD-10 coding | Retrieval tool, never freehand generation | Removes hallucinated-code risk entirely |
| Dosage safety | Deterministic formulary check, not a model | The risk is exactness; a rules check is auditable and doesn't need training data |
| Note schema | Identical to a typed note | Nothing downstream needs to know or care how the note was drafted |
| Audio handling | Processed on-device, never uploaded raw | Lowest-risk posture under NDPR for patient voice data |

---

## Open Questions / Next Steps

- [ ] Collect a consented corpus of real ward audio (English/Pidgin/Yoruba/Igbo/Hausa code-switching) to fine-tune Whisper on
- [ ] Choose mic hardware that survives ward noise and daily cleaning (lapel vs. bedside array) — built-in phone mics underperform badly in ward testing
- [ ] Define the offline fallback precisely: a queued draft structured on reconnect, vs. a hard fallback to typing when a note can't wait
- [ ] Decide how low-confidence ASR spans are surfaced in the review UI so clinicians know exactly what to double-check against the audio
- [ ] Design the session-ownership UX for multi-clinician rounds (ward rounds with a doctor + nurse + student all present)
