# AraCare Health OS: backend

Hospital operating system for Nigerian facilities. This repository holds the **backend API** and the
**design documents** (`docs/`). The web client lives in its own repository, `aracare-frontend`.

Current release: **patient registration and check-in, queue engine, EHR (triage and SOAP), an AI voice scribe**
that runs fully locally, **admin onboarding and the Overview dashboard**, **AraPulse** (internal communications and
emergency paging), and lab/pharmacy worklists. Billing, inventory and cloud sync are designed (see `docs/`) and
already have their event hooks; they are not built yet.

## Run it (development)

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload --port 8000     # API docs at http://localhost:8000/docs
pytest
```

SQLite is used by default (zero setup, file `aracare.db`). For PostgreSQL set
`ARACARE_DATABASE_URL=postgresql+psycopg2://user:pass@localhost/aracare`.
The schema is managed by Alembic and upgraded automatically at startup; a database created by an older
build (before migrations existed) is detected and upgraded in place.

Demo accounts (development only, created on first start, password `demo123`): `reception`, `nurse`, `doctor`,
`lab` (Medical Laboratory Scientist), `pharmacy` (Pharmacist), `admin`. Development also gets the suggested
departments and wards, but the hospital is **not** marked onboarded, so `admin` sees the set-up wizard.

Mock data for demos: `python -m app.mock_data --reset` fills about six weeks of history plus a live queue for today:
lab results (a few critical), dispensed prescriptions, the full hospital profile (marked onboarded) and extra staff
(`reception2`, `nurse2`..`nurse6`, `doctor2`..`doctor6`, `lab2`, `pharmacy2`, same password), each with a position
and department.

## Deploy (one facility server)

```bash
cp .env.example .env          # fill in ARACARE_SECRET_KEY, POSTGRES_PASSWORD, ARACARE_ADMIN_PASSWORD, CORS origin
docker compose up -d --build  # PostgreSQL 16 + API on :8000; health at /api/health
```

With `ARACARE_ENV=production` the server **refuses to start** with a default or short secret key, or with
`*` as the CORS origin. No demo accounts are created: the first admin (`admin`) comes from
`ARACARE_ADMIN_PASSWORD` and must change that password on first login; the admin then creates staff accounts
(`/api/admin/staff`). Interactive API docs are off unless `ARACARE_ENABLE_DOCS=true`.

Operational notes:
- **Run exactly one API process** (the image does). The queue sweeper and WebSocket hub are in-process;
  more workers need Redis pub/sub first.
- Put it behind a reverse proxy with HTTPS (Caddy/nginx) if anything other than the LAN can reach it.
- Back up the database daily: `docker compose exec db pg_dump -U aracare aracare | gzip > aracare-$(date +%F).sql.gz`,
  plus the `appdata` volume (patient photos).
- Outpatient visits are day-bound: anything still open after local midnight (`ARACARE_TIMEZONE`) is closed as
  abandoned by the sweeper, so it never blocks the patient's next check-in.
- Accounts lock for 15 min after 5 wrong passwords; an admin password reset unlocks them. Password changes,
  resets, role changes and deactivation sign the person out everywhere.
- New schema changes: edit the models, then `cd backend && alembic revision --autogenerate -m "..."` and commit
  the file in `migrations/versions/`.

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

## Onboarding and organisation

On first sign-in the admin is walked through set-up (a web-client gate only: the API never blocks on it):
1. **Hospital profile**: name, type (`general|teaching|specialist|primary|clinic`), ownership
   (`federal|state|private|mission|ngo`), licence number, address, city, LGA, phone, emergency line, email, website,
   bed capacity, open 24 hours, motto, logo (`GET/PUT /admin/facility`, `POST/DELETE /admin/facility/logo`).
2. **Departments and wards**: ticked from a suggested Nigerian general-hospital list (A&E, GOPD, Internal Medicine,
   Surgery, O&G, Paediatrics, ICU, Laboratory, Radiology, Pharmacy, Nursing Services, Records, Administration) with
   their wards (A&E Resus Bay, Male/Female Medical Ward, Labour Ward, Children's Ward, ICU ...), then edited freely.
   Codes are unique per hospital; departments and wards are deactivated, never deleted.
3. **Staff accounts**: role plus a **position** (House Officer ... Consultant, Medical Director; Staff Nurse ... Matron,
   Midwife; Medical Laboratory Scientist; Pharmacist; Front Desk Officer; Hospital Administrator) and a department.
4. **Finish**: `POST /admin/onboarding/complete` (needs name, address, phone and type). `/auth/me` returns
   `facility_onboarded`.

Roles: `reception`, `nurse`, `doctor`, `lab`, `pharmacy`, `admin`. Every staff member has an on/off-duty switch
(`POST /auth/duty`), which AraPulse uses to decide whom to page.

**Admin Overview**: `GET /admin/analytics?days=14` (7 to 90) returns today's numbers (checked in, waiting, with the
doctor, seen, average waits, critical vitals, lab backlog, staff on duty), a day-by-day series with every day present,
arrivals by hour today against a typical day, triage mix, top diagnoses, patient age and sex, lab volume and
turnaround, staff by role and department, and wards. Days follow the facility's local midnight (`ARACARE_TIMEZONE`);
average wait is call time minus time joined the queue, as on the Queues page. Viewing it is audited.

