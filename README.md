# Customer Prediction System

Django REST API plus a Next.js dashboard, with an offline ML pipeline for synthetic customer transactions: predict **when** a customer is likely to purchase again at a given vendor, surface **deal-style windows**, attach **mock-matched offers** (with alternates), and optionally generate short **GPT deal alerts**.

## Repository layout

| Path | Purpose |
|------|---------|
| `customer_prediction_system/` | Django project (`manage.py`, settings, `predictor` app) |
| `customer_prediction_system/predictor/generate_dataset1.py` | Deterministic synthetic CSV: 150 customers × 150 transactions (22,500 rows), single write to `predictor/data/dataset1.csv` |
| `customer_prediction_system/predictor/data/dataset1.csv` | Feature-engineered transactions (regenerate with the script or `dataset.ipynb`) |
| `customer_prediction_system/predictor/models/` | Trained artifacts: `timing_model.pkl`, `feature_list.pkl`, `bucket_boundaries.pkl` |
| `customer_prediction_system/predictor/pipeline.py` | Inference, cycle-aware windows, mock offer matching (`services.offer_fetcher`), multi-vendor run, OpenAI messaging |
| `customer_prediction_system/dataset.ipynb` | Alternative path to build / engineer data and export CSV |
| `customer_prediction_system/notebooks/model_training.ipynb` | Train timing classifier and save artifacts under `predictor/models/` |
| `services/` | Mock offer catalog (`mock_offers.json`) and `offer_fetcher.py`: load JSON, filter/rank offers, `match_best_offer`, `match_top_offers` |
| `customer-recommendation-frontend/` | Next.js app: login (JWT), dashboard with primary deal + alternate offers when the API returns them |
| `requirements.txt` | Python dependencies (Django, DRF, JWT, CORS, **PostgreSQL** via `psycopg`, **Faker** for dataset generation) |
| `Dockerfile` (repo root) | Django backend image: `runserver` on **8001** inside the container |
| `docker-compose.yml` | **postgres** + **backend** + **frontend** (one command full stack) |
| `customer-recommendation-frontend/Dockerfile` | Next.js production image: app listens on **3001** inside the container |

## Prerequisites

- **Python 3.11+** (3.13 works with the pinned stack)
- **PostgreSQL** running locally (or reachable via `POSTGRES_*` env vars)
- **Node.js** for the frontend

## Backend (Django + PostgreSQL)

### 1. Virtual environment and dependencies

```bash
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

pip install -r requirements.txt
```

### 2. Database configuration

The API uses **PostgreSQL** (sessions, auth, JWT blacklist, and `predictor` models). Copy env template and adjust if needed:

```bash
cp customer_prediction_system/.env.example customer_prediction_system/.env
# Export variables, or use a tool that loads .env before manage.py
```

- **macOS (Homebrew Postgres):** the default superuser is usually your **macOS login name**, not `postgres`. If `POSTGRES_USER` is **unset**, settings default the DB user from `USER` / `USERNAME` and use an empty password when `POSTGRES_PASSWORD` is unset (typical local **trust** setups).
- **Docker / Linux** with a `postgres` role: set `POSTGRES_USER=postgres` and `POSTGRES_PASSWORD` explicitly.

Create the database if it does not exist:

```bash
createdb customer_prediction   # often works as your OS user on macOS
```

### 3. Migrations and data

Always run Django commands from the folder that contains **`manage.py`**:

```bash
cd customer_prediction_system

python manage.py migrate

# Paths for --file are resolved relative to this directory (e.g. predictor/data/...)
python manage.py load_data --file predictor/data/dataset1.csv
```

Regenerate the synthetic dataset (deterministic names/IDs, 22,500 rows, Faker + UUID v5):

```bash
cd customer_prediction_system
python predictor/generate_dataset1.py
```

Then reload with `load_data` if you want the DB to match the new file.

### 4. Customer login users (optional)

To create a Django `User` + `UserProfile` linked to each `Customer` (for JWT login and `/api/recommendations/me/`):

```bash
export DEFAULT_CUSTOMER_PASSWORD='1234'
python manage.py sync_customer_accounts
```

Or pass the password once (same effect):

```bash
python manage.py sync_customer_accounts --password '1234'
```

**Usernames and passwords (demo defaults)**

- **Password:** Use **`1234`** with the commands above (or any value you prefer via `--password`). Passwords are stored hashed in the database.
- **Username:** Each login username matches the customer’s **`first_name`** and **`last_name`** from `predictor/data/dataset1.csv`: lowercase letters only, concatenated with no space—e.g. first row **Whitney** + **Hicks** → **`whitneyhicks`**. If two customers would collide, `sync_customer_accounts` appends `2`, `3`, … (see command output lines like `[created] username=…`).

Example demo login: **`whitneyhicks`** / **`1234`** (after `load_data` + `sync_customer_accounts`). Do not use **`1234`** in production.

You must run **`load_data`** (or otherwise have `Customer` rows) **before** `sync_customer_accounts`, or there will be no customer-linked users to create.

### 5. Run the API

```bash
cd customer_prediction_system
python manage.py runserver
```

Default: **http://127.0.0.1:8000/** (local `runserver`; Docker maps the API on **8001**—see below).

**Note:** Do not run `manage.py` from `customer-recommendation-frontend/` or from `~` without paths—use `cd customer_prediction_system` or pass the full path to `manage.py`.

## Docker (full stack)

From the **repository root** (where `docker-compose.yml` lives):

```bash
docker compose up --build
```

**Services and host ports**

