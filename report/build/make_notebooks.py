"""Builds and executes the two analysis notebooks used in the SIWES report.

    python report/build/make_notebooks.py

1. notebooks/aracare_patient_flow_analysis.ipynb  - data analysis of AraCare Health OS records
2. notebooks/beginner_data_science_projects.ipynb - Titanic, House Prices, Iris

Every chart is also written to report/figures/ so the report builder can embed it.
The AraCare notebook reads the SQLite database produced by `python -m app.mock_data`
(path in ARACARE_DB, default /tmp/claude-0/aracare_ds.db).
"""
import os
from pathlib import Path

import nbformat
from nbconvert.preprocessors import ExecutePreprocessor

ROOT = Path(__file__).resolve().parents[1]
NB = ROOT / "notebooks"

STYLE = r'''
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
FIG = Path("../figures"); FIG.mkdir(exist_ok=True)
NAVY, BLUE, TEAL, AMBER, RED, GREY = "#0B2A6F", "#1F5FD6", "#14A38B", "#E8A33D", "#D64545", "#8A94A6"
PALETTE = [NAVY, BLUE, TEAL, AMBER, RED, "#7B61FF", GREY]
sns.set_theme(style="whitegrid", palette=PALETTE, font="DejaVu Sans")
plt.rcParams.update({"figure.dpi": 110, "savefig.dpi": 200, "axes.titleweight": "bold",
                     "axes.titlesize": 13, "axes.labelsize": 11, "axes.spines.top": False,
                     "axes.spines.right": False})
def save(name):
    plt.tight_layout()
    plt.savefig(FIG / f"{name}.png", bbox_inches="tight", facecolor="white")
    plt.show()
'''


def md(s):
    return nbformat.v4.new_markdown_cell(s.strip())


def code(s):
    return nbformat.v4.new_code_cell(s.strip())