## AraPulse: internal communications

AraPulse connects every department so it no longer depends on paper slips and phone calls (design: `docs/arapulse.md`, built from
`docs/internal_communications.md`).
- **Channels**: *All staff* plus one channel per department (`#emergency`, `#laboratory`, `#pharmacy` ...). Anyone can
  read and post in any department's channel, so departments talk to each other directly; there are also direct
  messages. A message can carry a patient tag and a priority; critical messages must be acknowledged, and seen is
  not the same as acknowledged.
- **Pulse Codes** (emergency pages): Code Blue, Obstetric Emergency, Trauma Call, Rapid Response, Urgent Review.
  A page names the **ward and bed** and carries the patient's snapshot (latest vitals with flags, allergies, age/sex,
  blood group, diagnoses). It goes to the named doctor, else on-duty doctors in the department, else all on-duty
  doctors. The doctor acknowledges with an ETA, then arrives and resolves. A page still ringing after
  `ARACARE_PAGE_ESCALATE_SECONDS` (120) widens to every on-duty doctor, then to every doctor.
- **Alerts**: the ordering doctor gets the **lab result as soon as the lab reports it**. A critical result must be
  acknowledged; if not acknowledged within `ARACARE_CRITICAL_RESULT_ESCALATE_MINUTES` (10), it is posted in the doctor's
  department channel. Critical vitals at triage alert the on-duty doctors; dispensed prescriptions notify the prescriber.
- **Lab and pharmacy**: `/lab/worklist` (start, enter result with normal/abnormal/critical flag) and
  `/pharmacy/worklist` (dispense). Orders reach them when the doctor signs the note (`LabOrdered`, `Prescribed`),
  and their work feeds AraPulse through `LabResulted` and `Dispensed` events.
- Live updates go over `/api/ws/pulse?token=<JWT>`. The socket carries **no patient data** (only "refetch" or "a
  page targets you"); clients load the details over REST, which is audited.

## Architecture in one paragraph

A modular monolith (FastAPI + SQLAlchemy). Each module owns its tables and talks to others only through
**domain events** written to a transactional outbox (`outbox_events`) and dispatched in-process:
`VisitCheckedIn`, `TriageCompleted`, `NoteSigned`, `LabOrdered`, `Prescribed`, `JourneyClinicalCompleted`, ...
Billing, pharmacy and cloud sync will subscribe to those same events. See `docs/architecture.md`.

```
backend/app/modules/
  core/          staff, roles, audit log, consent, outbox, outbound messages, hospital profile
  org/           departments, wards, staff directory, onboarding and the suggested set-up catalogue
  insights/      admin Overview analytics
  registration/  patients (ARC-LAG-2026-000001), duplicate detection, fuzzy search, check-in -> visit
  queues/        ticket state machine, weighted fair queuing + aging, journey cascade, TV display, WebSocket
  ehr/           vitals + flags, SOAP note (immutable once signed), ICD-10, allergy hard-block, orders
  scribe/        local Whisper + Ollama, grounding, consent gate
  lab/           lab worklist + results, pharmacy worklist + dispensing
  pulse/         AraPulse: channels, messages, alerts, Pulse Codes, escalation sweeper, /ws/pulse
```

## API surface (all under `/api`)

`/auth/login`, `/auth/me`, `/auth/change-password`, `/auth/duty` · `/patients`, `/patients/search`, `/patients/{id}/check-in` · `/queues/{dept}`,
`/queues/{dept}/call-next`, `/tickets/{id}/{arrived|no-show|rejoin|cancel}`, `/display/{dept}` (public TV),
`/ws/queue` · `/ehr/visits/{id}/triage`, `/ehr/visits/{id}/note`, `/ehr/notes/{id}/sign`, `/ehr/...` ·
`/scribe/consent`, `/scribe/transcribe`, `/scribe/draft` · `/admin/audit|events|messages` ·
`/admin/staff` (list, create, update, `/{id}/reset-password`) · `/facility` (public), `/admin/facility` ·
`/org/departments`, `/org/wards`, `/org/directory` · `/admin/departments`, `/admin/wards` (create, update) ·
`/admin/onboarding`, `/admin/onboarding/departments`, `/admin/onboarding/complete` · `/admin/analytics` ·
`/lab/worklist`, `/lab/orders/{id}/{start|result}`, `/pharmacy/worklist`, `/pharmacy/orders/{id}/dispense` ·
`/pulse/summary|channels|alerts|pages|codes|patients|stats`, `/ws/pulse` · `/health`.

## Not built yet (by design)

Billing and cashier, inventory (stock levels), lab analyser integration, ANC/paediatrics, document OCR, FHIR API, cloud sync,
real SMS gateway (messages are queued in `outbound_messages`), Redis (live queue state is in PostgreSQL/SQLite and
WebSockets are in-process; swap in Redis pub/sub when running more than one API process), push/SMS for Pulse Codes
when a doctor has no AraCare screen open.
