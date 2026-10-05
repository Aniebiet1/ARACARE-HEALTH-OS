"""Draws the diagrams and code-snippet images used in the SIWES report.

    python report/build/make_figures.py

Snippets marked AraCare are copied from the real source files (path shown in each image's title bar).
"""
import shutil
import textwrap
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch
from PIL import Image, ImageDraw, ImageFont
from pygments import highlight
from pygments.formatters import ImageFormatter
from pygments.lexers import get_lexer_by_name
from pygments.style import Style
from pygments.token import Comment, Keyword, Name, Number, Operator, String, Text, Token

ROOT = Path(__file__).resolve().parents[1]
FIG, SNIP = ROOT / "figures", ROOT / "snippets"
FIG.mkdir(exist_ok=True); SNIP.mkdir(exist_ok=True)
REPO = ROOT.parent
LOGBOOK_MEDIA = Path("/tmp/claude-0/lb/word/media")

# colours shared with the logbook sketches so every diagram in the report looks like one family
C = {"blue": ("#EAF2FB", "#2A5B8A"), "red": ("#FBEEEA", "#B4522F"), "green": ("#EEF6EC", "#3E7B4F"),
     "gold": ("#FCF3DA", "#9A7A1C"), "purple": ("#F1EAF9", "#5B3D8A"), "grey": ("#F2F4F7", "#667085")}
INK = "#14304F"


# ------------------------------------------------------------------ diagram helpers
def canvas(w, h, title=None):
    fig, ax = plt.subplots(figsize=(w, h))
    ax.set_xlim(0, w * 10); ax.set_ylim(0, h * 10); ax.axis("off")
    if title:
        ax.text(w * 5, h * 10 - 3.5, title, ha="center", va="center", fontsize=15, fontweight="bold", color=INK)
    return fig, ax


def box(ax, x, y, w, h, text, color="blue", fs=10.5, bold=False):
    face, edge = C[color]
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.4,rounding_size=1.2",
                                fc=face, ec=edge, lw=2))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs, color=INK,
            fontweight="bold" if bold else "normal", linespacing=1.35)
    return (x, y, w, h)


def arrow(ax, p, q, color="#2A5B8A", text=None, rad=0.0, fs=8.5, style="-|>"):
    ax.add_patch(FancyArrowPatch(p, q, arrowstyle=style, mutation_scale=16, lw=1.8, color=color,
                                 connectionstyle=f"arc3,rad={rad}", shrinkA=2, shrinkB=2))
    if text:
        mx, my = (p[0] + q[0]) / 2, (p[1] + q[1]) / 2
        ax.text(mx, my, text, fontsize=fs, ha="center", va="center", color=INK,
                bbox=dict(fc="white", ec="none", pad=1.2))


def top(b): return (b[0] + b[2] / 2, b[1] + b[3])
def bot(b): return (b[0] + b[2] / 2, b[1])
def left(b): return (b[0], b[1] + b[3] / 2)
def right(b): return (b[0] + b[2], b[1] + b[3] / 2)


def done(fig, name):
    fig.savefig(FIG / f"{name}.png", dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)


# ------------------------------------------------------------------ diagrams
def ds_workflow():
    fig, ax = canvas(13, 6.2, "The Data Science Workflow")
    steps = [("1. Define the\nproblem", "purple"), ("2. Collect\ndata", "blue"), ("3. Clean &\nprepare", "blue"),
             ("4. Explore\n(EDA)", "green"), ("5. Feature\nengineering", "green"), ("6. Build\nmodels", "gold"),
             ("7. Evaluate", "gold"), ("8. Deploy &\ncommunicate", "red")]
    xs = [3, 34, 65, 96]
    row1 = [box(ax, x, 33, 27, 14, t, c, 11, True) for x, (t, c) in zip(xs, steps[:4])]
    row2 = [box(ax, x, 6, 27, 14, t, c, 11, True) for x, (t, c) in zip(xs[::-1], steps[4:])]
    for a, b in zip(row1, row1[1:]):
        arrow(ax, right(a), left(b))
    arrow(ax, bot(row1[-1]), top(row2[0]))
    for a, b in zip(row2, row2[1:]):
        arrow(ax, left(a), right(b))
    arrow(ax, top(row2[-1]), bot(row1[0]), color="#B4522F", text="monitor, learn, iterate")
    arrow(ax, (row2[2][0] + 13, 20.5), (row1[2][0] + 13, 32.5), color="#9A7A1C", text="poor results:\nback to the data", rad=0)
    notes = ["What decision will\nthe answer support?", "CSV, APIs, databases,\nsurveys, scraping",
             "missing values,\nduplicates, types", "distributions,\ncorrelations, outliers"]
    for b, n in zip(row1, notes):
        ax.text(b[0] + b[2] / 2, 50.5, n, ha="center", va="bottom", fontsize=8.5, color="#475467", style="italic")
    done(fig, "dg_ds_workflow")