# --------------------------------------------------------------------------- AraCare analysis
aracare = [
    md("""
# AraCare Health OS: Patient Flow and Clinical Data Analysis
**Author:** Joseph Cosmos Aniebiet (22/SC/CO/1301)

This notebook analyses six weeks of outpatient records from AraCare Health OS (General Hospital Ikeja
demo facility, generated with `python -m app.mock_data --seed 2026`, which follows the same rules as the live
code: ticket numbering, journey cascade, triage flags and allergy checks). The goal is to answer questions a
hospital manager would ask:

1. Who are our patients?
2. When do they arrive, and how busy are we each day?
3. How long do patients wait, and does the priority system work?
4. What conditions do we treat most?
5. How is the AI voice scribe being used?
"""),
    code(STYLE),
    code(r'''
import os, json, sqlite3
import numpy as np
import pandas as pd
DB = os.environ.get("ARACARE_DB", "/tmp/claude-0/aracare_ds.db")
con = sqlite3.connect(DB)
tables = pd.read_sql("select name from sqlite_master where type='table'", con)["name"]
pd.DataFrame({"table": tables, "rows": [pd.read_sql(f"select count(*) n from {t}", con).n[0] for t in tables]}) \
  .sort_values("rows", ascending=False).reset_index(drop=True)
'''),
    md("## 1. Loading and cleaning the data\nTimestamps are stored as naive UTC; Lagos is UTC+1, so every time column is shifted to local time."),
    code(r'''
LOCAL = pd.Timedelta(hours=1)
def times(df, cols):
    for c in cols:
        df[c] = pd.to_datetime(df[c], format="mixed") + LOCAL
    return df

patients = pd.read_sql("select * from patients", con)
visits   = times(pd.read_sql("select * from visits", con), ["checked_in_at"])
tickets  = times(pd.read_sql("select * from queue_tickets", con),
                 ["issued_at", "entered_waiting_at", "called_at", "confirmed_at", "completed_at"])
vitals   = pd.read_sql("select * from vitals", con)
diag     = pd.read_sql("select * from diagnoses where diagnosis_type='primary'", con)
notes    = pd.read_sql("select * from clinical_notes", con)
scribe   = pd.read_sql("select * from scribe_sessions", con)

today = visits.checked_in_at.max().normalize()
patients["dob"] = pd.to_datetime(patients.date_of_birth)
patients["age"] = ((today - patients.dob).dt.days / 365.25).astype(int)
print("patients:", len(patients), "| visits:", len(visits), "| tickets:", len(tickets))
print("period:", visits.checked_in_at.min().date(), "to", visits.checked_in_at.max().date())
print("missing values in vitals:\n", vitals[["bp_systolic","pulse_rate","temperature","spo2","weight_kg"]].isna().sum())
'''),
    md("## 2. Who are our patients?"),
    code(r'''
fig, ax = plt.subplots(1, 2, figsize=(12, 4.2), gridspec_kw={"width_ratios": [2, 1]})
bins = [0, 5, 12, 18, 30, 45, 60, 75, 100]
labels = ["0-4", "5-11", "12-17", "18-29", "30-44", "45-59", "60-74", "75+"]
patients["age_band"] = pd.cut(patients.age, bins=bins, labels=labels, right=False)
ct = patients.groupby(["age_band", "gender"], observed=False).size().unstack()
ct.plot(kind="bar", ax=ax[0], color=[RED, BLUE], width=0.8)
ax[0].set(title="Registered patients by age band and sex", xlabel="Age band (years)", ylabel="Patients")
ax[0].tick_params(axis="x", rotation=0); ax[0].legend(title="")
pay = visits.payment_track.str.replace("_", " ").str.title().value_counts(normalize=True).mul(100).sort_values()
ax[1].barh(pay.index, pay.values, color=[GREY, GREY, GREY, GREY, BLUE, NAVY][-len(pay):])
for i, val in enumerate(pay.values):
    ax[1].text(val + 1, i, f"{val:.0f}%", va="center", fontsize=9)
ax[1].set_xlim(0, 85)
ax[1].set(title="Visits by payment track", xlabel="% of visits")
save("ac_demographics")
patients.age.describe().round(1)
'''),
    md("""
**Finding.** The largest group is women aged 30 to 44 (antenatal care and the usual pattern of
health-seeking behaviour), and about one in four registered patients is a child. Roughly two thirds of visits
are paid out of pocket and most of the rest through an HMO, so the billing module that comes next must handle
cash and HMO claims equally well.
"""),
    md("## 3. When do patients arrive?"),
    code(r'''
visits["day"] = visits.checked_in_at.dt.normalize()
visits["hour"] = visits.checked_in_at.dt.hour
visits["weekday"] = visits.checked_in_at.dt.day_name()
fig, ax = plt.subplots(1, 2, figsize=(12, 4.2))
by_hour = visits.groupby("hour").size()
ax[0].bar(by_hour.index, by_hour.values, color=[RED if h in (8, 9, 10) else BLUE for h in by_hour.index])
ax[0].set(title="Check-ins by hour of day", xlabel="Hour (local time)", ylabel="Visits")
order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
per_day = visits.groupby(["day", "weekday"]).size().reset_index(name="n")
sns.boxplot(data=per_day, x="weekday", y="n", order=[d for d in order if d in set(per_day.weekday)],
            ax=ax[1], color=TEAL, width=0.55, fliersize=3)
ax[1].set(title="Visits per day, by weekday", xlabel="", ylabel="Visits per day")
ax[1].tick_params(axis="x", rotation=30)
save("ac_arrivals")
by_hour.idxmax(), round(by_hour.loc[8:10].sum() / by_hour.sum() * 100, 1)
'''),
    code(r'''
daily = visits.groupby("day").size()
fig, ax = plt.subplots(figsize=(12, 3.8))
ax.plot(daily.index, daily.values, marker="o", ms=3.5, color=BLUE, lw=1.5, label="Visits per day")
ax.plot(daily.index, daily.rolling(7, min_periods=1).mean(), color=RED, lw=2.4, label="7-day average")
ax.set(title="Daily outpatient volume over six weeks", ylabel="Visits", xlabel="")
ax.legend(frameon=False)
save("ac_daily_volume")
daily.describe().round(1)
'''),
    md("""
**Finding.** Arrivals peak between 08:00 and 11:00 (about 42% of all check-ins, highest at 09:00), which is
exactly the morning crush described in the queue-engine design. Monday is the busiest day (around 30 visits),
weekdays settle at 20 to 25, and weekends are quiet. The 7-day average is flat at about 20 visits a day, so the
pattern is a weekly cycle, not growth. Staffing an extra triage bay on weekday mornings, and especially on
Mondays, would cut the longest waits.
"""),
    md("## 4. How long do patients wait, and does prioritisation work?"),
    code(r'''
t = tickets[tickets.status == "completed"].copy()
t["wait_min"] = (t.called_at - t.entered_waiting_at).dt.total_seconds() / 60
t["service_min"] = (t.completed_at - t.confirmed_at).dt.total_seconds() / 60
t["dept"] = t.department.map({"TRIAGE": "Triage (nurse)", "OPD-GEN": "Doctor (OPD)"})
tiers = ["EMERGENCY", "HIGH", "NORMAL"]
t = t[t.priority_tier.isin(tiers)]
fig, ax = plt.subplots(figsize=(11, 4.4))
sns.boxplot(data=t, x="priority_tier", y="wait_min", hue="dept", order=tiers,
            palette=[TEAL, NAVY], ax=ax, fliersize=2, width=0.6)
ax.set(title="Waiting time by priority tier", xlabel="Priority tier", ylabel="Minutes waited before being called")
ax.legend(title="", frameon=False)
save("ac_wait_by_priority")
t.groupby(["dept", "priority_tier"]).wait_min.agg(["count", "median", "mean", "max"]).round(1)
'''),
    md("""
**Finding.** The doctor queue shows the priority system working: median wait is about 2 minutes for
EMERGENCY, 24 for HIGH and 57 for NORMAL. NORMAL patients are still served (none waited more than about 95
minutes), because weighted fair queuing lets a NORMAL patient through after a burst of HIGH ones and aging
promotes long waiters. In the triage queue the differences are smaller, because priority is only known after
the nurse has taken the vital signs: the tier shown there is the one the patient ended up with.
"""),
    code(r'''
# Total time in the clinic: from joining the triage queue to the end of the doctor's consultation
tri = t[t.department == "TRIAGE"].set_index("visit_id").entered_waiting_at
doc = t[t.department == "OPD-GEN"].set_index("visit_id")
doc = doc.assign(start=tri.reindex(doc.index)).dropna(subset=["start"])
doc["total_min"] = (doc.completed_at - doc.start).dt.total_seconds() / 60
fig, ax = plt.subplots(figsize=(10, 4.2))
for tier, c in zip(tiers, [RED, AMBER, BLUE]):
    sns.kdeplot(doc[doc.priority_tier == tier].total_min, ax=ax, color=c, fill=True, alpha=0.25, lw=2, label=tier, cut=0)
ax.set(title="Total time from arrival in the queue to end of consultation", xlabel="Minutes", ylabel="Density")
ax.legend(title="Doctor-queue priority", frameon=False)
save("ac_time_in_clinic")
doc.groupby("priority_tier").total_min.describe()[["count", "50%", "mean", "max"]].round(0)
'''),
    md('''
**Finding.** A typical NORMAL patient spends about two hours from joining the triage queue to leaving the
consulting room, a HIGH-priority patient noticeably less, and emergencies the least. Most of that time is
waiting, not care, which is why the receipt SMS and the TV display matter: the patient can wait outside and
come back when the number is close.
'''),
    md("## 5. Triage vital signs"),
    code(r'''
v = vitals.copy()
v["flag_list"] = v["flags"].apply(json.loads)
flag_counts = pd.Series([f["field"] for fl in v.flag_list for f in fl]).value_counts()
names = {"temperature": "Temperature", "bp": "Blood pressure", "bp_systolic": "BP (systolic)", "pulse_rate": "Pulse",
         "respiratory_rate": "Respiratory rate", "spo2": "Oxygen (SpO2)", "bmi": "BMI", "pain_score": "Pain score"}
fig, ax = plt.subplots(1, 2, figsize=(12, 4.4))
fc = flag_counts.rename(index=lambda s: names.get(s, s.replace("_", " ").title()))
ax[0].barh(fc.index[::-1], fc.values[::-1], color=AMBER)
ax[0].set(title="Abnormal-vital flags raised at triage", xlabel="Flags raised")
cols = ["bp_systolic", "bp_diastolic", "pulse_rate", "respiratory_rate", "temperature", "spo2", "bmi"]
corr = v[cols].corr()
sns.heatmap(corr, annot=True, fmt=".2f", cmap="RdBu_r", vmin=-1, vmax=1, ax=ax[1], cbar=False,
            xticklabels=["BP sys", "BP dia", "Pulse", "Resp", "Temp", "SpO2", "BMI"],
            yticklabels=["BP sys", "BP dia", "Pulse", "Resp", "Temp", "SpO2", "BMI"], annot_kws={"size": 8})
ax[1].set_title("Correlation between vital signs")
save("ac_vitals")
print("visits with at least one flag:", round((v.flag_list.str.len() > 0).mean() * 100, 1), "%")
'''),
    md("""
**Finding.** Three in four triaged patients had at least one abnormal vital sign, and fever is by far the
most common flag, consistent with a malaria-endemic setting. Pulse and respiratory rate move together
(r = 0.57), both fall as SpO2 rises, and systolic and diastolic pressure correlate as expected (r = 0.54).
Blood pressure is missing for about a quarter of records because it is not routinely taken for young
children; the analysis keeps those rows and ignores the gap only for the BP columns.
"""),
    md("## 6. What conditions do we treat?"),
    code(r'''
top = diag.icd10_description.value_counts().head(10)
codes = diag.drop_duplicates("icd10_description").set_index("icd10_description").icd10_code
labels = [f"{codes[d]}  {d[:48] + ('...' if len(d) > 48 else '')}" for d in top.index]
fig, ax = plt.subplots(figsize=(11, 4.8))
ax.barh(labels[::-1], top.values[::-1], color=[RED if "malaria" in d.lower() else NAVY for d in top.index[::-1]])
for i, val in enumerate(top.values[::-1]):
    ax.text(val + 1, i, str(val), va="center", fontsize=9)
ax.set(title="Top 10 primary diagnoses (ICD-10)", xlabel="Visits")
save("ac_top_diagnoses")
round(top.head(3) / len(diag) * 100, 1)
'''),
    md("## 7. AI voice scribe usage"),
    code(r'''
notes["signed_day"] = pd.to_datetime(notes.signed_at, format="mixed").dt.normalize()
weekly = notes.dropna(subset=["signed_day"]).groupby([pd.Grouper(key="signed_day", freq="W-MON"), "source"]).size().unstack(fill_value=0)
weekly.index = weekly.index.strftime("%d %b")
fig, ax = plt.subplots(1, 2, figsize=(12, 4.2), gridspec_kw={"width_ratios": [2, 1]})
weekly.rename(columns={"manual": "Typed", "ai_scribe": "Voice scribe"}).plot(kind="bar", stacked=True, ax=ax[0], color=[TEAL, NAVY][::-1])
ax[0].set(title="Signed clinical notes per week, by source", xlabel="Week ending", ylabel="Notes")
ax[0].tick_params(axis="x", rotation=0); ax[0].legend(frameon=False)
roles = scribe.role.str.title().value_counts()
ax[1].bar(roles.index, roles.values, color=[NAVY, TEAL])
ax[1].set(title="Scribe sessions by role", ylabel="Sessions")
save("ac_scribe_usage")
print("share of notes drafted by voice:", round((notes.source == "ai_scribe").mean() * 100, 1), "%")
print("scribe sessions accepted:", (scribe.status == "accepted").sum(), "of", len(scribe))
'''),
    md("""
## 8. Summary of findings

| Question | Answer from the data |
|---|---|
| Patients | Largest group is women 30 to 44; about 1 in 4 is a child; two thirds pay out of pocket |
| Arrivals | 42% of check-ins between 08:00 and 11:00; Mondays busiest; ~20 visits a day |
| Waiting | Doctor queue medians: EMERGENCY ~2 min, HIGH ~24 min, NORMAL ~57 min; no starvation |
| Time in clinic | Around two hours end to end for a NORMAL patient, mostly waiting |
| Clinical load | Malaria dominates; fever is the most common triage flag |
| Voice scribe | About 8% of notes, growing from week 1; used by nurses and doctors; every draft reviewed by a clinician |
"""),
]

