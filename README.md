# Customer Prediction System

Minimal Django REST API and ML pipeline for a synthetic customer transaction prediction system.

## Setup

```bash
# Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Navigate to Django project
cd customer_prediction_system

# Run migrations
python manage.py migrate

# Load synthetic transaction data (generated in `dataset.ipynb`)
python manage.py load_data --file customer_prediction_system/predictor/data/dataset1.csv

# Start server
python manage.py runserver
```

## API (read‑only)

| Endpoint | Description |
|----------|-------------|
| `GET /api/customers/` | List customers (search, ordering) |
| `GET /api/customers/{customer_id}/` | Get customer details |
| `GET /api/customers/{customer_id}/transactions/` | Get customer's transactions |
| `GET /api/transactions/` | List transactions (search, ordering) |
| `GET /api/transactions/{transaction_id}/` | Get transaction details |

## ML Overview (Phase 3)

- Synthetic behavioral dataset generated in `dataset.ipynb` with `likelihood_prediction` (days until next transaction).
- Regression models (Linear Regression, RandomForestRegressor, XGBRegressor) and classification models (RandomForestClassifier, XGBClassifier) trained in `notebooks/model_training.ipynb`.
- Predictions stored in the `likelihood_prediction` field on `Transaction` and exposed via the API for downstream use.