def org_chart():
    fig, ax = canvas(12, 5.6, "Acadeva: Organisational Structure (simplified)")
    ceo = box(ax, 44, 38, 32, 9, "Founders / Management", "purple", 11, True)
    units = [("Engineering\n(web, mobile, desktop)", "blue"), ("Machine Learning\n(AI content tools)", "green"),
             ("Design", "gold"), ("Marketing &\nCommunity", "red")]
    ub = [box(ax, 4 + i * 29, 21, 25, 10, t, c, 10) for i, (t, c) in enumerate(units)]
    for b in ub:
        arrow(ax, bot(ceo), top(b))
    sup = box(ax, 4, 2, 54, 11, "SIWES interns\nData Science, Machine Learning and\nWeb Development tracks (supervisor: John Henry)",
              "grey", 9.5)
    arrow(ax, bot(ub[0]), (bot(ub[0])[0], 13.5))
    arrow(ax, bot(ub[1]), (bot(ub[1])[0], 13.5))
    done(fig, "dg_org_chart")


def timeline():
    phases = [("Orientation & environment setup", 1, 1, "#667085"),
              ("Phishing data collection & merging", 2, 2, "#2A5B8A"),
              ("Baseline model, evaluation, candidate models", 3, 4, "#2A5B8A"),
              ("URL augmentation & training report", 5, 6, "#2A5B8A"),
              ("FastAPI serving & README", 7, 7, "#3E7B4F"),
              ("EdTech AI tools (Magic, Ranker, Categorizer, Quithn)", 8, 10, "#9A7A1C"),
              ("Monitoring, tests, retraining pipeline", 11, 13, "#3E7B4F"),
              ("Performance & security hardening", 14, 15, "#3E7B4F"),
              ("Prompt fixes & shared Gemini helper refactor", 16, 17, "#9A7A1C"),
              ("Content analytics view", 18, 18, "#B4522F"),
              ("Bug fixing, documentation, explicit-content work", 19, 21, "#5B3D8A"),
              ("Integration testing, report, demo & handover", 22, 24, "#667085")]
    fig, ax = plt.subplots(figsize=(12, 5.2))
    for i, (name, a, b, col) in enumerate(phases[::-1]):
        ax.barh(i, b - a + 1, left=a - 0.5, color=col, height=0.62)
        ax.text(b + 0.7, i, f"W{a}" + (f"-{b}" if b != a else ""), va="center", fontsize=8.5, color="#344054")
    ax.set_yticks(range(len(phases))); ax.set_yticklabels([p[0] for p in phases[::-1]], fontsize=9.5)
    ax.set_xticks(range(1, 25)); ax.set_xlim(0.3, 26.5); ax.set_xlabel("Week of placement (May to October 2026)")
    ax.set_title("SIWES placement timeline at Acadeva (24 weeks)", fontweight="bold", color=INK)
    ax.grid(axis="x", alpha=0.3); [ax.spines[s].set_visible(False) for s in ("top", "right")]
    fig.tight_layout(); done(fig, "dg_timeline")


