# Customer Prediction System

Django REST API for customer transaction data with likelihood predictions.

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

# Load data from CSV (uses predictor/data/dataset.csv by default)
python manage.py load_data

# Create superuser for admin (optional)
python manage.py createsuperuser

# Start server
python manage.py runserver
```

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /` | API info and endpoint list |
| `GET /api/customers/` | List customers (search, ordering) |
| `GET /api/customers/{customer_id}/` | Get customer details |
| `GET /api/customers/{customer_id}/transactions/` | Get customer's transactions |
| `GET /api/transactions/` | List transactions (search, ordering) |
| `GET /api/transactions/{transaction_id}/` | Get transaction details |
| `GET /admin/` | Django admin |

## Project Structure

```
Customer Prediction System/
├── customer_prediction_system/   # Django project
│   ├── predictor/                # App (models, views, serializers)
│   └── manage.py
├── predictor/data/
│   └── dataset.csv              # Transaction data
└── requirements.txt
```
