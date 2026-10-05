"""Text of the SIWES report. Blocks: ("p", text) ("h2", "2.1 Title") ("h3", text) ("ul", [..]) ("ol", [..])
("fig", path-relative-to-repo, caption, {opts}) ("table", headers, rows, caption, widths) ("break",)
Inline: **bold**, `code`."""

F = "report/figures/"
S = "report/snippets/"
P = "pictures/"

# ================================================================== PRELIMINARY PAGES
PRELIMS = [
    ("Dedication", "dedication", [
        "This work is dedicated to Almighty God, the source of all wisdom, knowledge and understanding, "
        "who kept me throughout the period of my industrial training;",
        "and to my beloved parents, for their love, prayers and sacrifices, which made my education possible.",
    ]),
    ("Acknowledgement", "acknowledgement", [
        "I give all glory to Almighty God for the gift of life, good health and the grace to complete my Student "
        "Industrial Work Experience Scheme (SIWES) and this report.",
        "I sincerely thank the management and staff of **Acadeva Limited** for accepting me as an intern and for "
        "creating an environment where I could learn by doing real work. I am especially grateful to my industry-based "
        "supervisor, **Mr. John Henry**, whose guidance, patience and honest feedback shaped every project I worked on, "
        "from the phishing detection model to the AI content tools. I also thank the engineering, machine learning and "
        "design teams, and the PY50 trainees, for the knowledge they shared with me and the questions that made me "
        "understand my own work better.",
        "My gratitude goes to the Head of Department and all the lecturers of the **Department of Computer Science, "
        "Faculty of Computing, University of Uyo**, for the academic foundation that made this training meaningful, and "
        "to the departmental SIWES coordinator and my institution-based supervisor for their supervision and support. "
        "I also acknowledge the **Industrial Training Fund (ITF)** for sustaining the SIWES programme.",
        "Finally, I am deeply thankful to my parents, siblings, friends and coursemates for their encouragement, prayers "
        "and support throughout this period. May God bless you all.",
    ]),
    ("Abstract", "abstract", [
        "This report documents the six-month Student Industrial Work Experience Scheme (SIWES) undertaken at Acadeva "
        "Limited, an education technology company in Akwa Ibom State, Nigeria, between May and October 2026, and the "
        "IT project developed from the skills acquired. During the placement I worked as an AI/ML intern in the Data "
        "Science, Machine Learning and Web Development tracks. I built a phishing detection system that merges an email "
        "dataset and a URL dataset, extracts TF-IDF features, trains and ranks six candidate classifiers, strengthens the "
        "model with generated typosquatting examples, and serves predictions through a tested, rate-limited FastAPI "
        "service with a safe champion/challenger retraining flow. I also contributed to four generative-AI content tools "
        "(Acadeva Magic, the Book Topic Ranker, the Content Categorizer and the Quithn quiz generator) through prompt "
        "engineering, bug fixing and a shared helper refactor, and built a content analytics view. The data science "
        "workflow learned is demonstrated with three beginner projects: Titanic survival prediction (82.2% "
        "cross-validated accuracy), California house price prediction (R² = 0.81) and Iris flower classification "
        "(97.8% accuracy).",
        "The IT project, **AraCare Health OS**, applies these skills to a real problem in Nigerian hospitals: long, "
        "disorderly outpatient queues and paper records. AraCare is an offline-first hospital operating system built "
        "with FastAPI, SQLAlchemy and React. Its first release covers patient registration with QR-coded receipts, a "
        "queue engine that uses weighted fair queuing with aging so urgent patients are seen first without anyone being "
        "starved, a waiting-room TV display, an electronic health record with vital-sign flags, ICD-10 diagnoses and a "
        "server-side allergy hard-block, and an AI voice scribe that runs fully on the hospital's own computer using "
        "Whisper and a local language model, with grounding rules that remove any value the clinician did not say. All "
        "47 automated tests pass. An analysis of six weeks of system records shows that the priority rules work as "
        "designed: in the doctor queue, median waits were about 2 minutes for emergencies, 24 minutes for high-priority "
        "patients and 57 minutes for normal patients, while arrivals peak between 08:00 and 11:00.",
        "Keywords: SIWES, data science workflow, machine learning, phishing detection, hospital information system, "
        "queue management, electronic health records, speech recognition, FastAPI, React.",
    ]),
]

# ================================================================== CHAPTER 1
CH1 = [
    ("h2", "INTRODUCTION"),
    ("p", "This chapter gives an overview of the Student Industrial Work Experience Scheme (SIWES) and introduces the "
          "organisation where I completed my industrial training, **Acadeva Limited**. It explains the purpose of SIWES, "
          "describes the background and profile of Acadeva, including its history, vision, mission and core values, and "
          "outlines the duration and scope of my internship. Together these sections provide the context for the "
          "practical skills presented in Chapter Two and the IT project presented in Chapter Three."),
    ("h2", "1.1 Background of the SIWES Programme"),
    ("p", "The Students Industrial Work Experience Scheme (SIWES) is a skills training programme designed to bridge the "
          "gap between the theory learned in the classroom and the practice of industry. It was established by the "
          "Industrial Training Fund (ITF) in 1973, following the observation that many graduates of Nigerian tertiary "
          "institutions lacked the practical skills that employers needed. Today it is a compulsory part of degree "
          "programmes in engineering, technology, science and related disciplines, and is jointly managed by the ITF, "
          "the National Universities Commission (NUC), the participating institutions and the employers who host the "
          "students."),
    ("p", "The scheme places students in real work environments where they apply what they have learned to real "
          "problems, under the guidance of experienced professionals. For students of Computer Science, this means "
          "working with the tools, codebases, data and development practices that are used in industry today: version "
          "control, code review, automated testing, cloud and API services, data pipelines and machine learning "
          "systems. It also exposes students to the non-technical side of professional life: deadlines, teamwork, "
          "communication with non-technical colleagues, documentation and accountability."),
    ("p", "The specific objectives of SIWES, as stated by the Industrial Training Fund, are to:"),
    ("ul", ["provide an avenue for students in higher institutions to acquire industrial skills and experience in their "
            "course of study;",
            "prepare students for the work situation they are likely to meet after graduation;",
            "expose students to work methods and techniques in handling equipment and machinery that may not be "
            "available in their institutions;",
            "make the transition from school to the world of work easier, and enhance students' contacts for later "
            "job placement;",
            "provide students with an opportunity to apply their theoretical knowledge to real work situations, "
            "thereby bridging the gap between theory and practice; and",
            "enlist and strengthen employers' involvement in the entire educational process of preparing graduates "
            "for employment in industry."]),
    ("p", "The programme typically lasts six months for university students. At the end, the student submits a logbook "
          "signed by the industry-based supervisor and a technical report, and is assessed by the institution. This "
          "report is part of that requirement."),
    ("h2", "1.2 About Acadeva"),
    ("p", "**Acadeva Limited** is a Nigerian education technology company that collects and organises study materials, "
          "past questions and PDFs from Nigerian universities by school, department and course. Students use Acadeva "
          "to find what they need to study, download it for offline use, share materials with classmates, and keep a "
          "shared academic schedule with reminders. Study tools such as quizzes and summaries are built on top of the "
          "materials to help students learn from them, and these tools are powered by machine learning and large "
          "language models."),
    ("p", "Acadeva is available on Android, iOS, iPadOS, macOS, Windows and Linux, and is registered with the Corporate "
          "Affairs Commission (CAC). It operates in Akwa Ibom State. The company has a small core team working across "
          "engineering, machine learning and design, supported by a wider team of about nine people in development, "
          "design and marketing. Students on placement are attached to the Data Science, Machine Learning and Web "
          "Development tracks, where they work under the supervision of **Mr. John Henry**. Figure 1.1 shows a "
          "simplified view of how the company is organised and where SIWES interns fit."),
    ("fig", F + "dg_org_chart.png", "Simplified organisational structure of Acadeva and the position of SIWES interns.", {"width": 5.4}),
    ("table", ["Item", "Details"],
     [["Company", "Acadeva Limited (registered with the Corporate Affairs Commission)"],
      ["Sector", "Education technology (EdTech)"],
      ["Location", "Akwa Ibom State, Nigeria"],
      ["Products", "Study-material library, offline downloads, sharing, academic schedule with reminders, AI study tools "
                   "(quizzes, summaries, metadata generation)"],
      ["Platforms", "Android, iOS, iPadOS, macOS, Windows, Linux"],
      ["Team", "Small core team (engineering, machine learning, design) plus about nine people in development, design "
               "and marketing"],
      ["Intern tracks", "Data Science, Machine Learning, Web Development"]],
     "Acadeva at a glance.", [1.6, 4.9]),
    ("h2", "1.3 History, Vision, Mission and Core Values"),
    ("h3", "Organisational History"),
    ("p", "Acadeva began as a prototype that won first and second place at a campus technology competition in November "
          "2024. The Android app launched on 20 June 2025, and more than 2,000 students signed up within the first six "
          "months. In July 2025 Acadeva was First Runner-Up at the DevEast Entrepreneurship Week at the Federal "
          "University of Technology, Owerri (FUTO), and received startup funding."),
    ("p", "Since launch, Acadeva has grown through partnerships with student and academic communities. Its library has "
          "grown past 1,000 shared books, and it has hosted more than 20 large quiz events. It has since added iOS and "
          "iPadOS apps and desktop apps for Windows, macOS and Linux, and introduced paid subscriptions. Throughout this "
          "growth the company has relied on automation, including machine learning, to keep a small team productive: "
          "for example, uploaded books are tagged and described by AI tools instead of by hand."),
    ("h3", "Vision Statement"),
    ("p", "To make quality academic resources accessible to every student and create a more connected way for students "
          "to learn together."),
    ("h3", "Mission Statement"),
    ("p", "To make study resources accessible and learning more effective by building collaborative and innovative tools "
          "designed around students' real academic needs."),
    ("h3", "Core Values"),
    ("ul", ["Accessibility: study materials should be available to every student, including offline and on low-cost devices.",
            "Collaboration: students learn better together, so sharing and group features are central to the product.",
            "Innovation: new technology, including AI, is used where it genuinely helps students learn.",
            "Student-Centricity: features are built around students' real academic needs, not around technology for its own sake.",
            "Integrity: honesty in how materials are sourced and shared, and in how student data is handled."]),
    ("h2", "1.4 Duration and Scope of Internship"),
    ("p", "My SIWES placement at Acadeva ran for six months (24 weeks), from May to October 2026, in the role of "
          "**AI/ML Intern**. The placement was structured to give practical exposure to how a student-focused software "
          "product is built, maintained and improved. I participated in activities in the Data Science, Machine Learning "
          "and Web Development tracks under the supervision of Mr. John Henry."),
    ("table", ["Item", "Details"],
     [["Student", "Joseph Cosmos Aniebiet (22/SC/CO/1301)"],
      ["Organisation", "Acadeva Limited, Akwa Ibom State"],
      ["Role", "AI/ML Intern (Data Science, Machine Learning and Web Development tracks)"],
      ["Period", "11 May 2026 to 23 October 2026 (24 weeks)"],
      ["Industry-based supervisor", "Mr. John Henry"],
      ["Main projects", "Phishing detection model and API; Acadeva Magic, Book Topic Ranker, Content Categorizer and "
                        "Quithn (generative-AI content tools); content analytics view"]],
     "Summary of the SIWES placement.", [1.9, 4.6]),
    ("p", "Work was organised in phases, as recorded week by week in my logbook and summarised in Figure 1.2. The first "
          "half of the placement focused on building and serving a phishing detection model from scratch. The middle "
          "phase moved to the generative-AI content tools that power Acadeva's study features. The final phase was "
          "about making both systems production-ready: monitoring, automated tests, performance, security, "
          "documentation, integration testing and handover."),
    ("fig", F + "dg_timeline.png", "Timeline of activities across the 24-week placement (from the SIWES logbook)."),
    ("p", "Within this period I developed practical skills in the following areas:"),
    ("ul", ["Data collection and management: sourcing, merging and labelling datasets; tagging study materials by school, department and course.",
            "Data cleaning and analysis: label normalisation, de-duplication, PDF text extraction and review of logged predictions.",
            "Data visualisation and exploratory analysis: class balance, per-source metrics and content analytics with pandas and Matplotlib.",
            "Programming and software development: Python, FastAPI, Pydantic, pytest, JavaScript/Node.js, Git and documentation.",
            "Machine learning: TF-IDF features, linear classifiers, model calibration, evaluation metrics, data augmentation and safe retraining.",
            "Generative AI: prompt engineering, few-shot examples and structured JSON output with the Gemini API.",
            "Professional skills: teamwork, code review, knowledge sharing with PY50 trainees, presentations and handover."]),
    ("h2", "1.5 Conclusion"),
    ("p", "This chapter has established the context of my SIWES placement at Acadeva Limited, a young but fast-growing "
          "Nigerian EdTech company whose product depends on data and machine learning. It introduced the purpose of "
          "SIWES, the organisation's history, vision, mission and values, and the scope of my internship. The next "
          "chapter presents the practical skills and competencies I acquired, including the data science workflow and "
          "three beginner data science projects."),
]