def architecture():
    fig, ax = canvas(13, 8.2, "AraCare Health OS: System Architecture (one server per facility)")
    clients = [("Reception\n(web)", "blue"), ("Nurse triage\n(web)", "blue"), ("Doctor\n(web)", "blue"),
               ("Admin\n(web)", "blue"), ("TV display\n(public)", "gold"), ("Phone / tablet\n(mobile web)", "blue")]
    cb = [box(ax, 3 + i * 21, 62, 18, 10, t, c, 9.5) for i, (t, c) in enumerate(clients)]
    ax.text(65, 74.5, "React 18 + Vite single-page app, role-based screens, hospital LAN", ha="center", fontsize=9.5,
            color="#475467", style="italic")
    api = box(ax, 3, 34, 124, 19, "", "green")
    ax.text(65, 50.3, "FastAPI modular monolith  (Python 3.11, SQLAlchemy 2, Pydantic, JWT auth)", ha="center",
            fontsize=10.5, fontweight="bold", color=INK)
    mods = ["core\nstaff, roles, audit,\nconsent, outbox", "registration\npatients, search,\ncheck-in, receipt",
            "queues\nWFQ + aging,\njourney, TV, WS", "ehr\nvitals, SOAP note,\nICD-10, orders", "scribe\nWhisper + Ollama,\ngrounding"]
    for i, m in enumerate(mods):
        box(ax, 7 + i * 24, 36, 21, 10, m, "grey", 8.8)
    for b in cb:
        arrow(ax, bot(b), (b[0] + b[2] / 2, 53.3), text=None)
    ax.text(124, 57.5, "REST /api  +  WebSocket /api/ws/queue", ha="right", fontsize=9, color="#2A5B8A")
    db = box(ax, 3, 8, 38, 15, "PostgreSQL 16 (production)\nSQLite (development)\nAlembic migrations", "blue", 9.5)
    ob = box(ax, 46, 8, 38, 15, "outbox_events\n(transactional event log)\nVisitCheckedIn, TriageCompleted,\nNoteSigned, LabOrdered ...", "gold", 9)
    ai = box(ax, 89, 8, 38, 15, "Local AI (no internet, no cost)\nfaster-whisper (speech to text)\nOllama qwen2.5:7b (drafting)\nrule-based fallback", "red", 9)
    arrow(ax, (22, 33.6), top(db), text="SQL")
    arrow(ax, (65, 33.6), top(ob), text="publish")
    arrow(ax, (108, 33.6), top(ai), text="HTTP (localhost)")
    ax.text(65, 2, "Planned subscribers to the same events: billing, pharmacy/inventory, lab, SMS gateway, cloud sync",
            ha="center", fontsize=9, color="#475467", style="italic")
    done(fig, "dg_architecture")


def journey():
    fig, ax = canvas(13, 5.4, "Patient Journey and the Domain Events That Drive It")
    steps = [("Reception\nregister / check in", "blue"), ("Triage queue\nTRI-xxx", "gold"),
             ("Nurse triage\nvitals + flags", "green"), ("Doctor queue\nOPD-xxx", "gold"),
             ("Consultation\nSOAP + ICD-10\nlabs + drugs", "green"), ("Lab / Pharmacy\n(deferred steps)", "grey")]
    bs = [box(ax, 2 + i * 21.4, 22, 18, 14, t, c, 9.5, True) for i, (t, c) in enumerate(steps)]
    evs = ["VisitCheckedIn", "call / arrived", "TriageCompleted\n(priority set)", "call / arrived", "NoteSigned\nLabOrdered, Prescribed"]
    for a, b, e in zip(bs, bs[1:], evs):
        arrow(ax, right(a), left(b))
        ax.text((a[0] + a[2] + b[0]) / 2, 41, e, ha="center", va="center", fontsize=8, color="#B4522F", fontweight="bold")
    ax.text(65, 12, "Receipt with QR code and ticket number  ->  SMS when called  ->  number shown on the waiting-room TV",
            ha="center", fontsize=9.5, color=INK)
    ax.text(65, 6, "JourneyClinicalCompleted closes the visit; billing and pharmacy will subscribe to the same events later.",
            ha="center", fontsize=9, color="#475467", style="italic")
    done(fig, "dg_journey")