| Service | Host port | Notes |
|---------|-----------|--------|
| PostgreSQL | **5432** | DB `customer_prediction`, user/password `postgres` / `postgres` (as defined in `docker-compose.yml`) |
| Backend (Django) | **8001** | `POSTGRES_HOST` is the `postgres` service name on the compose network |
| Frontend (Next.js) | **3003** | Mapped to container port **3001**; UI at **http://localhost:3003** |

The frontend image is built with **`NEXT_PUBLIC_API_URL=http://localhost:8001`** so the **browser** calls the API on the host (same machine as the dashboard).

**First-time database setup** (after containers are up, migrations applied):

```bash
docker compose exec backend python manage.py migrate
docker compose exec backend python manage.py load_data --file predictor/data/dataset1.csv
docker compose exec backend python manage.py sync_customer_accounts --password '1234'
```

Log in at **http://localhost:3003/login** with **`whitneyhicks`** / **`1234`** (first customer in `dataset1.csv`: Whitney Hicks), or another username from the `sync_customer_accounts` output.

Individual images can also be built with `docker build` using the `Dockerfile` files at the repo root and under `customer-recommendation-frontend/`; Compose is the intended way to run everything together.

## Frontend (Next.js)

```bash
cd customer-recommendation-frontend
npm install
```

Create **`.env.local`** in that folder so the browser calls the Django API reliably (avoids `localhost` vs `127.0.0.1` mismatches):

```env
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
```

If the API runs in Docker on port **8001**, use **`http://127.0.0.1:8001`** (or the URL from `docker compose` / `NEXT_PUBLIC_API_URL` in the frontend build).

Start the dev server (use another port if **3000** is taken—e.g. by Grafana—or **3001** is in use):

```bash
npm run dev -- -p 3002
```

Open **http://localhost:3002/login** (or whatever port you chose). Restart `npm run dev` after changing `.env.local`.

## API overview

| Area | Endpoint | Description |
|------|----------|-------------|
| Auth | `POST /api/auth/login/` | JWT obtain pair (username / password) |
| Auth | `POST /api/auth/refresh/` | Refresh access token |
| Auth | `POST /api/auth/logout/` | Blacklist refresh token |
| Data | `GET /api/customers/` | List customers (search, ordering) |
| Data | `GET /api/customers/{customer_id}/` | Customer details |
| Data | `GET /api/customers/{customer_id}/transactions/` | Customer transactions (capped) |
| Data | `GET /api/transactions/` | List transactions |
| Data | `GET /api/transactions/{transaction_id}/` | Transaction details |
| Scoped | `GET /api/recommendations/me/` | Recommendations for the customer linked to the JWT user’s `UserProfile` |

`UserProfile` ties a Django user to a `Customer`. When creating profiles in the shell, use **`UserProfile.get_or_create_for_user(user, customer)`** or `get_or_create(user=..., defaults={"customer": customer})` so `customer_id` is never null on insert.

### Recommendations payload (offers)

`GET /api/recommendations/me/` returns JSON built by `predictor.pipeline.get_recommendations_for_customer`. Each item includes:

- **Primary deal (backward compatible):** `vendor`, `recommended_title`, `deal_price`, `offer_url`, `valid_until`, `offer_category`, `score`, `bucket`, `confidence`, `pattern`, nested `offer`, and `message`.
- **`alternate_offers`:** up to **three** ranked mock offers (`vendor`, `price`, `category`, `title`, `url`, `valid_until`) when the transaction vendor maps to the mock catalog (e.g. Walmart, Amazon, major US airlines → `Airlines`). Vendors without catalog coverage still get synthetic pricing and an empty `alternate_offers` list.

The Django app adds the repo root to `sys.path` so `from services.offer_fetcher import …` resolves next to this repository.

### Mock offers (data + CLI)

- Edit **`services/mock_offers.json`** to add or change deals (invalid JSON or a missing file yields an empty catalog at runtime).
- Quick check from the repo root:

  ```bash
  python services/offer_fetcher.py
  ```

Root URL **`/`** returns a small JSON map of these endpoints.

## Machine learning

- **Data:** `predictor/generate_dataset1.py` or **`dataset.ipynb`** can drive the ledger and feature columns; the script mirrors notebook-style engineering and keeps **22,500** rows (no dropna-driven row loss). Run **PIPELINE 1/4 → 4/4** in the notebook if you rely on that path; cell `# 15` can fall back to base features if pattern columns are missing.
- **Training:** `notebooks/model_training.ipynb` trains a **RandomForestClassifier** on quantile buckets of “days until next purchase at this vendor,” with cross-validation, and writes **`timing_model.pkl`**, **`feature_list.pkl`**, and **`bucket_boundaries.pkl`** into **`predictor/models/`**.
- **Inference script:** `predictor/pipeline.py` loads those artifacts and CSV, exposes **`predict_window()`**, **`detect_purchase_pattern()`**, **`run_for_all_vendors()`**, and **`generate_message()`** (optional GPT). From the Django app folder:

  ```bash
  cd customer_prediction_system
  python predictor/pipeline.py
  ```

  Set **`OPENAI_API_KEY`** for GPT copy; on failure, a short fallback message is used.

### Extra Python packages for notebooks / pipeline

`requirements.txt` covers the API and dataset script. For notebooks and `pipeline.py` you may also need:

```bash
pip install pandas numpy scikit-learn joblib openai
```

## ML overview (concise)

- **Target:** timing buckets (soon / medium / later) from inter-purchase behavior at the **customer + vendor** level.
- **Stored models** are **classification** (Random Forest), not an older regression-only stack.
- The REST API exposes **`likelihood_prediction`** on transactions; **`pipeline.py`** uses the pickle artifacts plus CSV for demos and messaging.