# ================================================================== CHAPTER 2
CH2 = [
    ("h2", "INTRODUCTION"),
    ("p", "The purpose of this chapter is to give a structured account of the practical skills I acquired during the "
          "placement. Following the department's template, each section describes the concept and why it matters, the "
          "practical activities I performed, the tools I used, and what I learned. Most of the examples come from the two "
          "streams of work recorded in my logbook: the **phishing detection system** (weeks 1 to 7 and 11 to 15) and the "
          "**Acadeva generative-AI content tools** (weeks 8 to 10 and 16 to 21). The chapter then presents the data "
          "science workflow that ties these activities together, and three beginner data science projects that "
          "demonstrate the workflow end to end."),

    ("h2", "2.1 Data Collection and Management"),
    ("p", "Every data science or machine learning project starts with data, and the quality of the final model can never "
          "be better than the quality of the data it learned from. Data collection means finding, obtaining and recording "
          "the data needed to answer a question; data management means storing it in a consistent structure, with clear "
          "labels and documented sources, so that anyone on the team can use it and reproduce the results."),
    ("p", "When Acadeva asked for an in-house model to flag phishing emails and URLs, my first task was to research public "
          "datasets. I shortlisted and used two: `phishing_email.csv`, which contains the combined text of emails with a "
          "label, and the **PhiUSIIL Phishing URL Dataset**, which contains URLs with a label. The two datasets used "
          "different column names and, importantly, different label conventions, so I wrote a loader that renames the "
          "columns, normalises the labels so that 1 always means phishing and 0 always means legitimate, adds a `source` "
          "column (email or URL), and merges both into one table (Figure 2.1). Keeping the source column turned out to be "
          "valuable later, because it allowed metrics to be broken down per source."),
    ("fig", S + "it_merge.png", "Loading, normalising and merging the email and URL datasets into one table."),
    ("p", "On the EdTech side, data management meant organising academic materials. Past questions and books are tagged by "
          "school, department and course so that students can find them, and the AI tools described in Section 2.6 "
          "generate much of this metadata automatically. I worked on the subject and category taxonomy used to classify "
          "uploaded books, which is the backbone of how the library is organised."),
    ("ul", ["Practical activity: researched, downloaded and merged phishing email and URL datasets; organised the project as data/, saved_models/ and utils/ folders; refined the book subject/category taxonomy.",
            "Tools/technologies used: Python, pandas, CSV files, Git.",
            "Skills acquired: dataset selection, schema alignment, label normalisation, project and data organisation."]),

    ("h2", "2.2 Data Cleaning and Analysis"),
    ("p", "Raw data is almost never ready for analysis. It contains missing values, duplicates, inconsistent formats and "
          "errors. Data cleaning is the process of detecting and fixing these problems, and it usually takes more time "
          "than modelling. The principle of \"garbage in, garbage out\" was very clear in my work: a phishing model "
          "trained on duplicated or mislabelled rows reports accuracy it cannot deliver in production."),
    ("p", "For the phishing project I removed empty texts and exact duplicates after merging, stripped whitespace, cast "
          "labels to integers, and checked the class balance of each source. After the model went live, I added request "
          "logging to the API and wrote a script to extract **low-confidence predictions** for manual review. Reviewing "
          "these with the team lead revealed recurring false positives, which I documented as edge cases for the next "
          "retraining cycle. This taught me that cleaning and analysis do not stop when a model is deployed."),
    ("p", "For the EdTech tools, the input data is documents. Many uploaded PDFs are large or scanned, so they are "
          "compressed and their text is extracted (with OCR for scanned pages) before being sent to the language model. "
          "I investigated user reports that handwritten books were often mis-tagged as printed. I collected a small sample "
          "of handwritten and printed pages, compared the tool's behaviour on both, adjusted the instructions and few-shot "
          "examples, and re-tested until handwritten detection improved."),
    ("ul", ["Practical activity: de-duplication and label checks; low-confidence prediction review; handwritten vs. printed sample analysis.",
            "Tools/technologies used: pandas, Python logging, Jupyter Notebook, PDF text extraction.",
            "Skills acquired: data quality checks, error analysis, building small evaluation sets from real user reports."]),

    ("h2", "2.3 Data Visualisation"),
    ("p", "Data visualisation turns numbers into pictures that people can understand quickly. A good chart answers one "
          "question clearly, uses the right type of chart for the data (bars to compare categories, lines for trends over "
          "time, histograms for distributions, scatter plots for relationships) and avoids clutter."),
    ("p", "In week 18 the content team asked for a simple way to see what kinds of books were being uploaded. I gathered "
          "their requirements, wrote a script that aggregates the category and subject fields produced by Acadeva Magic, "
          "and built a bar-chart view of the category distribution (Figure 2.2). I then added the distribution of "
          "topic-relevance scores from the Book Topic Ranker to the same view and presented it to the content team, who "
          "used it to decide which subjects needed more materials."),
    ("fig", S + "it_analytics.png", "Aggregating Acadeva Magic output into a category-distribution chart for the content team."),
    ("ul", ["Practical activity: built the content analytics view (category distribution and relevance-score distribution).",
            "Tools/technologies used: pandas, Matplotlib, Seaborn.",
            "Skills acquired: choosing chart types, gathering requirements from non-technical users, presenting findings."]),

    ("h2", "2.4 Programming and Software Development"),
    ("p", "A model is only useful if other software can use it. A large part of my placement was therefore software "
          "engineering: turning a training script into a service with a clear API, tests, documentation, and protection "
          "against misuse."),
    ("h3", "Serving the model with FastAPI"),
    ("p", "I scaffolded the serving application with **FastAPI**, replacing an earlier plan to use Flask, because FastAPI "
          "validates requests automatically with Pydantic and generates interactive documentation at `/docs`. I built a "
          "`/health` endpoint and a `/predict` endpoint, with the model loading code in `utils/model_utils.py` (Figure "
          "2.3). Two later improvements came from measuring rather than guessing. Profiling in week 14 showed that the "
          "vectoriser was being rebuilt on every request, so I moved model loading to start-up, which gave a clear "
          "response-time improvement in simple load tests. In week 15 I tightened the request schema with maximum length "
          "and required-field rules, added rate-limiting middleware, and checked that error responses never leak internal "
          "stack traces."),
    ("fig", S + "it_api.png", "FastAPI service for the phishing model with Pydantic validation, logging and rate limiting."),
    ("h3", "Automated testing"),
    ("p", "In week 12 I set up **pytest** for the project. The tests cover model loading, phishing and legitimate inputs, "
          "and edge cases such as empty text, very long text and non-ASCII characters (Figure 2.4). The new tests "
          "immediately uncovered two small bugs in the response schema, which I fixed. I also added a local test-runner "
          "script so the suite runs before each commit."),
    ("fig", S + "it_tests.png", "Examples of the pytest suite written for the /predict endpoint."),
    ("h3", "Shared helper for the AI tools"),
    ("p", "Acadeva's four AI content tools each repeated the same boilerplate for calling the Gemini API. In weeks 16 and "
          "17 I proposed and carried out a refactor that moved model initialisation, generation settings, JSON output and "
          "error handling into one shared helper (Figure 2.5), then migrated all four tools to it and verified that their "
          "outputs were unchanged. This made the AI layer much easier to maintain, and it later made it easy to find and "
          "fix a conflict between two services that shared the same API rate limit."),
    ("fig", S + "it_gemini.png", "The shared JavaScript helper used by Acadeva Magic, the Ranker, the Categorizer and Quithn."),
    ("ul", ["Practical activity: FastAPI service, request logging, pytest suite, performance fix, input validation and rate limiting, shared Gemini helper, README and contribution docs.",
            "Tools/technologies used: Python, FastAPI, Pydantic, Uvicorn, pytest, joblib, JavaScript/Node.js, Gemini API, Git, Swagger UI.",
            "Skills acquired: API design, testing, profiling, secure input handling, refactoring, technical writing."]),

    ("h2", "2.5 Exploratory Data Analysis"),
    ("p", "Exploratory Data Analysis (EDA) means getting to know a dataset before modelling it: its size, types, missing "
          "values, distributions and relationships. EDA prevents expensive mistakes, such as training a classifier on "
          "data that is 95% one class and then celebrating 95% accuracy."),
    ("p", "For the phishing data I examined the class balance of each source, the length of texts, and the most frequent "
          "tokens in each class. EDA also shaped evaluation: I added a **per-source metrics breakdown** (email vs. URL "
          "vs. augmented) to the training report, because an overall score hid the fact that the first models were much "
          "weaker on disguised URLs than on emails. For the Book Topic Ranker, I compared the distributions of relevance "
          "scores across sample PDFs to flag books whose scores were inconsistent. All EDA was done in Jupyter Notebooks "
          "with pandas, Matplotlib and Seaborn, which keep code, output and explanation together in one document."),
    ("ul", ["Practical activity: class-balance checks, text-length and token analysis, per-source metrics, score-distribution comparison.",
            "Tools/technologies used: Jupyter Notebook, pandas, Matplotlib, Seaborn.",
            "Skills acquired: forming questions about data, spotting imbalance and hidden weaknesses, using EDA to design evaluation."]),

    ("h2", "2.6 Machine Learning Concepts and Modelling"),
    ("p", "Machine learning is the practice of building models that learn patterns from data instead of being explicitly "
          "programmed. My work covered two kinds: **supervised classification** for phishing detection, and **generative "
          "AI** with large language models for the EdTech tools."),
    ("h3", "Phishing detection: from baseline to six ranked candidates"),
    ("p", "Text must be converted to numbers before a classifier can use it. I used **TF-IDF** (term frequency-inverse "
          "document frequency), which gives each word or word pair a weight that is high when it is frequent in one "
          "document but rare across all documents. I used uni-grams and bi-grams, and added character-level features "
          "with a configurable cap after the full dataset caused a memory error. The first model was a Logistic "
          "Regression baseline evaluated on a **stratified** train/test split, so both sets keep the same proportion "
          "of phishing examples."),
    ("p", "I then extended the training script with a `get_model_candidates()` function that returns six TF-IDF "
          "pipelines (Figure 2.6): Logistic Regression, Linear SVC, a Linear SVC wrapped in `CalibratedClassifierCV` (so "
          "the API can return a meaningful confidence score, which a plain SVM does not provide), Multinomial Naive "
          "Bayes, an SGD classifier and a Passive-Aggressive classifier. A standard loop fits, times and evaluates every "
          "candidate on the same split, ranks them by a selectable metric with tie-breakers, writes everything to "
          "`training_report.json`, and saves the winner with joblib. Figure 2.7 shows the whole pipeline."),
    ("fig", S + "it_candidates.png", "Six candidate pipelines sharing one TF-IDF front end, and the stratified split."),
    ("fig", F + "lb_phishing_pipeline.png", "Phishing detection model: training and serving pipeline (logbook sketch, weeks 3 to 7).", {"width": 4.6}),
    ("p", "The evaluation metrics were chosen for an imbalanced, security-sensitive problem. Accuracy alone is "
          "misleading, so the main selection metric was the **F1 score of the phishing class**:"),
    ("table", ["Metric", "Formula", "What it tells us"],
     [["Accuracy", "(TP + TN) / all predictions", "Share of all predictions that are correct"],
      ["Precision", "TP / (TP + FP)", "Of the messages flagged as phishing, how many really are"],
      ["Recall", "TP / (TP + FN)", "Of all phishing messages, how many were caught"],
      ["F1 score", "2 x Precision x Recall / (Precision + Recall)", "Balance of precision and recall; used to rank models"]],
     "Classification metrics used to evaluate and rank the phishing models (TP = true positive, FP = false positive, "
     "FN = false negative, TN = true negative).", [1.1, 2.6, 2.8]),
    ("h3", "Hard examples through data augmentation"),
    ("p", "Reviewing early results showed that the model missed disguised URLs such as `p4ypal.com` or "
          "`paypal.verify-123.xyz`. The public datasets simply did not contain enough of them. I wrote generators for "
          "**typosquatting** variants (character substitutions such as a to 4, o to 0, l to 1, m to rn and w to vv), "
          "brand-in-subdomain spoofs and urgent-keyword domains (Figure 2.8), plus a curated list of real brand domains as "
          "hard negatives so the model would not start flagging genuine sites. The augmentation set is controlled by a "
          "`--url-augmentation-weight` flag."),
    ("fig", S + "it_augment.png", "Generating typosquatting and brand-spoofing URLs as hard training examples."),
    ("h3", "Safe retraining: champion and challenger"),
    ("p", "Retraining on new data should never make production worse. In week 13 I replaced the practice of overwriting "
          "a single model file with timestamped model versions and a `promote_model.py` script (Figure 2.9). A newly "
          "trained challenger replaces the production model only if it scores higher on the selection metric. I tested "
          "it with a deliberately weaker model to confirm that it correctly refused to promote."),
    ("fig", S + "it_promote.png", "Champion/challenger promotion: the production model is only replaced by a better one."),
    ("h3", "Generative AI: Acadeva's content tools"),
    ("p", "From week 8 I joined the EdTech sub-team, which uses Google's Gemini models through carefully engineered "
          "prompts. All four tools follow the same pattern (Figure 2.10): a book or article goes in with a system prompt, "
          "and a structured JSON object comes out."),
    ("ul", ["Acadeva Magic: generates book metadata (title, description, course code, terms, subject, category, quiz type, handwritten and explicit-content flags) from an uploaded PDF. I improved the few-shot examples to reduce hallucinated course codes, fixed multi-course-code parsing, improved handwritten detection and tightened explicit-content handling.",
            "Book Topic Ranker: scores a book's relevance (0.00 to 1.00) against a fixed list of 140+ topics. I refined the topic list and the scoring-consistency instructions.",
            "Content Categorizer: assigns one category to an article or post using few-shot examples. I curated examples for local news and fixed mishandling of sponsored content.",
            "Quithn: generates a 25-question quiz with options, correct answer, feedback and difficulty from a chapter. I improved the difficulty and JSON-validation instructions and fixed a duplicate-answer-option bug."]),
    ("fig", F + "lb_edtech_pipeline.png", "Acadeva EdTech AI content tools: the shared prompt-pipeline pattern (logbook sketch, weeks 8 to 10).", {"width": 4.6}),
    ("p", "The most important lesson from this work is that a language model's output must be treated as untrusted "
          "until it is validated: it can invent values that look plausible. Asking for structured JSON, giving clear "
          "few-shot examples, setting a low temperature and validating the output against a schema all reduce this risk. "
          "I applied the same lesson, more strictly, in the AI voice scribe of my IT project (Chapter Three)."),
    ("ul", ["Practical activity: TF-IDF feature extraction, six-model comparison, probability calibration, augmentation, champion/challenger retraining, prompt engineering for four LLM tools.",
            "Tools/technologies used: scikit-learn, joblib, Gemini API (gemini-2.0-flash / 1.5-flash), JSON schema output.",
            "Skills acquired: model selection and evaluation on imbalanced data, feature engineering for text, error analysis, safe deployment, prompt engineering."]),

    ("h2", "2.7 The Data Science Workflow"),
    ("p", "The most valuable thing I learned during the placement is not any single tool, but the **workflow** that "
          "connects them. A data science project is a cycle of well-defined steps, and skipping a step almost always "
          "causes problems later. Figure 2.11 shows the workflow as I learned and practised it. It is closely related to "
          "the industry-standard CRISP-DM process (Cross-Industry Standard Process for Data Mining)."),
    ("fig", F + "dg_ds_workflow.png", "The data science workflow: eight steps in a cycle, with feedback loops."),
    ("ol", ["Define the problem: state the question in terms of a decision. \"Flag phishing messages before a student clicks them\" is a problem; \"use machine learning\" is not. Decide how success will be measured (for example, phishing-class F1).",
            "Collect data: find or gather data that can answer the question: files, databases, APIs, surveys or logs. Record where it came from and its licence.",
            "Clean and prepare: handle missing values, remove duplicates, fix types and inconsistent labels, and join sources. This step usually takes the most time.",
            "Explore (EDA): study distributions, class balance, correlations and outliers with summary statistics and charts. EDA often changes the plan.",
            "Feature engineering: turn raw data into informative inputs, for example TF-IDF weights from text, family size from two columns, or rooms per household.",
            "Build models: start with a simple baseline, then try stronger models. Always split data into training and test sets, and use cross-validation where possible.",
            "Evaluate: measure performance on data the model has never seen, with metrics that fit the problem, and analyse the errors. Poor results send you back to the data, not just to a different algorithm.",
            "Deploy and communicate: put the model where it is used (an API, a dashboard, a report), explain results to non-technical people, then monitor it and retrain safely as new data arrives."]),
    ("table", ["Workflow step", "How it was applied in the phishing detection project"],
     [["1. Define the problem", "Acadeva needed an in-house model to flag phishing emails and URLs; success = phishing-class F1"],
      ["2. Collect data", "phishing_email.csv and the PhiUSIIL URL dataset"],
      ["3. Clean and prepare", "Label normalisation, merging, de-duplication, source column"],
      ["4. Explore", "Class balance per source; found weakness on disguised URLs"],
      ["5. Feature engineering", "TF-IDF word uni/bi-grams + character features; augmented hard examples"],
      ["6. Build models", "Logistic Regression baseline, then six ranked candidates"],
      ["7. Evaluate", "Accuracy, precision, recall, F1, per-source metrics, low-confidence review"],
      ["8. Deploy and communicate", "FastAPI /predict, README, training_report.json, champion/challenger retraining, team demos"]],
     "Mapping the data science workflow to the phishing detection project.", [1.8, 4.7]),

    ("h2", "2.8 Beginner Data Science Projects"),
    ("p", "To practise the complete workflow on well-known problems, I completed three classic beginner data science "
          "projects. They cover the three most common types of supervised learning problem: binary classification, "
          "regression and multi-class classification. All three were done in one Jupyter notebook "
          "(`report/notebooks/beginner_data_science_projects.ipynb`), and every number below comes from running it."),
    ("h3", "2.8.1 Project 1: Titanic Survival Prediction"),
    ("p", "**Problem.** Given a passenger's details, predict whether they survived the sinking of the Titanic in 1912. "
          "This is a binary classification problem. **Data.** 891 passengers with 15 columns, including class, sex, age, "
          "number of relatives on board, fare and port of embarkation. Only 38.4% survived."),
    ("p", "**Cleaning.** Age was missing for 177 passengers. Instead of filling them all with one average, I filled each "
          "missing age with the median age of passengers of the same class and sex, which is more realistic. The two "
          "missing embarkation ports were filled with the most common port, and the `deck` column (77% missing) was "
          "dropped. **Feature engineering.** I created `family_size` (siblings/spouses + parents/children + 1) and "
          "`is_child` (age under 13), encoded sex as 0/1 and one-hot encoded the port."),
    ("fig", F + "bp_titanic_eda.png", "Titanic EDA: survival by sex and by class, and age distribution by outcome."),
    ("p", "EDA (Figure 2.12) shows the famous \"women and children first\" pattern: 74.2% of women survived but only "
          "18.9% of men, and survival fell from 63.0% in first class to 24.2% in third class. I trained three models on an "
          "80/20 stratified split and also measured 5-fold cross-validated accuracy, which is more reliable on a small "
          "dataset (Table 2.3)."),
    ("table", ["Model", "Test accuracy", "5-fold CV accuracy"],
     [["Logistic Regression", "81.6%", "80.7%"], ["Decision Tree (max depth 4)", "79.9%", "80.7%"],
      ["Random Forest (300 trees)", "80.4%", "**82.2%**"]],
     "Titanic results.", [2.6, 1.8, 2.1]),
    ("fig", F + "bp_titanic_model.png", "Random Forest confusion matrix and feature importance for the Titanic model."),
    ("p", "**Findings.** The Random Forest had the best cross-validated accuracy (82.2%). Its feature importance (Figure "
          "2.13) confirms the EDA: sex is by far the strongest predictor, followed by fare, age and class. The confusion "
          "matrix shows the model is better at recognising passengers who died (101 of 110) than those who survived "
          "(43 of 69), which is common when one class is larger."),
    ("h3", "2.8.2 Project 2: House Price Prediction"),
    ("p", "**Problem.** Predict the median house value of a district in California from its characteristics. This is a "
          "regression problem, because the target is a continuous number. **Data.** The California Housing dataset: "
          "20,640 districts, with location, housing age, rooms, bedrooms, population, households, median income and "
          "proximity to the ocean."),
    ("p", "**Cleaning and features.** 207 missing `total_bedrooms` values were filled with the median. Raw totals are "
          "not comparable between large and small districts, so I engineered ratios: rooms per household, bedrooms per "
          "room and population per household. The categorical `ocean_proximity` column was one-hot encoded."),
    ("fig", F + "bp_housing_eda.png", "California housing EDA: value by location (point size = population) and income vs. value."),
    ("p", "The map (Figure 2.14) shows that coastal districts around the Bay Area and Los Angeles are the most expensive, "
          "and median income is strongly related to house value (correlation 0.69). Notice the horizontal line at "
          "$500,000: values above that were capped when the data was collected, a data quality issue that limits any "
          "model's accuracy at the top end."),
    ("table", ["Model", "MAE", "RMSE", "R²"],
     [["Linear Regression", "$50,889", "$72,669", "0.597"], ["Random Forest (150 trees)", "**$32,230**", "**$50,131**", "**0.808**"]],
     "House price results on the 20% test set.", [2.4, 1.3, 1.3, 1.0]),
    ("fig", F + "bp_housing_model.png", "Random Forest predicted vs. actual house values (points near the red line are accurate).", {"width": 4.0}),
    ("p", "**Findings.** The Random Forest explains about 81% of the variation in house values (R² = 0.808) and its "
          "average error is about $32,000, a 37% reduction compared with linear regression, because it can capture "
          "non-linear effects such as location. Figure 2.15 shows the predictions cluster around the perfect-prediction "
          "line, with the largest errors at the $500,000 cap."),
    ("h3", "2.8.3 Project 3: Iris Flower Classification"),
    ("p", "**Problem.** Identify which of three species (setosa, versicolor or virginica) an iris flower belongs to, "
          "from four measurements: sepal length and width, and petal length and width. This is a multi-class "
          "classification problem and the classic first project in machine learning. **Data.** 150 flowers, 50 of each "
          "species, with no missing values."),
    ("fig", F + "bp_iris_eda.png", "Pair plot of the four iris measurements, coloured by species.", {"width": 5.0}),
    ("p", "The pair plot (Figure 2.16) shows that setosa is completely separated by petal size, while versicolor and "
          "virginica overlap slightly. I used **K-Nearest Neighbours (KNN)**, which classifies a flower by the majority "
          "species of its k closest neighbours. To choose k, I tested every value from 1 to 20 on a stratified 70/30 "
          "split (Figure 2.17)."),
    ("fig", F + "bp_iris_model.png", "Choosing k for K-Nearest Neighbours, and the confusion matrix of the final model."),
    ("p", "**Findings.** With k = 5 the model classified 44 of the 45 test flowers correctly (97.8% accuracy). The only "
          "error was one virginica predicted as versicolor, exactly where the EDA showed the two species overlap."),
    ("table", ["Project", "Problem type", "Best model", "Result", "Key lesson"],
     [["Titanic survival", "Binary classification", "Random Forest", "82.2% CV accuracy", "Group-wise imputation and feature engineering"],
      ["House prices", "Regression", "Random Forest", "R² = 0.808, MAE $32,230", "Ratios beat raw totals; watch for capped data"],
      ["Iris species", "Multi-class classification", "KNN (k = 5)", "97.8% accuracy", "Tune hyper-parameters on held-out data"]],
     "Summary of the three beginner data science projects.", [1.2, 1.3, 1.1, 1.3, 1.6]),

    ("h2", "2.9 Other Technical and Professional Skills"),
    ("p", "Beyond the technical work, the placement developed skills that are just as important in a professional "
          "environment:"),
    ("ul", ["Teamwork and code review: every significant change, such as the shared-helper refactor and the explicit-content work, went through review with my supervisor before being merged.",
            "Knowledge sharing: in week 10 I walked PY50 trainees through the phishing-detection pipeline, and in week 24 I handed my work over to the next intern.",
            "Technical documentation: I wrote the project README, setup and contribution guides, a retraining guide, docs for the shared prompt helper and inline comments for complex code.",
            "Prioritisation and scope discipline: in week 19 I triaged a backlog of user-reported bugs by impact, and in week 21 I chose one meaningful improvement and finished it cleanly instead of starting several.",
            "Integration testing: in week 22 I ran the phishing API and the EdTech tools together end to end, which revealed a rate-limit conflict that unit tests could not catch.",
            "Communication and presentation: I presented the analytics view to the content team and delivered the end-of-placement demo to the Acadeva team."]),
    ("h2", "2.10 Conclusion"),
    ("p", "This chapter has presented the practical skills I acquired at Acadeva, from collecting and cleaning data to "
          "building, evaluating, serving and maintaining machine learning models and generative-AI tools. The data "
          "science workflow tied these activities together, and the three beginner projects demonstrated it end to end. "
          "The next chapter shows how I applied the same skills, in software engineering, data analysis and safe use of "
          "AI, to build my IT project: AraCare Health OS."),
]