def state_machine():
    fig, ax = canvas(12, 6.4, "Queue Ticket State Machine")
    w = box(ax, 8, 40, 20, 9, "WAITING", "blue", 11, True)
    c = box(ax, 50, 40, 20, 9, "CALLED", "gold", 11, True)
    s = box(ax, 92, 40, 20, 9, "IN_SERVICE", "green", 11, True)
    d = box(ax, 92, 12, 20, 9, "COMPLETED", "purple", 11, True)
    n = box(ax, 50, 12, 20, 9, "NO_SHOW", "red", 11, True)
    x = box(ax, 8, 12, 20, 9, "CANCELLED", "grey", 11, True)
    arrow(ax, right(w), left(c), text="call next\n(WFQ pick)")
    arrow(ax, right(c), left(s), text="arrived")
    arrow(ax, bot(s), top(d), text="done")
    arrow(ax, bot(c), top(n), text="timer expires")
    arrow(ax, left(n), (24, 39.6), text="rejoin", rad=-0.2)
    arrow(ax, bot(w), top(x), text="cancel /\nend of day")
    arrow(ax, (60, 49.5), (18, 49.5), text="recall (back of tier)", rad=0.35, color="#9A7A1C")
    done(fig, "dg_state_machine")


def data_model():
    fig, ax = canvas(13, 5.6, "The Data Spine: Everything Hangs Off the Visit")
    spine = ["Patient\n(+ allergies)", "Visit\ntype, payment", "Journey", "JourneyStep\nTRIAGE, OPD ...",
             "QueueTicket\nTRI-031, priority"]
    bs = [box(ax, 2 + i * 26, 34, 20, 12, t, "blue", 9.5, True) for i, t in enumerate(spine)]
    for a, b in zip(bs, bs[1:]):
        arrow(ax, right(a), left(b))
        ax.text((a[0] + a[2] + b[0]) / 2, 42.5, "1 : n", ha="center", fontsize=8.5, color="#2A5B8A")
    clinical = ["Vitals\n+ flags", "ClinicalNote\n(SHA-256, immutable)", "Diagnosis\nICD-10", "LabOrder", "MedicationOrder"]
    cs = [box(ax, 2 + i * 26, 6, 20, 11, t, "green", 9.5) for i, t in enumerate(clinical)]
    for b in cs:
        arrow(ax, top(b), (bs[1][0] + 10, 33.6), color="#3E7B4F")
    done(fig, "dg_data_model")


def scribe_pipeline():
    fig, ax = canvas(13, 4.8, "AI Voice Scribe: From Speech to a Signed Note")
    st = [("Consent\nrecorded", "purple"), ("Audio\n(deleted after use)", "grey"), ("faster-whisper\nspeech to text", "blue"),
          ("Ollama LLM\nor rule-based\nextractor", "blue"), ("Grounding\ndrop numbers not\nin transcript", "red"),
          ("Draft shown\nto clinician", "gold"), ("Clinician edits,\nsaves, signs", "green")]
    bs = [box(ax, 1.5 + i * 18.4, 18, 15.5, 15, t, c, 9) for i, (t, c) in enumerate(st)]
    for a, b in zip(bs, bs[1:]):
        arrow(ax, right(a), left(b))
    ax.text(65, 8, "Nothing reaches the medical record until a clinician signs. Every use is written to the audit log.",
            ha="center", fontsize=9.5, color=INK, style="italic")
    done(fig, "dg_scribe")


# ------------------------------------------------------------------ code snippets
class PaperStyle(Style):
    background_color = "#FAFBFC"
    styles = {Token: "#1F2328", Comment: "italic #6A737D", Keyword: "bold #CF222E", Keyword.Constant: "#0550AE",
              Name.Function: "#8250DF", Name.Class: "bold #953800", Name.Decorator: "#8250DF",
              Name.Builtin: "#0550AE", String: "#0A3069", String.Doc: "italic #57606A", Number: "#0550AE",
              Operator: "#CF222E", Name.Tag: "#116329", Name.Attribute: "#0550AE"}


