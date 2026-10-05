# AraCare Health OS: backend

Hospital operating system for Nigerian facilities. This repository holds the **backend API** and the
**design documents** (`docs/`). The web client lives in its own repository, `aracare-frontend`.

Current release (first slice): **patient registration and check-in, queue engine, EHR (triage and SOAP),
and an AI voice scribe** that runs fully locally. Billing, pharmacy/inventory and cloud sync are designed
(see `docs/`) and already have their event hooks; they are not built yet.

## Run it

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000     # API docs at http://localhost:8000/docs
pytest                                         # 23 tests
```

SQLite is used by default (zero setup, file `aracare.db`). For PostgreSQL set
`ARACARE_DATABASE_URL=postgresql+psycopg2://user:pass@localhost/aracare`.

Demo accounts (created on first start, password `demo123`): `reception`, `nurse`, `doctor`, `admin`.
Change `ARACARE_SECRET_KEY` for anything beyond a demo.

### Local AI scribe (no API, no cost)

| Part | What | Install |
|---|---|---|
| Speech to text | OpenAI **Whisper** weights (MIT) through `faster-whisper` | `pip install -r requirements-scribe.txt` (weights download on first use) |
| Note drafting | A local LLM served by **Ollama** | install Ollama, then `ollama pull qwen2.5:7b` |

Settings (environment variables, prefix `ARACARE_`): `WHISPER_MODEL` (`base` for weak machines, `small` default,
`medium` for accuracy), `WHISPER_DEVICE` (`cpu`/`cuda`), `OLLAMA_MODEL`, `OLLAMA_URL`,
`LLM_ENGINE` (`auto`|`ollama`|`rules`), `ASR_ENGINE` (`auto`|`none`).

If Whisper or Ollama is missing the system degrades instead of failing: dictation can be typed or pasted, and
drafting falls back to a simple rule-based extractor. The manual forms always work.

**Safety rules built into the scribe**
- It only produces a *draft*. Nothing reaches the record until a clinician reviews, saves and signs.
- The patient's consent to voice dictation is recorded (immutable) before audio can be processed.
- Audio is never stored; it is deleted right after transcription.
- Any vital sign the model returns that is not literally in the transcript is removed.
- Suggested diagnoses, labs and drugs are chips the clinician must accept; allergy checks still run on accept.
- Every use is written to the audit log, and signed notes record whether they came from dictation.

## Architecture in one paragraph

A modular monolith (FastAPI + SQLAlchemy). Each module owns its tables and talks to others only through
**domain events** written to a transactional outbox (`outbox_events`) and dispatched in-process:
`VisitCheckedIn`, `TriageCompleted`, `NoteSigned`, `LabOrdered`, `Prescribed`, `JourneyClinicalCompleted`, ...
Billing, pharmacy and cloud sync will subscribe to those same events. See `docs/architecture.md`.

```
backend/app/modules/
  core/          staff, roles, audit log, consent, outbox, outbound messages
  registration/  patients (ARC-LAG-2026-000001), duplicate detection, fuzzy search, check-in -> visit
  queues/        ticket state machine, weighted fair queuing + aging, journey cascade, TV display, WebSocket
  ehr/           vitals + flags, SOAP note (immutable once signed), ICD-10, allergy hard-block, orders
  scribe/        local Whisper + Ollama, grounding, consent gate
```

## API surface (all under `/api`)

`/auth/login` · `/patients`, `/patients/search`, `/patients/{id}/check-in` · `/queues/{dept}`,
`/queues/{dept}/call-next`, `/tickets/{id}/{arrived|no-show|rejoin|cancel}`, `/display/{dept}` (public TV),
`/ws/queue` · `/ehr/visits/{id}/triage`, `/ehr/visits/{id}/note`, `/ehr/notes/{id}/sign`, `/ehr/...` ·
`/scribe/consent`, `/scribe/transcribe`, `/scribe/draft` · `/admin/audit|events|messages`.

## Not built yet (by design)

Billing and cashier, pharmacy/inventory, lab module, ANC/paediatrics, document OCR, FHIR API, cloud sync,
real SMS gateway (messages are queued in `outbound_messages`), Redis (live queue state is in PostgreSQL/SQLite and
WebSockets are in-process; swap in Redis pub/sub when running more than one API process).
