# Customer Prediction System

Django REST API plus an offline ML pipeline for synthetic customer transactions: predict **when** a customer is likely to purchase again at a given vendor, surface **deal-style windows**, and optionally generate short **GPT deal alerts**.

## Repository layout

| Path | Purpose |
|------|---------|
| `customer_prediction_system/` | Django project (`manage.py`, settings, `predictor` app) |
| `customer_prediction_system/predictor/data/dataset1.csv` | Feature-engineered export from `dataset.ipynb` |
| `customer_prediction_system/predictor/models/` | Trained artifacts: `timing_model.pkl`, `feature_list.pkl`, `bucket_boundaries.pkl` |
| `customer_prediction_system/predictor/pipeline.py` | Inference, cycle-aware windows, multi-vendor run, OpenAI messaging |
| `customer_prediction_system/dataset.ipynb` | Generate / engineer data and export CSV |
| `customer_prediction_system/notebooks/model_training.ipynb` | Train timing classifier and save artifacts under `predictor/models/` |

## Setup (API)

```bash
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

pip install -r requirements.txt

cd customer_prediction_system
python manage.py migrate

# Load CSV into SQLite (path is relative to repo root when resolving inside the command)
python manage.py load_data --file predictor/data/dataset1.csv

python manage.py runserver
```

## API (read-only)

| Endpoint | Description |
|----------|-------------|
| `GET /api/customers/` | List customers (search, ordering) |
| `GET /api/customers/{customer_id}/` | Customer details |
| `GET /api/customers/{customer_id}/transactions/` | Customer transactions (capped) |
| `GET /api/transactions/` | List transactions |
| `GET /api/transactions/{transaction_id}/` | Transaction details |

## Machine learning

- **Data:** `dataset.ipynb` builds a synthetic ledger, engineers features (gaps, rolling stats, vendor context, optional day/month pattern features), and exports **`predictor/data/dataset1.csv`**. Run **PIPELINE 1/4 → 4/4** in that notebook before relying on the full column set; cell `# 15` falls back to base features if pattern columns are not built yet.
- **Training:** `notebooks/model_training.ipynb` trains a **RandomForestClassifier** on quantile buckets of “days until next purchase at this vendor,” with cross-validation, and writes **`timing_model.pkl`**, **`feature_list.pkl`**, and **`bucket_boundaries.pkl`** into **`predictor/models/`**.
- **Inference script:** `predictor/pipeline.py` loads those artifacts and CSV, exposes **`predict_window()`** (ML bucket + window), **`detect_purchase_pattern()`** (gap-based cycle windows), **`run_for_all_vendors()`** (ranked recommendations), and **`generate_message()`** (optional GPT copy). Run from the Django app folder:

  ```bash
  cd customer_prediction_system
  python predictor/pipeline.py
  ```

  Set **`OPENAI_API_KEY`** in the environment for GPT message generation; if the API call fails, a short fallback message is used.

### Python dependencies for the pipeline (not in `requirements.txt` today)

The Django `requirements.txt` covers the API only. For notebooks and `pipeline.py`, install additionally, for example:

```bash
pip install pandas numpy scikit-learn joblib openai
```

## ML overview (concise)

- Target: **timing buckets** (soon / medium / later) derived from inter-purchase behavior at the **customer + vendor** level.
- Stored model outputs in this repo are **classification** (Random Forest), not the older regression stack mentioned in early drafts.
- The REST API exposes stored **`likelihood_prediction`** on transactions for downstream use; the standalone **`pipeline.py`** script uses the trained model file plus CSV for demos and messaging.