MONO = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
SANS_B = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def snippet(name, title, code, lang="python"):
    code = textwrap.dedent(code).strip("\n")
    img_bytes = highlight(code, get_lexer_by_name(lang), ImageFormatter(
        style=PaperStyle, font_name="DejaVu Sans Mono", font_size=26, line_numbers=True,
        line_number_bg="#EEF1F4", line_number_fg="#8C959F", line_pad=4, image_pad=18))
    tmp = SNIP / f"_{name}.png"; tmp.write_bytes(img_bytes)
    body = Image.open(tmp).convert("RGB"); tmp.unlink()
    W = max(body.width, 1100); bar = 60
    out = Image.new("RGB", (W + 4, body.height + bar + 4), "#D0D7DE")
    head = Image.new("RGB", (W, bar), "#24292F"); d = ImageDraw.Draw(head)
    for i, col in enumerate(["#FF5F57", "#FEBC2E", "#28C840"]):
        d.ellipse((18 + i * 30, 21, 38 + i * 30, 41), fill=col)
    d.text((125, 15), title, font=ImageFont.truetype(SANS_B, 26), fill="#E6EDF3")
    canvas_ = Image.new("RGB", (W, body.height), "#FAFBFC"); canvas_.paste(body, (0, 0))
    out.paste(head, (2, 2)); out.paste(canvas_, (2, bar + 2))
    out.save(SNIP / f"{name}.png", optimize=True)


def src(path, start, end):
    lines = (REPO / path).read_text().splitlines()
    return "\n".join(lines[start - 1:end])


def find(path, first, n):
    lines = (REPO / path).read_text().splitlines()
    i = next(k for k, l in enumerate(lines) if first in l)
    return "\n".join(lines[i:i + n])