# --------------------------------------------------------------------------- beginner projects
beginner = [
    md("""
# Three Beginner Data Science Projects
**Author:** Joseph Cosmos Aniebiet (22/SC/CO/1301)

1. **Titanic survival prediction** (binary classification)
2. **House price prediction** (regression, California Housing)
3. **Iris flower classification** (multi-class classification)

Each project follows the same workflow: define the question, load data, clean it, explore it, engineer
features, train a model, evaluate it, and communicate the result.
"""),
    code(STYLE),
    code(r'''
import numpy as np, pandas as pd
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.linear_model import LogisticRegression, LinearRegression
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.tree import DecisionTreeClassifier
from sklearn.neighbors import KNeighborsClassifier
from sklearn.metrics import (accuracy_score, classification_report, confusion_matrix,
                             mean_absolute_error, mean_squared_error, r2_score, ConfusionMatrixDisplay)
from sklearn.datasets import load_iris
'''),
    md("## Project 1: Titanic survival prediction\n**Question:** given a passenger's details, did they survive?"),
    code(r'''
titanic = pd.read_csv("../data/titanic.csv")
print(titanic.shape)
titanic.isna().sum()[lambda s: s > 0]
'''),
    code(r'''
df = titanic[["survived", "pclass", "sex", "age", "sibsp", "parch", "fare", "embarked"]].copy()
df["age"] = df.age.fillna(df.groupby(["pclass", "sex"]).age.transform("median"))   # impute by group
df["embarked"] = df.embarked.fillna(df.embarked.mode()[0])
df["family_size"] = df.sibsp + df.parch + 1                                           # feature engineering
df["is_child"] = (df.age < 13).astype(int)
df["sex"] = df.sex.map({"male": 0, "female": 1})
df = pd.get_dummies(df, columns=["embarked"], drop_first=True, dtype=int)
fig, ax = plt.subplots(1, 3, figsize=(13, 3.8))
sns.barplot(data=titanic, x="sex", y="survived", hue="sex", legend=False, ax=ax[0], palette=[BLUE, RED], errorbar=None)
ax[0].set(title="Survival rate by sex", ylabel="Survival rate", xlabel="")
sns.barplot(data=titanic, x="pclass", y="survived", hue="pclass", legend=False, ax=ax[1], palette=[NAVY, BLUE, TEAL], errorbar=None)
ax[1].set(title="Survival rate by class", ylabel="", xlabel="Passenger class")
sns.histplot(data=titanic, x="age", hue="alive", bins=30, ax=ax[2], palette=[RED, TEAL], multiple="stack")
ax[2].set(title="Age distribution by outcome", xlabel="Age")
save("bp_titanic_eda")
'''),
    code(r'''
X, y = df.drop(columns="survived"), df.survived
X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)
models = {"Logistic Regression": LogisticRegression(max_iter=1000),
          "Decision Tree": DecisionTreeClassifier(max_depth=4, random_state=42),
          "Random Forest": RandomForestClassifier(n_estimators=300, max_depth=6, random_state=42)}
rows = []
for name, m in models.items():
    m.fit(X_tr, y_tr)
    rows.append({"model": name, "test_accuracy": accuracy_score(y_te, m.predict(X_te)),
                 "cv_accuracy": cross_val_score(m, X, y, cv=5).mean()})
titanic_results = pd.DataFrame(rows).round(3)
best = models["Random Forest"]
fig, ax = plt.subplots(1, 2, figsize=(12, 4))
ConfusionMatrixDisplay.from_estimator(best, X_te, y_te, display_labels=["Died", "Survived"], cmap="Blues", ax=ax[0], colorbar=False)
ax[0].set_title("Random Forest confusion matrix"); ax[0].grid(False)
imp = pd.Series(best.feature_importances_, index=X.columns).sort_values()
ax[1].barh(imp.index, imp.values, color=NAVY); ax[1].set_title("Feature importance")
save("bp_titanic_model")
titanic_results
'''),
    md("## Project 2: House price prediction\n**Question:** what is the median house value of a district, given its characteristics?"),
    code(r'''
housing = pd.read_csv("../data/housing.csv")
print(housing.shape); print(housing.isna().sum()[lambda s: s > 0])
h = housing.copy()
h["total_bedrooms"] = h.total_bedrooms.fillna(h.total_bedrooms.median())
h["rooms_per_household"] = h.total_rooms / h.households
h["bedrooms_per_room"] = h.total_bedrooms / h.total_rooms
h["population_per_household"] = h.population / h.households
h = pd.get_dummies(h, columns=["ocean_proximity"], dtype=int)
fig, ax = plt.subplots(1, 2, figsize=(12, 4.3))
sc = ax[0].scatter(housing.longitude, housing.latitude, c=housing.median_house_value, s=housing.population / 200,
                   cmap="viridis", alpha=0.5)
plt.colorbar(sc, ax=ax[0], label="Median house value ($)")
ax[0].set(title="House value by location", xlabel="Longitude", ylabel="Latitude")
ax[1].scatter(housing.median_income, housing.median_house_value, s=4, alpha=0.2, color=BLUE)
ax[1].set(title="Income vs. house value", xlabel="Median income (tens of thousands $)", ylabel="Median house value ($)")
save("bp_housing_eda")
'''),
    code(r'''
X, y = h.drop(columns="median_house_value"), h.median_house_value
X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.2, random_state=42)
reg = {"Linear Regression": LinearRegression(),
       "Random Forest": RandomForestRegressor(n_estimators=150, n_jobs=-1, random_state=42)}
rows, preds = [], {}
for name, m in reg.items():
    m.fit(X_tr, y_tr); p = m.predict(X_te); preds[name] = p
    rows.append({"model": name, "MAE": mean_absolute_error(y_te, p),
                 "RMSE": mean_squared_error(y_te, p) ** 0.5, "R2": r2_score(y_te, p)})
housing_results = pd.DataFrame(rows).round(3)
fig, ax = plt.subplots(figsize=(7, 5))
ax.scatter(y_te, preds["Random Forest"], s=5, alpha=0.3, color=TEAL)
lim = [0, 520000]; ax.plot(lim, lim, color=RED, lw=2, label="Perfect prediction")
ax.set(xlim=lim, ylim=lim, title="Random Forest: predicted vs. actual", xlabel="Actual value ($)", ylabel="Predicted value ($)")
ax.legend(frameon=False)
save("bp_housing_model")
housing_results
'''),
    md("## Project 3: Iris flower classification\n**Question:** which of three iris species is a flower, from four measurements?"),
    code(r'''
iris = load_iris(as_frame=True)
idf = iris.frame.copy(); idf["species"] = idf.target.map(dict(enumerate(iris.target_names)))
g = sns.pairplot(idf.drop(columns="target"), hue="species", palette=[NAVY, TEAL, AMBER], height=2.0,
                 plot_kws={"s": 18, "alpha": 0.8})
g.figure.suptitle("Iris measurements by species", y=1.02, fontweight="bold")
g.savefig(FIG / "bp_iris_eda.png", dpi=170, bbox_inches="tight", facecolor="white")
'''),
    code(r'''
X, y = iris.data, iris.target
X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.3, random_state=42, stratify=y)
knn = {k: accuracy_score(y_te, KNeighborsClassifier(n_neighbors=k).fit(X_tr, y_tr).predict(X_te)) for k in range(1, 21)}
best_k = max(knn, key=knn.get)
model = KNeighborsClassifier(n_neighbors=best_k).fit(X_tr, y_tr)
fig, ax = plt.subplots(1, 2, figsize=(12, 4))
ax[0].plot(list(knn), list(knn.values()), marker="o", color=NAVY); ax[0].axvline(best_k, color=RED, ls="--")
ax[0].set(title="Choosing k for K-Nearest Neighbours", xlabel="k (neighbours)", ylabel="Test accuracy")
ConfusionMatrixDisplay.from_estimator(model, X_te, y_te, display_labels=iris.target_names, cmap="Greens", ax=ax[1], colorbar=False)
ax[1].set_title(f"KNN (k = {best_k}) confusion matrix"); ax[1].grid(False)
save("bp_iris_model")
print("best k:", best_k, "accuracy:", round(knn[best_k], 3))
print(classification_report(y_te, model.predict(X_te), target_names=iris.target_names))
'''),
    code(r'''
import json
summary = {"titanic": titanic_results.to_dict("records"), "housing": housing_results.to_dict("records"),
           "iris": {"best_k": int(best_k), "accuracy": round(float(knn[best_k]), 3)}}
json.dump(summary, open(FIG / "beginner_results.json", "w"), indent=2)
summary
'''),
]


def run(cells, name):
    nb = nbformat.v4.new_notebook(cells=cells)
    nb.metadata["kernelspec"] = {"name": "python3", "display_name": "Python 3", "language": "python"}
    ExecutePreprocessor(timeout=900, kernel_name="python3").preprocess(nb, {"metadata": {"path": str(NB)}})
    nbformat.write(nb, NB / name)
    print("wrote", NB / name)


if __name__ == "__main__":
    NB.mkdir(exist_ok=True)
    run(aracare, "aracare_patient_flow_analysis.ipynb")
    run(beginner, "beginner_data_science_projects.ipynb")
