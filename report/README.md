# SIWES IT Project Report: AraCare Health OS

Joseph Cosmos Aniebiet (22/SC/CO/1301), Department of Computer Science, University of Uyo.
SIWES placement: Acadeva Limited, May to October 2026.

| Path | What it is |
|---|---|
| `output/Joseph_Cosmos_Aniebiet_SIWES_IT_Project_Report.docx` | The report (Word, editable) |
| `output/Joseph_Cosmos_Aniebiet_SIWES_IT_Project_Report.pdf` | The same report as PDF |
| `notebooks/aracare_patient_flow_analysis.ipynb` | Data analysis of AraCare records (Chapter 3.10) |
| `notebooks/beginner_data_science_projects.ipynb` | Titanic, House Prices, Iris (Chapter 2.8) |
| `figures/`, `snippets/` | Charts, diagrams and code images used in the report |
| `build/` | Scripts that regenerate everything |

Rebuild (from the repository root):

```bash
pip install -r backend/requirements-dev.txt python-docx pdfplumber nbformat nbconvert ipykernel seaborn scikit-learn pygments
cd backend && ARACARE_DATABASE_URL=sqlite:////tmp/aracare_ds.db python -m app.mock_data && cd ..
ARACARE_DB=/tmp/aracare_ds.db python report/build/make_notebooks.py
python report/build/make_figures.py
python report/build/build_report.py   # needs LibreOffice Writer for page numbers + PDF
```

The report text lives in `build/content.py`; edit it there and rebuild so the table of contents and
figure numbers stay correct. If you edit the .docx directly instead, update the table of contents by hand.