# ================================================================== CHAPTER 3
# figure/table references in this chapter use {fig:id} / {tab:id}; ids are given in the block options
W = 5.8   # default screenshot width (inches)

CH3 = [
    ("h2", "INTRODUCTION"),
    ("p", "This chapter presents the IT project I developed by applying the skills acquired during SIWES: **AraCare "
          "Health OS**, a hospital operating system for Nigerian health facilities. The project combines the software "
          "engineering practices I used at Acadeva (APIs, validation, automated tests, documentation), the data science "
          "workflow (data modelling, analysis and visualisation), and the safe use of AI (grounded, human-reviewed "
          "language-model output). The chapter covers the background and problem, the aim and objectives, the "
          "methodology and tools, the system architecture and design, a walkthrough of the working system from login to "
          "every major screen, including the waiting-room TV triage display, an analysis of the system's data in a Python "
          "notebook, testing, and finally the challenges, limitations and future work."),
    ("h2", "3.1 Project Overview"),
    ("p", "AraCare Health OS is a modular hospital information system designed to run on **one server inside each "
          "hospital**, so that the hospital keeps working even when the internet is down. Staff use role-based web "
          "screens over the hospital's local network: reception registers and checks in patients, nurses take vital "
          "signs at triage, doctors write consultation notes and orders, and administrators manage staff and settings. "
          "A public TV screen in the waiting room shows which ticket numbers are being served and who should be ready "
          "next."),
    ("p", "The first release, documented in this report, delivers four modules end to end: **patient registration and "
          "check-in**, the **queue engine**, the **electronic health record (EHR)** for triage and consultation, and an "
          "**AI voice scribe** that turns dictation into a draft note entirely on the hospital's own computer. Billing, "
          "pharmacy and inventory, laboratory, capacity and finance dashboards, internal communications and IoT patient "
          "monitoring are fully designed in the project's documentation (`docs/`), and the events they will need are "
          "already being published, but they are not yet built."),
    ("table", ["Item", "Details"],
     [["Project title", "AraCare Health OS: an offline-first hospital operating system"],
      ["Type", "Full-stack web application (backend API + web client) with data analysis"],
      ["Backend repository", "github.com/Aniebiet1/ARACARE-HEALTH-OS-BACKEND (API, design docs, screenshots)"],
      ["Frontend repository", "github.com/Aniebiet1/ARACARE-HEALTH-OS-FRONTEND (React web client)"],
      ["Users", "Receptionists, nurses, doctors, administrators, patients (receipt, SMS, TV display)"],
      ["Release covered", "Registration and check-in, queue engine, EHR (triage and SOAP notes), AI voice scribe"],
      ["Size", "About 4,000 lines of Python in the backend, 11 detailed design documents, 47 automated tests"]],
     "AraCare Health OS at a glance.", [1.7, 4.8], {"id": "glance"}),

    ("h2", "3.2 Background of the Study"),
    ("p", "Outpatient departments (OPD) in Nigerian public and private hospitals are under constant pressure. The design "
          "document for the queue engine describes a typical morning: around 200 patients arrive between 07:30 and "
          "10:00, but three doctors who each see a patient every 8 to 12 minutes can see only about 60 patients in a "
          "session. The remaining patients wait for three to five hours. Many leave the premises to eat or run errands "
          "and lose their place, because the \"queue\" is a pile of paper folders on a desk. There is no reliable way to "
          "tell a patient how long they will wait, and no guarantee that a very sick patient is seen before a routine "
          "check-up."),
    ("p", "Clinical documentation has similar problems. Records are kept on paper cards and folders that are hard to "
          "find, easy to lose and often illegible. Paper notes do not produce standard diagnosis codes (ICD-10) that "
          "insurance (HMO) claims need, and they cannot warn a doctor that a patient is allergic to the drug being "
          "prescribed. Where electronic systems exist, they often depend on a constant internet connection, which many "
          "facilities do not have, and typing structured notes takes time that busy clinicians do not have. Voice "
          "dictation could help, but cloud speech services are expensive, send patient audio outside the hospital, and "
          "perform poorly on Nigerian accents, Pidgin English and noisy wards."),
    ("p", "These observations, together with what I learned at Acadeva about building reliable APIs and using AI "
          "safely, motivated the design of AraCare."),
    ("h2", "3.3 Problem Statement"),
    ("p", "Nigerian hospital outpatient departments lack an affordable, offline-capable system that can organise patient "
          "flow and capture structured clinical records safely. Specifically:"),
    ("ol", ["Queues are managed manually, so waiting is long, unpredictable and unfair, and urgent patients are not reliably prioritised.",
            "Patients who step away lose their place, and there is no way to inform them when their turn is near.",
            "Patient records are on paper, so they are lost, duplicated (the same patient registered several times with different spellings) and not searchable.",
            "Clinical safety checks, such as abnormal vital signs and drug allergies, depend entirely on human memory.",
            "Structured documentation is slow to type, and cloud-based voice tools are costly, need internet access and raise privacy concerns."]),
    ("h2", "3.4 Aim and Objectives"),
    ("p", "**Aim:** to design and implement an offline-first hospital operating system that organises outpatient flow "
          "fairly and captures structured, safe clinical records, with an optional local AI assistant for documentation."),
    ("p", "**Objectives:**"),
    ("ol", ["To build a patient registration and check-in module with unique patient numbers, duplicate detection, fuzzy name search and QR-coded receipts.",
            "To build a queue engine that prioritises patients by clinical need, prevents starvation of lower-priority patients, and shows live queue status on a waiting-room TV display.",
            "To build an EHR for triage vital signs and SOAP consultation notes with ICD-10 diagnoses, laboratory and drug orders, automatic vital-sign flags and an allergy hard-block.",
            "To build an AI voice scribe that runs locally, never writes to the record without a clinician's signature, and removes values that were not actually spoken.",
            "To secure the system with role-based access, audit logging and safe production settings, and verify it with automated tests.",
            "To analyse the data produced by the system in order to evaluate whether the queue rules work and to describe the patient population."]),
    ("h2", "3.5 Scope and Significance"),
    ("p", "The project covers the outpatient journey from arrival at reception to the end of the doctor's consultation, "
          "for a single facility running its own server. Laboratory and pharmacy steps are recorded as \"deferred\" "
          "journey steps so that visits complete cleanly now and the data is ready when those modules are added. Real SMS "
          "delivery is out of scope: messages are queued in an `outbound_messages` table, ready for an SMS gateway."),
    ("p", "The project is significant because it shows that a modern, safe hospital system does not require expensive "
          "cloud subscriptions or a constant internet connection. It reduces waiting-room crowding by letting patients "
          "wait elsewhere and return when called, protects patients with automatic safety checks, produces coded data for "
          "insurance claims and public-health reporting, and keeps patient data inside the hospital."),

    ("h2", "3.6 Methodology and Tools"),
    ("p", "The project followed an **incremental, design-first** approach. Before writing code, I wrote a detailed design "
          "document for each module (eleven documents in the `docs/` folder, covering registration, queues, EHR, the voice "
          "scribe, billing, inventory, capacity and finance dashboards, internal communications and IoT monitoring). Each "
          "document describes the real-world problem, the state machines, the data model and the edge cases. I then built "
          "the system as a **vertical slice**: a thin but complete path through registration, queues, EHR and scribe, "
          "rather than many half-finished modules. Every rule that protects patients was written as an automated test, "
          "and the user interface was checked by walking through a full visit and capturing the screenshots shown in "
          "Section 3.9."),
    ("table", ["Layer", "Technology", "Why it was chosen"],
     [["Backend API", "Python 3.11, FastAPI, Uvicorn", "Fast, automatic validation and API docs (as used at Acadeva)"],
      ["Data validation", "Pydantic v2", "Typed request/response models; validates AI output"],
      ["Database access", "SQLAlchemy 2.0, Alembic", "One codebase for SQLite and PostgreSQL; versioned migrations"],
      ["Database", "SQLite (development), PostgreSQL 16 (production)", "Zero-setup locally; robust in production"],
      ["Authentication", "JWT (PyJWT), salted password hashing", "Stateless tokens; lockout after failed logins"],
      ["Real-time updates", "WebSockets (FastAPI)", "Queue screens and TV refresh instantly"],
      ["Frontend", "React 18, Vite, jsQR, qrcode.react", "Fast single-page app; QR receipts and camera scanning"],
      ["Speech to text", "faster-whisper (OpenAI Whisper weights)", "Runs locally on CPU; MIT licence; no cost"],
      ["Note drafting", "Ollama with qwen2.5:7b, rule-based fallback", "Local LLM; keeps working if the model is absent"],
      ["Testing", "pytest, FastAPI TestClient", "47 automated tests of rules and full visit flows"],
      ["Deployment", "Docker, Docker Compose", "One command to run the API and PostgreSQL on a facility server"],
      ["Data analysis", "Jupyter, pandas, NumPy, Matplotlib, Seaborn", "Notebook analysis of system records (Section 3.10)"]],
     "Technology stack of AraCare Health OS.", [1.4, 2.4, 2.7], {"id": "stack"}),

    ("h2", "3.7 System Architecture"),
    ("p", "AraCare is a **modular monolith**: one deployable API process per facility, internally divided into modules "
          "that each own their own database tables (Figure {fig:arch}). This is simpler to deploy and maintain on a single "
          "hospital server than many separate microservices, while keeping the code organised so that modules could be "
          "separated later. Role-based web clients talk to the API over the hospital's local network using REST, and a "
          "WebSocket channel pushes queue changes to every screen instantly."),
    ("fig", F + "dg_architecture.png", "System architecture of AraCare Health OS.", {"id": "arch"}),
    ("p", "Modules never call each other's internals. Instead they communicate through **domain events** such as "
          "`VisitCheckedIn`, `TriageCompleted` and `NoteSigned`. Each event is written to an `outbox_events` table in the "
          "same database transaction as the change that caused it, so an event can never be lost or published for a "
          "change that was rolled back (Table {tab:events}). The same table will later feed SMS dispatch, cloud backup "
          "and the billing and pharmacy modules."),
    ("table", ["Event", "Published by", "Reacted to by (now)", "Planned subscribers"],
     [["PatientRegistered", "registration", "messaging (card SMS)", ""],
      ["VisitCheckedIn", "registration", "queues (journey + triage ticket)", "billing: draft invoice"],
      ["TriageCompleted", "ehr", "queues (doctor ticket, set priority)", ""],
      ["CriticalVitals", "ehr", "real-time alert", "on-call notification"],
      ["LabOrdered / Prescribed", "ehr (on sign)", "queues (deferred LAB/PHARM step)", "lab, pharmacy, inventory"],
      ["NoteSigned", "ehr", "queues (close doctor step)", "billing charge, HMO claim (ICD-10)"],
      ["JourneyClinicalCompleted", "queues", "log", "billing: cashier ticket"]],
     "Domain events: the only coupling between modules.", [1.7, 1.1, 2.0, 1.7], {"id": "events"}),
    ("p", "All data hangs off one **spine** (Figure {fig:spine}): a Patient has many Visits; each Visit has one Journey "
          "made of ordered JourneySteps (TRIAGE, OPD-GEN, LAB, ...), and each live step has a QueueTicket. Clinical "
          "records (vitals, the note, diagnoses and orders) attach to the Visit, so every future charge, stock movement or "
          "insurance claim will attach to the same visit too."),
    ("fig", F + "dg_data_model.png", "The data spine: Patient, Visit, Journey, JourneyStep and QueueTicket, with clinical records.", {"id": "spine"}),
    ("p", "Figure {fig:journey} shows how a patient moves through the system and which event moves them to the next "
          "step."),
    ("fig", F + "dg_journey.png", "The patient journey and the domain events that drive it.", {"id": "journey"}),

    ("h2", "3.8 Design and Implementation of the Core Modules"),
    ("h3", "3.8.1 Patient Registration and Check-in"),
    ("p", "Each patient receives a facility-scoped number such as `ARC-LAG-2026-000301` (system, state code, year, "
          "sequence), plus a global UUID so that records can be shared across facilities in future. Numbers are issued "
          "from a row-locked counter, so two receptionists registering patients at the same moment can never receive the "
          "same number (this is covered by a concurrency test). Before saving a new patient, the system checks for likely "
          "duplicates by phone number and similar name."),
    ("p", "Searching is designed for real Nigerian data, where the same name is spelled in different ways "
          "(Okonkwo/Okonkow, Babatunde/Babtunde) and phone numbers are written as 0803..., +234803... or 234803.... "
          "The search normalises phone numbers and scores each name token with a fuzzy string similarity (Figure "
          "{fig:search}). A scanned QR code or typed patient number goes straight to the exact record."),
    ("fig", S + "ac_search.png", "Phone normalisation and fuzzy name scoring for patient search (registration/service.py).", {"id": "search"}),
    ("p", "Checking in creates a Visit with a reason (new complaint, follow-up, antenatal, emergency) and a payment track "
          "(out of pocket, HMO, government, staff, waiver; waivers need administrator approval). The `VisitCheckedIn` "
          "event starts the journey and issues a triage ticket, and the receptionist prints a receipt with the ticket "
          "number and a QR code the patient can show on the next visit."),
    ("h3", "3.8.2 The Queue Engine"),
    ("p", "Every department has its own daily queue, and every patient in it is a **ticket** with exactly one state at a "
          "time (Figure {fig:states}). A ticket is WAITING until a staff member clicks \"Call next patient\"; it is then "
          "CALLED (an SMS is queued and the TV shows the number); when the patient appears it becomes IN_SERVICE, then "
          "COMPLETED. If the patient does not appear in time, a background sweeper marks the ticket NO_SHOW; the patient "
          "can rejoin once, and a second no-show cancels the ticket."),
    ("fig", F + "dg_state_machine.png", "Queue ticket state machine.", {"id": "states", "width": 5.6}),
    ("p", "The starting priority comes from the visit, not from guesswork (Figure {fig:priority}): emergency visits are "
          "EMERGENCY; follow-ups are FOLLOW_UP; antenatal visits, children under five and adults aged 65 or over are HIGH; "
          "everyone else is NORMAL. After triage, the nurse's assessment and the vital-sign rules can raise the priority "
          "for the doctor queue, and critical vital signs force EMERGENCY."),
    ("fig", S + "ac_priority.png", "Initial priority rules (queues/service.py).", {"id": "priority"}),
    ("p", "A simple priority queue would let a steady stream of HIGH patients keep a NORMAL patient waiting all day. "
          "AraCare prevents this with two techniques (Figure {fig:wfq}):"),
    ("ul", ["Aging: a NORMAL ticket that has waited more than 45 minutes is treated as HIGH, and a FOLLOW_UP ticket that has waited more than 90 minutes is treated as NORMAL. Aging is computed on read and never stored back, so it cannot snowball.",
            "Weighted fair queuing (WFQ): after 3 HIGH patients in a row, the next call goes to a waiting NORMAL patient; after 5 NORMAL patients in a row, a FOLLOW_UP patient gets a turn. EMERGENCY always goes first.",
            "Concurrency safety: the department's queue state row is locked before choosing, so two consulting rooms clicking at the same moment can never call the same patient."]),
    ("fig", S + "ac_wfq.png", "Aging, ordering and weighted fair queuing in pick_next() (queues/service.py).", {"id": "wfq", "max_h": 8.2}),
    ("p", "For example, if the triage queue holds H1, H2, H3, H4 (HIGH) and N1 (NORMAL), the calls go H1, H2, H3, then N1 "
          "because the HIGH burst limit of 3 was reached, then H4. Each waiting ticket's estimated wait is its position in "
          "the queue multiplied by the median service time of the last ten patients, divided by the number of counters active "
          "in the last hour; this estimate is shown on the TV display."),
    ("h3", "3.8.3 Electronic Health Record and Clinical Safety"),
    ("p", "The EHR records triage vitals (blood pressure, pulse, respiratory rate, temperature, SpO2, weight, height, BMI "
          "and pain score) and the doctor's SOAP note (Subjective, Objective, Assessment, Plan) with ICD-10 diagnoses, "
          "laboratory orders and prescriptions. Safety rules live in the server code, not only in the user interface, so "
          "they cannot be bypassed by a different client. The clinical logic is kept in a separate file of pure functions "
          "with no database access, which makes it easy to test and to defend."),
    ("p", "**Vital-sign flags.** Every saved set of vitals is checked against thresholds (Figure {fig:flags}): for example "
          "a temperature above 37.5 °C is a fever, and 39.5 °C or more is critical; SpO2 below 94% is abnormal and below "
          "90% is critical. Any critical flag publishes a `CriticalVitals` alert and forces EMERGENCY priority in the "
          "doctor queue."),
    ("fig", S + "ac_flags.png", "Vital-sign flagging rules (ehr/clinical_rules.py).", {"id": "flags", "max_h": 8.0}),
    ("p", "**Allergy hard-block.** When a doctor prescribes a drug, the server checks it against the patient's recorded "
          "allergies by **drug class**, not just by name (Figure {fig:allergy}). A patient recorded as allergic to "
          "\"penicillin\" is therefore blocked from receiving amoxicillin or Augmentin, and \"sulfa drugs\" blocks "
          "Septrin. The prescription is refused unless the doctor documents an override reason, which is stored and "
          "audited."),
    ("fig", S + "ac_allergy.png", "Drug-class allergy matching (ehr/clinical_rules.py).", {"id": "allergy"}),
    ("p", "**Signed notes are immutable.** A note cannot be signed without an assessment and at least one ICD-10 "
          "diagnosis. Once signed, its content is fingerprinted with a SHA-256 hash and can no longer be edited; "
          "corrections are added as dated addenda, which is what medico-legal practice requires."),
    ("h3", "3.8.4 The AI Voice Scribe"),
    ("p", "The voice scribe lets a nurse or doctor speak instead of type. Its design applies the lesson I learned at "
          "Acadeva, that language-model output must be treated as untrusted, much more strictly, because here a "
          "hallucinated number could harm a patient. Figure {fig:scribe} shows the pipeline."),
    ("fig", F + "dg_scribe.png", "AI voice scribe pipeline: from speech to a signed note.", {"id": "scribe"}),
    ("ul", ["Local only: speech is transcribed by faster-whisper and the draft is written by a local model served by Ollama, so no audio or text leaves the hospital and there is no per-use cost.",
            "Consent first: the patient's consent to recording is stored (append-only) before any audio is processed, and the audio file is deleted right after transcription.",
            "Grounding: any vital-sign number in the AI draft that does not literally appear in the transcript is removed and reported as dropped (Figure {fig:ground}).",
            "Draft, never record: the scribe only fills the form. Suggested diagnoses, tests and drugs appear as chips that the clinician must accept, and the allergy check still runs on every accepted drug. Nothing is saved until the clinician signs.",
            "Graceful degradation: if Whisper is not installed, dictation can be typed or pasted; if Ollama is not running, a rule-based extractor takes over. The manual forms always work."]),
    ("fig", S + "ac_ground.png", "Grounding: removing numbers the clinician never said (scribe/structure.py).", {"id": "ground"}),
    ("h3", "3.8.5 Events, Security and Production Safety"),
    ("p", "The event bus (Figure {fig:bus}) writes each event to the outbox, runs the subscribed handlers in the same "
          "transaction, and only broadcasts WebSocket notifications **after** the transaction commits, so screens never "
          "show a change that was rolled back. WebSocket messages carry only the event name, never patient data."),
    ("fig", S + "ac_events.png", "In-process event bus with a transactional outbox (app/events.py).", {"id": "bus"}),
    ("p", "Security measures include role-based permissions (a nurse cannot write a doctor's note; a doctor cannot "
          "register patients), JWT authentication, account lockout for 15 minutes after five wrong passwords, forced "
          "password change for new and reset accounts, sign-out everywhere when a password or role changes, an audit log "
          "entry for every view of a chart, and a public TV display that shows only ticket numbers and initials. In "
          "production mode the server refuses to start with a weak secret key or a wildcard CORS origin (Figure "
          "{fig:config}), and no demo accounts are created."),
    ("fig", S + "ac_config.png", "The server refuses to start with unsafe production settings (app/config.py).", {"id": "config"}),

    ("h2", "3.9 System Walkthrough: User Interface"),
    ("p", "This section walks through the working system in the order a visit happens, from signing in to a signed "
          "consultation note, followed by the administrator's screens and the mobile layout. All screenshots were taken "
          "from the running application with the demo facility \"General Hospital Ikeja\"; the patients are synthetic. "
          "Where two screens are shown side by side, the caption describes the left one first."),
    ("h3", "3.9.1 Sign In and Account Security"),
    ("p", "Every staff member signs in with a username and password (Figure {fig:login}). A wrong password shows a "
          "neutral message that does not reveal whether the username exists, and repeated failures lock the account for "
          "15 minutes. Passwords can be changed from any screen (Figure {fig:pw}); new passwords must be at least eight "
          "characters and mix letters with numbers or symbols, and changing one signs the user out on all other devices."),
    ("fig", P + "01-login.png", "Sign-in page (left) and the message shown after a wrong password (right).",
     {"id": "login", "pair": [P + "01-login.png", P + "02-login-wrong-password.png"], "name": "login_pair", "width": 6.4}),
    ("fig", P + "14-change-password.png", "Change-password dialog.", {"id": "pw", "width": 4.6}),
    ("h3", "3.9.2 Waiting-Room TV Display (Triage and Doctor Queues)"),
    ("p", "The TV display is a public page meant for a large screen in each waiting area. Figure {fig:tvtri} shows the "
          "**triage** display: the ticket being served and its triage bay on the left, the next patients with their "
          "estimated wait on the right, and the day's statistics (waiting, served today, average wait) at the bottom. "
          "To protect privacy it shows only initials and surnames, never full names or clinical information. Figure "
          "{fig:tvopd} shows the same display for the General Outpatient (doctor) clinic, with two patients being "
          "served at once."),
    ("fig", P + "03-tv-display-triage.png", "Waiting-room TV display for the triage queue.", {"id": "tvtri", "width": 5.6}),
    ("fig", P + "04-tv-display-doctor-clinic.png", "Waiting-room TV display for the doctor (OPD) queue.", {"id": "tvopd", "width": 4.5}),
    ("p", "The display refreshes instantly through the WebSocket whenever any ticket changes, and every 10 seconds as a "
          "fallback (Figure {fig:tvcode})."),
    ("fig", S + "ac_tv.png", "React component behind the TV display (frontend/src/pages/TV.jsx).", {"id": "tvcode", "width": 5.8}),
    ("h3", "3.9.3 Reception: Finding, Registering and Checking In Patients"),
    ("p", "The receptionist's home screen offers two ways to find a returning patient: scanning the QR code on their "
          "receipt, or searching by phone number, patient number or name. A fuzzy search for \"Okafor\" returns Okafor, "
          "Okoro and Okon records ranked by similarity (Figure {fig:rec}). Selecting a patient opens their profile with "
          "the check-in form, while a new patient is registered with a short form in which only surname, first name, "
          "phone, date of birth and sex are required (Figure {fig:recprof})."),
    ("fig", P + "05-reception-dashboard.png", "Reception home screen (left) and fuzzy search results for \"Okafor\" (right).",
     {"id": "rec", "pair": [P + "05-reception-dashboard.png", P + "06-reception-search-results.png"], "name": "rec_pair", "width": 6.4}),
    ("fig", P + "07-reception-patient-profile-checkin.png", "Patient profile with the check-in form (left) and the new patient registration form (right).",
     {"id": "recprof", "pair": [P + "07-reception-patient-profile-checkin.png", P + "09-reception-new-patient-form.png"], "name": "recprof_pair", "width": 6.4}),
    ("p", "On saving, the patient number is generated and sent by SMS, known allergies are highlighted in amber, and the "
          "receptionist can ask for consent to take a photo (Figure {fig:registered})."),
    ("fig", P + "10-reception-patient-registered.png", "Patient registered, with known allergies highlighted and the optional photo consent.", {"id": "registered", "width": 5.0}),
    ("p", "Every patient can be given a printable **patient card** with a QR code, and each check-in produces a **visit "
          "receipt** showing the ticket number (here TRI-031), where to go next, payment details and allergies (Figure "
          "{fig:receipt}). On the next visit the receptionist scans the code with a webcam, a handheld scanner, or a "
          "photo of the receipt on the patient's phone, and reception keeps a live overview of both queues with each "
          "patient's priority and waiting time (Figure {fig:scan})."),
    ("fig", P + "08-reception-patient-card.png", "Printable patient card (left) and the check-in receipt with ticket TRI-031 (right).",
     {"id": "receipt", "pair": [P + "08-reception-patient-card.png", P + "11-reception-checkin-receipt.png"], "name": "receipt_pair", "width": 6.4}),
    ("fig", P + "12-reception-qr-scanner.png", "QR receipt scanner (left) and the live queue overview for triage and the doctor queue (right).",
     {"id": "scan", "pair": [P + "12-reception-qr-scanner.png", P + "13-reception-queue-overview.png"], "name": "scan_pair", "width": 6.4}),
    ("h3", "3.9.4 Nurse Triage"),
    ("p", "The nurse sees the triage queue in priority order (Figure {fig:nurse}, left). TRI-025, a NORMAL patient who "
          "has waited 47 minutes, is shown as HIGH with a \"Long wait\" label: this is the aging rule at work. Clicking "
          "\"Call next patient\" calls the next ticket and opens the vital-signs form (right), where the nurse marks the "
          "patient as arrived or not here."),
    ("fig", P + "15-nurse-triage-dashboard.png", "Nurse triage dashboard with TRI-025 promoted by aging (left), and a patient called with the vital-signs form open (right).",
     {"id": "nurse", "pair": [P + "15-nurse-triage-dashboard.png", P + "16-nurse-patient-called.png"], "name": "nurse_pair", "width": 6.4}),
    ("p", "Instead of typing, the nurse can use the voice note. After the patient agrees to be recorded, the nurse "
          "records or types what was said, and \"Fill in the form\" extracts each value into the vital-signs form for the "
          "nurse to check (Figure {fig:nvoice}). On saving, the system flags abnormal values: here fever 38.9 °C, BP "
          "150/95, pulse 108 and respiratory rate 22 are flagged, and the patient moves to the doctor queue (Figure "
          "{fig:nflags})."),
    ("fig", P + "17-nurse-voice-scribe.png", "Voice note with recorded consent (left) and the vital signs filled in from it, for the nurse to check (right).",
     {"id": "nvoice", "pair": [P + "17-nurse-voice-scribe.png", P + "18-nurse-vitals-from-voice.png"], "name": "nvoice_pair", "width": 6.4}),
    ("fig", P + "19-nurse-triage-saved-with-flags.png", "Triage saved, with abnormal vital signs flagged.", {"id": "nflags", "width": 5.0}),
    ("h3", "3.9.5 Doctor Consultation"),
    ("p", "The doctor's queue works the same way, and calling a patient opens their chart with today's vitals and "
          "complaint (Figure {fig:doc}). The doctor can start from a template such as \"Uncomplicated malaria\", which "
          "pre-fills the note, diagnosis, tests and drugs, or dictate the consultation and let the scribe draft the SOAP "
          "note for review (Figure {fig:tmpl})."),
    ("fig", P + "20-doctor-dashboard.png", "Doctor dashboard with the doctor queue (left) and the patient chart opened for consultation (right).",
     {"id": "doc", "pair": [P + "20-doctor-dashboard.png", "report/build/_tmp/21-doctor-patient-chart_crop.png"], "name": "doc_pair", "width": 6.4,
      "crops": {"report/build/_tmp/21-doctor-patient-chart_crop.png": [P + "21-doctor-patient-chart.png", (0, 0, 2160, 1450)]}}),
    ("fig", P + "22-doctor-note-from-template.png", "Clinical note from the \"Uncomplicated malaria\" template (left) and a SOAP note drafted from the doctor's dictation (right).",
     {"id": "tmpl", "pair": ["report/build/_tmp/22-doctor-note-from-template_crop.png", "report/build/_tmp/23-doctor-voice-scribe-draft_crop.png"],
      "name": "tmpl_pair", "width": 6.4,
      "crops": {"report/build/_tmp/22-doctor-note-from-template_crop.png": [P + "22-doctor-note-from-template.png", (560, 0, 2160, 2050)],
                "report/build/_tmp/23-doctor-voice-scribe-draft_crop.png": [P + "23-doctor-voice-scribe-draft.png", (560, 380, 2160, 2150)]}}),
    ("p", "Diagnoses are searched by keyword and stored with their ICD-10 code; here \"malaria\" finds B50.9, "
          "Plasmodium falciparum malaria. Laboratory tests and medicines are added from suggestions or typed in (Figure "
          "{fig:icd})."),
    ("fig", P + "24-doctor-icd10-diagnosis.png", "ICD-10 diagnosis search (left) and laboratory orders and prescriptions (right).",
     {"id": "icd", "pair": ["report/build/_tmp/24-doctor-icd10-diagnosis_crop.png", "report/build/_tmp/25-doctor-labs-and-prescriptions_crop.png"],
      "name": "icd_pair", "width": 6.4,
      "crops": {"report/build/_tmp/24-doctor-icd10-diagnosis_crop.png": [P + "24-doctor-icd10-diagnosis.png", (560, 1700, 2160, 2800)],
                "report/build/_tmp/25-doctor-labs-and-prescriptions_crop.png": [P + "25-doctor-labs-and-prescriptions.png", (560, 2450, 2160, 3522)]}}),
    ("p", "Figure {fig:block} shows the allergy hard-block in action. This patient is recorded as allergic to "
          "penicillin, and the doctor tries to prescribe amoxicillin. The server refuses it, explains why, and offers to "
          "choose another medicine or document a reason to override (left). When the note is signed it becomes "
          "read-only, the orders are sent, and the journey tracker shows the patient's next steps, laboratory and "
          "pharmacy (right)."),
    ("fig", P + "26-doctor-allergy-safety-block.png", "Allergy safety block for a penicillin-allergic patient (left) and the signed visit with the journey tracker (right).",
     {"id": "block", "pair": ["report/build/_tmp/26-doctor-allergy-safety-block_crop.png", "report/build/_tmp/27-doctor-visit-signed-journey_crop.png"],
      "name": "block_pair", "width": 6.4,
      "crops": {"report/build/_tmp/26-doctor-allergy-safety-block_crop.png": [P + "26-doctor-allergy-safety-block.png", (560, 2500, 2160, 3987)],
                "report/build/_tmp/27-doctor-visit-signed-journey_crop.png": [P + "27-doctor-visit-signed-journey.png", (820, 0, 2160, 2664)]}}),
    ("h3", "3.9.6 Administration"),
    ("p", "Administrators manage staff accounts: they create accounts with a temporary password that must be changed "
          "at first login, change roles, reset passwords and deactivate accounts (Figure {fig:staff}). The branding page "
          "sets the facility's name, address, logo and receipt motto with a live receipt preview, and visits on the "
          "waiver payment track wait for an administrator's approval (Figure {fig:brand})."),
    ("fig", P + "28-admin-staff-management.png", "Staff management (left) and adding a staff member with a temporary password (right).",
     {"id": "staff", "pair": [P + "28-admin-staff-management.png", P + "29-admin-add-staff.png"], "name": "staff_pair", "width": 6.4}),
    ("fig", P + "30-admin-branding-receipt.png", "Facility branding with live receipt preview (left) and a waiver check-in awaiting approval (right).",
     {"id": "brand", "pair": [P + "30-admin-branding-receipt.png", P + "34-admin-checkin-waiver-approval.png"], "name": "brand_pair", "width": 6.4}),
    ("p", "The records pages give full accountability: the audit log of who did what and when, the system event log "
          "from the outbox (Figure {fig:audit}), and the queued SMS messages to patients (Figure {fig:sms})."),
    ("fig", P + "31-admin-audit-log.png", "Audit log (left) and system events from the transactional outbox (right).",
     {"id": "audit", "pair": [P + "31-admin-audit-log.png", P + "32-admin-system-events.png"], "name": "audit_pair", "width": 6.4}),
    ("fig", P + "33-admin-sms-messages.png", "Queued SMS messages to patients.", {"id": "sms", "width": 4.8}),
    ("h3", "3.9.7 Mobile Layout"),
    ("p", "The same web client adapts to phones and tablets (Figure {fig:mobile}), so a receptionist or nurse can work "
          "from a phone if a desktop is not available."),
    ("fig", P + "35-mobile-login.png", "Mobile layout: sign in, reception and queues.",
     {"id": "mobile", "pair": [P + "35-mobile-login.png", P + "36-mobile-reception.png", P + "37-mobile-queues.png"],
      "name": "mobile_triple", "width": 4.6}),

    ("h2", "3.10 Data Analysis of AraCare Records (Python Notebook)"),
    ("p", "A hospital system is also a source of data for better decisions. To evaluate whether AraCare's rules work and "
          "to show what a manager could learn from the system, I analysed six weeks of records in a Jupyter notebook "
          "(`report/notebooks/aracare_patient_flow_analysis.ipynb`), following the data science workflow from Chapter "
          "Two. Because real patient data cannot be used in a student report, the dataset was produced by the project's "
          "own data generator (`python -m app.mock_data --seed 2026`), which writes backdated history through the same "
          "rules as the live code: ticket numbering, the journey cascade, triage flags, the allergy block and signed-note "
          "hashing. It contains 407 patients, 852 visits, 1,664 queue tickets, 812 vital-sign records and 777 signed "
          "notes from 24 August to 5 October 2026."),
    ("p", "**Preparation.** The tables were loaded from the database with pandas, timestamps were converted from UTC to "
          "Lagos time, and ages were computed from dates of birth. Blood pressure was missing in 209 vital-sign records, "
          "because it is not routinely taken for young children, so those gaps were left as missing rather than filled "
          "with invented values."),
    ("h3", "Who are the patients?"),
    ("fig", F + "ac_demographics.png", "Registered patients by age band and sex, and visits by payment track.", {"id": "demo"}),
    ("p", "The largest group is women aged 30 to 44, reflecting antenatal care and typical health-seeking behaviour, and "
          "about one in four patients is a child (Figure {fig:demo}). About 69% of visits are paid out of pocket and 28% "
          "through an HMO, so the billing module must handle cash and insurance claims equally well."),
    ("h3", "When do patients arrive?"),
    ("fig", F + "ac_arrivals.png", "Check-ins by hour of day and visits per day by weekday.", {"id": "arrive"}),
    ("fig", F + "ac_daily_volume.png", "Daily outpatient volume over six weeks, with the 7-day moving average.", {"id": "daily"}),
    ("p", "About 42% of all check-ins happen between 08:00 and 11:00, with the peak at 09:00 (Figure {fig:arrive}). "
          "Monday is the busiest day, at around 30 visits, weekdays settle at 20 to 25 and weekends are quiet. The 7-day "
          "average is flat at about 20 visits per day (Figure {fig:daily}), so the pattern is a weekly cycle rather than "
          "growth. **Recommendation:** staff an extra triage bay on weekday mornings, especially Mondays."),
    ("h3", "Does the priority system work?"),
    ("fig", F + "ac_wait_by_priority.png", "Waiting time before being called, by priority tier and queue.", {"id": "wait"}),
    ("table", ["Queue", "Priority", "Patients", "Median wait (min)", "Maximum wait (min)"],
     [["Doctor (OPD)", "EMERGENCY", "34", "2.4", "4.9"], ["Doctor (OPD)", "HIGH", "433", "23.8", "39.9"],
      ["Doctor (OPD)", "NORMAL", "309", "57.2", "94.8"], ["Triage (nurse)", "EMERGENCY", "34", "13.0", "66.4"],
      ["Triage (nurse)", "HIGH", "456", "20.1", "68.5"], ["Triage (nurse)", "NORMAL", "322", "34.0", "68.0"]],
     "Waiting time by queue and priority tier.", [1.4, 1.2, 1.0, 1.5, 1.4], {"id": "waits"}),
    ("p", "The doctor queue shows the priority system working exactly as designed (Figure {fig:wait} and Table "
          "{tab:waits}): median waits of about 2 minutes for EMERGENCY, 24 for HIGH and 57 for NORMAL patients. Yet no "
          "NORMAL patient waited more than about 95 minutes, which shows that weighted fair queuing and aging prevent "
          "starvation. In the triage queue the differences are smaller because priority is only fully known after the "
          "nurse has taken the vital signs: the tier shown there is the one the patient ended up with."),
    ("fig", F + "ac_time_in_clinic.png", "Total time from joining the triage queue to the end of the consultation.", {"id": "total"}),
    ("p", "End to end, a typical NORMAL patient spends about 116 minutes from joining the triage queue to leaving the "
          "consulting room, a HIGH-priority patient about 70 minutes and an emergency about 44 minutes (Figure "
          "{fig:total}). Most of that time is waiting, which is why the receipt, SMS and TV display matter: patients can "
          "wait outside and return when their number is close."),
    ("h3", "Clinical picture"),
    ("fig", F + "ac_vitals.png", "Abnormal-vital flags raised at triage, and correlation between vital signs.", {"id": "vitals"}),
    ("p", "Three in four triaged patients had at least one abnormal vital sign, and fever was by far the most common flag "
          "(Figure {fig:vitals}), as expected in a malaria-endemic area. Pulse and respiratory rate rise together "
          "(r = 0.57) and both fall as SpO2 rises, which supports combining these flags when raising priority."),
    ("fig", F + "ac_top_diagnoses.png", "Top 10 primary diagnoses by ICD-10 code.", {"id": "dx"}),
    ("p", "Malaria (B50.9) accounts for 31% of all primary diagnoses, followed by upper respiratory infection (9%) and "
          "gastroenteritis (8.5%) (Figure {fig:dx}). Because every diagnosis is coded, this report can be produced "
          "instantly for disease surveillance or for planning drug stock, which is impossible with paper notes."),
    ("h3", "Use of the AI voice scribe"),
    ("fig", F + "ac_scribe_usage.png", "Signed notes per week by source, and scribe sessions by role.", {"id": "scribeuse"}),
    ("p", "About 8% of signed notes were drafted by voice, rising from a handful in the first week, and the scribe was "
          "used almost equally by doctors (63 sessions) and nurses (57 sessions) (Figure {fig:scribeuse}). Every one of "
          "the 120 drafts was reviewed and accepted by a clinician before signing, as the design requires."),
    ("table", ["Question", "Answer from the data"],
     [["Who are the patients?", "Largest group: women aged 30 to 44; about 1 in 4 is a child; 69% pay out of pocket"],
      ["When do they arrive?", "42% between 08:00 and 11:00; Mondays busiest; about 20 visits per day"],
      ["Does prioritisation work?", "Doctor-queue medians: EMERGENCY 2 min, HIGH 24 min, NORMAL 57 min; no starvation"],
      ["How long is a visit?", "About 2 hours for a NORMAL patient, mostly waiting"],
      ["What is treated most?", "Malaria (31%); fever is the most common triage flag"],
      ["Is the scribe used safely?", "8% of notes; all 120 drafts reviewed and accepted by a clinician"]],
     "Summary of findings from the AraCare data analysis.", [2.0, 4.5], {"id": "findings"}),

    ("h2", "3.11 Testing and Validation"),
    ("p", "Testing focused on the rules that protect patients and on full visit flows. The backend has **47 automated "
          "tests**, written with pytest and FastAPI's TestClient, each running against a fresh database. All 47 pass "
          "(Figure {fig:pytest})."),
    ("table", ["Test file", "Tests", "What is verified"],
     [["test_flow.py", "9", "Full visit journey; roles; duplicate detection and fuzzy search; sign requires ICD-10; allergy block "
                            "and documented override; critical vitals force EMERGENCY"],
      ["test_queue.py", "7", "Emergency first; elders outrank adults; WFQ prevents starvation; aging; no-show, rejoin and "
                             "cancel; TV shows no full names and shows ETAs"],
      ["test_scribe.py", "8", "Grounding drops invented numbers; consent gate; Ollama output validated; fallback to rules "
                              "when Ollama or Whisper is down; audio discarded"],
      ["test_hardening.py", "13", "Unsafe production settings refused; login lockout; token revocation; concurrent "
                                  "registrations get unique numbers; day-end sweeper; upload limits; audit record IDs"],
      ["test_features.py", "10", "Allergy class aliases (sulfa blocks Septrin); scanner noise tolerance; receipts; photo "
                                 "privacy; branding; broken Whisper install degrades safely"]],
     "Automated test suite of the AraCare backend.", [1.4, 0.6, 4.5], {"id": "tests"}),
    ("fig", S + "ac_pytest.png", "Test run: all 47 backend tests pass.", {"id": "pytest", "max_h": 8.2}),
    ("p", "In addition to automated tests, the complete flow was tested manually through the user interface, from "
          "registration to a signed note, on a desktop browser, a 1080p TV screen and a phone-sized screen, producing the "
          "screenshots in Section 3.9."),
    ("h2", "3.12 Deployment"),
    ("p", "A facility server runs AraCare with Docker Compose: one command starts PostgreSQL 16 and the API, the "
          "database schema is upgraded automatically by Alembic at start-up, and a health check is available at "
          "`/api/health`. In production the first administrator is created from an environment variable and must change "
          "the password at first login; interactive API documentation is disabled unless explicitly enabled. Only one "
          "API process runs per facility because the queue sweeper and WebSocket hub are in-process; the documentation "
          "explains how to back up the database daily and how to place the server behind HTTPS."),

    ("h2", "3.13 Challenges"),
    ("ul", ["Fairness versus urgency: a strict priority queue starved NORMAL patients in early tests. Solving it required the WFQ burst limits and aging, and careful tests to prove both properties at once.",
            "Concurrency: two receptionists or two consulting rooms acting at the same moment could receive the same patient number or call the same patient. Row-level locks on the counter and queue-state rows fixed this.",
            "AI hallucination: the local language model sometimes produced plausible vital signs that were never spoken. The grounding rule and Pydantic validation of model output made this safe.",
            "Running AI offline on modest hardware: Whisper and a 7-billion-parameter model are heavy for a hospital PC, so model sizes are configurable and every AI step has a non-AI fallback.",
            "Messy real-world input: Nigerian name spellings, phone formats and allergy descriptions (\"sulfa drugs\", \"NSAIDs\") required fuzzy search, phone normalisation and drug-class aliases.",
            "Day boundaries: visits left open overnight blocked the patient's next check-in; a sweeper now closes them as abandoned after local midnight."]),
    ("h2", "3.14 Limitations and Future Work"),
    ("p", "**Limitations.** The current release covers outpatient registration, queues, triage and consultation only. "
          "SMS messages are queued but not sent, because no SMS gateway is connected. The analysis in Section 3.10 uses "
          "generated data, so its numbers illustrate the system's behaviour rather than measure a real hospital. The "
          "voice scribe has not yet been evaluated with real Nigerian clinicians, accents and ward noise, and the system "
          "supports a single API process per facility."),
    ("p", "**Future work.** The next releases will implement the modules already designed in `docs/`: billing and the "
          "cashier queue with HMO claims, pharmacy and inventory with stock reservation on `Prescribed`, the laboratory "
          "queue, capacity and finance dashboards, internal communications and IoT bedside monitoring. Other planned "
          "work includes connecting a Nigerian SMS gateway, cloud backup and analytics sync from the outbox, Redis pub/sub "
          "to run several API processes, a FHIR API for interoperability, and a pilot in a real facility to measure "
          "waiting times before and after deployment and to fine-tune the speech model for local accents."),
    ("h2", "3.15 Conclusion"),
    ("p", "This chapter presented AraCare Health OS, an offline-first hospital operating system that I designed and "
          "built by applying the skills acquired during my SIWES at Acadeva. The system registers and checks in patients "
          "with QR receipts, manages queues fairly with weighted fair queuing and aging, shows live status on a "
          "waiting-room TV, records triage and consultations with automatic safety checks and ICD-10 coding, and offers "
          "a local AI voice scribe that can never write to the record without a clinician's review. It is protected by "
          "role-based security and audit logging and verified by 47 passing automated tests. The data analysis confirmed "
          "that the queue rules behave as designed and showed how the same records can guide staffing and planning. "
          "Together, the placement and the project demonstrated the full journey from data to working software: "
          "understanding a real problem, designing carefully, building and testing, analysing the results, and "
          "communicating them clearly."),
]