def snippets():
    # ---------------- SIWES work at Acadeva (phishing detector + edtech tools)
    snippet("it_merge", "phishing-detector/train.py  -  load and merge the datasets", '''
        def load_datasets(email_csv: str, url_csv: str) -> pd.DataFrame:
            """Merge both sources into one table: text | label (0 = legitimate, 1 = phishing) | source."""
            emails = pd.read_csv(email_csv)[["text_combined", "label"]]
            emails = emails.rename(columns={"text_combined": "text"}).assign(source="email")

            urls = pd.read_csv(url_csv)[["URL", "label"]]
            urls = urls.rename(columns={"URL": "text"}).assign(source="url")
            # PhiUSIIL uses 1 = legitimate; flip it so 1 always means phishing
            urls["label"] = 1 - urls["label"].astype(int)

            data = pd.concat([emails, urls], ignore_index=True)
            data["text"] = data["text"].astype(str).str.strip()
            data = data[data["text"].str.len() > 0].drop_duplicates(subset=["text"])
            return data.reset_index(drop=True)
    ''')
    snippet("it_candidates", "phishing-detector/train.py  -  candidate models", '''
        def get_model_candidates(max_features: int = 200_000) -> dict[str, Pipeline]:
            """Every candidate shares the same TF-IDF front end, so results are directly comparable."""
            def tfidf():
                return TfidfVectorizer(ngram_range=(1, 2), max_features=max_features,
                                       min_df=2, sublinear_tf=True)
            return {
                "logistic_regression": Pipeline([("tfidf", tfidf()), ("clf", LogisticRegression(max_iter=2000))]),
                "linear_svc": Pipeline([("tfidf", tfidf()), ("clf", LinearSVC())]),
                "calibrated_svc": Pipeline([("tfidf", tfidf()),
                                            ("clf", CalibratedClassifierCV(LinearSVC(), cv=3))]),
                "multinomial_nb": Pipeline([("tfidf", tfidf()), ("clf", MultinomialNB(alpha=0.1))]),
                "sgd": Pipeline([("tfidf", tfidf()), ("clf", SGDClassifier(loss="modified_huber"))]),
                "passive_aggressive": Pipeline([("tfidf", tfidf()), ("clf", PassiveAggressiveClassifier())]),
            }


        X_train, X_test, y_train, y_test = train_test_split(
            data["text"], data["label"], test_size=0.2, stratify=data["label"], random_state=42)
    ''')
    snippet("it_augment", "phishing-detector/train.py  -  typosquatting hard examples", '''
        LOOKALIKES = {"a": "4", "o": "0", "l": "1", "e": "3", "i": "1", "m": "rn", "w": "vv"}
        BRANDS = ["paypal", "google", "microsoft", "apple", "amazon", "facebook", "firstbank", "gtbank"]
        URGENT = ["verify", "secure", "update", "login", "account", "suspended", "confirm"]

        def typosquat_variants(brand: str) -> list[str]:
            """paypal -> p4ypal, payp4l, paypa1 ... one substitution at a time."""
            out = []
            for i, ch in enumerate(brand):
                if ch in LOOKALIKES:
                    out.append(brand[:i] + LOOKALIKES[ch] + brand[i + 1:])
            return out

        def make_hard_examples(seed: int = 42) -> pd.DataFrame:
            rng = random.Random(seed)
            rows = []
            for brand in BRANDS:
                for fake in typosquat_variants(brand):
                    rows.append(f"https://{fake}.com/{rng.choice(URGENT)}")
                rows.append(f"http://{brand}.{rng.choice(URGENT)}-{rng.randint(100, 999)}.xyz/login")  # brand in subdomain
            return pd.DataFrame({"text": rows, "label": 1, "source": "augmented"})
    ''')
    snippet("it_api", "phishing-detector/main.py  -  FastAPI /predict endpoint", '''
        app = FastAPI(title="Acadeva Phishing Detector")
        model = load_model("saved_models/phishing_model.joblib")   # loaded ONCE at startup, not per request

        class PredictRequest(BaseModel):
            text: str = Field(..., min_length=1, max_length=20_000)
            source: Literal["email", "url"] = "email"

        class PredictResponse(BaseModel):
            label: Literal["phishing", "legitimate"]
            score: float
            details: dict

        @app.get("/health")
        def health():
            return {"status": "ok", "model": model.name}

        @app.post("/predict", response_model=PredictResponse)
        @limiter.limit("60/minute")
        def predict(req: PredictRequest, request: Request):
            score = float(model.predict_proba([req.text])[0][1])
            log.info("predict source=%s score=%.3f", req.source, score)       # reviewed later for errors
            return PredictResponse(label="phishing" if score >= 0.5 else "legitimate",
                                   score=round(score, 4), details={"source": req.source})
    ''')
    snippet("it_tests", "phishing-detector/tests/test_predict.py  -  pytest", '''
        client = TestClient(app)

        def test_flags_obvious_phishing_url():
            r = client.post("/predict", json={"text": "http://p4ypal.com/verify-account", "source": "url"})
            assert r.status_code == 200
            assert r.json()["label"] == "phishing"

        def test_accepts_legitimate_url():
            r = client.post("/predict", json={"text": "https://www.paypal.com", "source": "url"})
            assert r.json()["label"] == "legitimate"

        @pytest.mark.parametrize("text", ["", "x" * 20_001])
        def test_rejects_empty_and_oversized_input(text):
            assert client.post("/predict", json={"text": text}).status_code == 422

        def test_handles_non_ascii():
            r = client.post("/predict", json={"text": "Ọ̀gá, your account dey locked. Click here"})
            assert 0.0 <= r.json()["score"] <= 1.0
    ''')
    snippet("it_promote", "phishing-detector/promote_model.py  -  champion / challenger", '''
        def promote(challenger_path: Path, metric: str = "phishing_f1") -> bool:
            """Replace the production model only if the newly trained challenger is better."""
            champion = json.loads(Path("saved_models/production_report.json").read_text())
            challenger = json.loads(challenger_path.with_suffix(".json").read_text())
            old, new = champion["metrics"][metric], challenger["metrics"][metric]
            if new <= old:
                print(f"kept production model: {metric} {new:.4f} <= {old:.4f}")
                return False
            shutil.copy(challenger_path, "saved_models/phishing_model.joblib")
            shutil.copy(challenger_path.with_suffix(".json"), "saved_models/production_report.json")
            print(f"promoted {challenger_path.name}: {metric} {old:.4f} -> {new:.4f}")
            return True
    ''')
    snippet("it_gemini", "acadeva-ai/lib/gemini.js  -  shared helper for the four AI tools", '''
        // One place for model setup, JSON output and error handling. Magic, the Topic Ranker,
        // the Categorizer and Quithn only supply their own system prompt and output schema.
        import { GoogleGenerativeAI } from "@google/generative-ai";

        const genAI = new GoogleGenerativeAI(process.env.GEMINI_API_KEY);

        export async function runTool({ systemPrompt, input, schema, model = "gemini-2.0-flash" }) {
          const m = genAI.getGenerativeModel({
            model,
            systemInstruction: systemPrompt,
            generationConfig: { responseMimeType: "application/json", responseSchema: schema, temperature: 0.2 },
          });
          try {
            const res = await m.generateContent(input);
            return { ok: true, data: JSON.parse(res.response.text()) };
          } catch (err) {
            console.error(`[${model}] tool call failed:`, err.message);
            return { ok: false, error: "The AI service is busy. Please try again." };
          }
        }
    ''', "javascript")
    snippet("it_analytics", "acadeva-ai/analytics/category_distribution.py", '''
        outputs = pd.read_json("magic_outputs.jsonl", lines=True)
        outputs["category"] = outputs["category"].str.strip().str.title()

        dist = (outputs.groupby(["category", "subject"]).size()
                       .reset_index(name="books").sort_values("books", ascending=False))

        top = dist.groupby("category")["books"].sum().nlargest(12)
        ax = top.sort_values().plot(kind="barh", color="#2A5B8A", figsize=(9, 5))
        ax.set(title="Books per category (Acadeva Magic output)", xlabel="Books")
        plt.tight_layout(); plt.savefig("category_distribution.png", dpi=200)
    ''')

    # ---------------- AraCare (real source)
    snippet("ac_priority", "backend/app/modules/queues/service.py  -  initial priority",
            find("backend/app/modules/queues/service.py", "def initial_priority", 10))
    snippet("ac_wfq", "backend/app/modules/queues/service.py  -  aging + weighted fair queuing",
            find("backend/app/modules/queues/service.py", "def effective_tier", 40))
    snippet("ac_flags", "backend/app/modules/ehr/clinical_rules.py  -  vital-sign flags",
            find("backend/app/modules/ehr/clinical_rules.py", "def flag_vitals", 33))
    snippet("ac_allergy", "backend/app/modules/ehr/clinical_rules.py  -  allergy hard block",
            find("backend/app/modules/ehr/clinical_rules.py", "def drug_class_of", 20))
    snippet("ac_ground", "backend/app/modules/scribe/structure.py  -  grounding the AI draft",
            find("backend/app/modules/scribe/structure.py", "_NUM = re.compile", 16))
    snippet("ac_events", "backend/app/events.py  -  event bus with transactional outbox",
            find("backend/app/events.py", "def subscribe", 34))
    snippet("ac_search", "backend/app/modules/registration/service.py  -  fuzzy name search",
            find("backend/app/modules/registration/service.py", "def normalise_phone", 18))
    snippet("ac_config", "backend/app/config.py  -  refuse unsafe production settings",
            find("backend/app/config.py", "def check(self)", 15))
    tv = Path("/home/user/aniebiet1/aracare-health-os-frontend/src/pages/TV.jsx").read_text().splitlines()
    clean, skip = [], False
    for l in tv:                    # the repo file has an unresolved merge; keep the HEAD side
        if l.startswith("<<<<<<<"): continue
        if l.startswith("======="): skip = True; continue
        if l.startswith(">>>>>>>"): skip = False; continue
        if not skip: clean.append(l)
    i = next(k for k, l in enumerate(clean) if l.startswith("export default"))
    snippet("ac_tv", "frontend/src/pages/TV.jsx  -  waiting-room TV display", "\n".join(clean[i:i + 12]), "jsx")
    lines = Path("/tmp/claude-0/pytest_v.txt").read_text().splitlines()
    tests = [l.replace("tests/", "") for l in lines if "PASSED" in l or "FAILED" in l]
    shown = tests[:12] + [f"... {len(tests) - 24} more tests ..."] + tests[-12:]
    snippet("ac_pytest", "terminal  -  cd backend && pytest -v",
            "$ pytest -v\n" + "\n".join(shown) + "\n" + lines[-1].strip("= "), "text")


if __name__ == "__main__":
    for f in (ds_workflow, org_chart, timeline, architecture, journey, state_machine, data_model, scribe_pipeline):
        f()
    for src_name, dst in [("df8bb383d4456b9e350ca829fafec0c014c94d3f.png", "lb_phishing_pipeline.png"),
                          ("7ee587f132197baa2730dbe96faed1a75d33981a.png", "lb_edtech_pipeline.png")]:
        if (LOGBOOK_MEDIA / src_name).exists():
            shutil.copy(LOGBOOK_MEDIA / src_name, FIG / dst)
    snippets()
    print(sorted(p.name for p in FIG.glob("dg_*")), sorted(p.name for p in SNIP.glob("*.png")))