CHAPTERS = [(1, "Introduction to SIWES Placement", CH1),
            (2, "Practical Skills Acquired During SIWES", CH2),
            (3, "IT Project on AraCare Health OS", CH3)]

REFERENCES = [
    "Acadeva Limited. (2026). Acadeva organisation information for SIWES reports. Uyo: Acadeva Limited.",
    "Chapman, P., Clinton, J., Kerber, R., Khabaza, T., Reinartz, T., Shearer, C., & Wirth, R. (2000). CRISP-DM 1.0: "
    "Step-by-step data mining guide. SPSS Inc.",
    "Demers, A., Keshav, S., & Shenker, S. (1989). Analysis and simulation of a fair queueing algorithm. ACM SIGCOMM "
    "Computer Communication Review, 19(4), 1-12.",
    "FastAPI. (2026). FastAPI documentation. https://fastapi.tiangolo.com",
    "Géron, A. (2019). Hands-on machine learning with Scikit-Learn, Keras and TensorFlow (2nd ed.). O'Reilly Media. "
    "(Source of the California Housing dataset copy used.)",
    "Google. (2026). Gemini API documentation: structured output. https://ai.google.dev",
    "Industrial Training Fund. (2016). Students Industrial Work Experience Scheme (SIWES): Guidelines and operational "
    "procedures. Abuja: ITF.",
    "Kaggle / Encyclopedia Titanica. (n.d.). Titanic passenger dataset (seaborn-data copy). "
    "https://github.com/mwaskom/seaborn-data",
    "Pace, R. K., & Barry, R. (1997). Sparse spatial autoregressions. Statistics & Probability Letters, 33(3), 291-297.",
    "Pedregosa, F., et al. (2011). Scikit-learn: Machine learning in Python. Journal of Machine Learning Research, 12, "
    "2825-2830.",
    "Prasad, A., & Chandra, S. (2024). PhiUSIIL: A diverse security profile empowered phishing URL detection framework "
    "based on similarity index and incremental learning. Computers & Security, 136, 103545.",
    "Radford, A., Kim, J. W., Xu, T., Brockman, G., McLeavey, C., & Sutskever, I. (2023). Robust speech recognition via "
    "large-scale weak supervision. Proceedings of the 40th International Conference on Machine Learning (ICML).",
    "Richardson, C. (2018). Microservices patterns: With examples in Java (transactional outbox pattern). Manning.",
    "Fisher, R. A. (1936). The use of multiple measurements in taxonomic problems. Annals of Eugenics, 7(2), 179-188.",
    "World Health Organization. (2019). International statistical classification of diseases and related health "
    "problems, 10th revision (ICD-10). Geneva: WHO.",
    "World Health Organization. (2023). World malaria report 2023. Geneva: WHO.",
]
REFERENCES.sort()

APPENDICES = [
    ("h3", "Appendix A: AraCare API Endpoints (all under /api)"),
    ("table", ["Area", "Endpoints"],
     [["Authentication", "/auth/login, /auth/me, /auth/change-password"],
      ["Patients", "/patients, /patients/search, /patients/{id}/check-in, receipts, photos"],
      ["Queues", "/queues/{dept}, /queues/{dept}/call-next, /tickets/{id}/{arrived | no-show | rejoin | cancel}"],
      ["TV display (public)", "/display/{dept}; WebSocket /ws/queue"],
      ["EHR", "/ehr/visits/{id}/triage, /ehr/visits/{id}/note, /ehr/notes/{id}/sign, ICD-10 search, orders, allergies"],
      ["Scribe", "/scribe/consent, /scribe/transcribe, /scribe/draft"],
      ["Administration", "/admin/audit, /admin/events, /admin/messages, /admin/staff (list, create, update, reset-password)"],
      ["Health", "/health"]],
     "AraCare API surface.", [1.6, 4.9]),
    ("h3", "Appendix B: Reproducing the Notebooks, Figures and This Report"),
    ("p", "All analysis and figures in this report can be regenerated from the backend repository:"),
    ("ol", ["`cd backend && pip install -r requirements-dev.txt && pytest` (runs the 47 tests).",
            "`ARACARE_DATABASE_URL=sqlite:////tmp/aracare_ds.db python -m app.mock_data` (generates the six-week dataset).",
            "`ARACARE_DB=/tmp/aracare_ds.db python report/build/make_notebooks.py` (executes both notebooks and saves the charts).",
            "`python report/build/make_figures.py` (diagrams and code snippets), then `python report/build/build_report.py` (this document)."]),
    ("p", "The notebooks are `report/notebooks/aracare_patient_flow_analysis.ipynb` and "
          "`report/notebooks/beginner_data_science_projects.ipynb`; the datasets for the beginner projects are in "
          "`report/data/`, and the UI screenshots are in `pictures/`."),
]
