#!/usr/bin/env python3
"""
Generate synthetic transaction data: 150 customers × 150 transactions = 22,500 rows.

- Nested loops only (no random truncation, sampling, or break that skips rows).
- Deterministic: fixed seeds for Faker and ``random``; stable UUID v5 IDs (no uuid4).
- Dates strictly increasing per customer; file is written once at the end.
- Feature engineering matches dataset.ipynb PIPELINE 2/4, but NaNs are filled
  instead of dropping rows so the row count stays 22,500.

Run from the Django project directory (where manage.py lives):
    python predictor/generate_dataset1.py
"""

from __future__ import annotations

import random
import uuid
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
from faker import Faker

# --- Configuration ---
NUM_CUSTOMERS = 150
TRANSACTIONS_PER_CUSTOMER = 150
EXPECTED_ROWS = NUM_CUSTOMERS * TRANSACTIONS_PER_CUSTOMER

START_DATE = datetime(2024, 1, 1, 0, 0, 0)
# Span through late 2025 (~729 days) for evenly spaced transaction dates
DATE_SPAN_DAYS = 729

VENDORS = [
    "Walmart",
    "Amazon",
    "Costco",
    "Starbucks",
    "American Airlines",
    "United Airlines",
    "CVS Pharmacy",
    "Delta Airlines",
    "Subway",
    "Chick-Fil-A",
    "Chipotle",
    "Panera Bread",
    "Macdonalds",
]

VENDOR_GROUPS = {
    0: ["American Airlines", "Walmart"],
    1: ["Delta Airlines", "Costco"],
    2: ["United Airlines", "Amazon"],
    3: ["American Airlines", "Costco"],
    4: ["Walmart", "Delta Airlines"],
}

RNG_SEED = 42

# Stable namespace for UUID v5 (same inputs → same UUIDs across runs and Python versions).
DATASET_UUID_NAMESPACE = uuid.uuid5(
    uuid.NAMESPACE_DNS, "customer-prediction-system.dataset1.v1"
)


def deterministic_customer_id(cust_idx: int) -> str:
    return str(uuid.uuid5(DATASET_UUID_NAMESPACE, f"customer:{cust_idx:04d}"))


def deterministic_transaction_id(cust_idx: int, txn_idx: int) -> str:
    return str(uuid.uuid5(DATASET_UUID_NAMESPACE, f"txn:{cust_idx:04d}:{txn_idx:04d}"))


def _transaction_amount(vendor: str, rng: random.Random) -> float:
    if vendor in ("American Airlines", "United Airlines", "Delta Airlines"):
        return round(rng.uniform(100.0, 500.0), 2)
    if vendor in ("Walmart", "Costco", "Amazon"):
        return round(rng.uniform(50.0, 500.0), 2)
    if vendor in (
        "Starbucks",
        "Chipotle",
        "Panera Bread",
        "Subway",
        "Chick-Fil-A",
        "Macdonalds",
    ):
        return round(rng.uniform(5.0, 100.0), 2)
    if vendor == "CVS Pharmacy":
        return round(rng.uniform(10.0, 100.0), 2)
    return round(rng.uniform(80.0, 500.0), 2)


def build_raw_transactions() -> tuple[list[list], list[tuple[str, str, str]]]:
    """Outer: customers; inner: transactions. Exactly EXPECTED_ROWS appends."""
    Faker.seed(RNG_SEED)
    random.seed(RNG_SEED)
    fake = Faker()
    rng = random.Random(RNG_SEED)

    rows: list[list] = []
    first_ten_customers: list[tuple[str, str, str]] = []

    for cust_idx in range(NUM_CUSTOMERS):
        first_name = fake.first_name()
        last_name = fake.last_name()
        customer_id = deterministic_customer_id(cust_idx)
        if cust_idx < 10:
            first_ten_customers.append((first_name, last_name, customer_id))

        primary = VENDOR_GROUPS[cust_idx // 30]
        secondary = [v for v in VENDORS if v not in primary]
        all_vendors = primary + secondary

        for txn_idx in range(TRANSACTIONS_PER_CUSTOMER):
            # Strictly increasing calendar dates per customer (no truncation).
            if TRANSACTIONS_PER_CUSTOMER > 1:
                day_offset = int(DATE_SPAN_DAYS * txn_idx / (TRANSACTIONS_PER_CUSTOMER - 1))
            else:
                day_offset = 0
            transaction_datetime = START_DATE + timedelta(days=day_offset)

            vendor = rng.choice(all_vendors)
            amount = _transaction_amount(vendor, rng)
            transaction_type = rng.choice(["Debit", "Credit"])
            transaction_id = deterministic_transaction_id(cust_idx, txn_idx)

            rows.append(
                [
                    first_name,
                    last_name,
                    customer_id,
                    transaction_id,
                    transaction_datetime,
                    amount,
                    vendor,
                    transaction_type,
                ]
            )

    assert len(rows) == EXPECTED_ROWS
    return rows, first_ten_customers


def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    """Align with dataset.ipynb PIPELINE 2/4; keep all rows (fill NaNs instead of drop)."""
    df = df.copy()
    df["transaction_datetime"] = pd.to_datetime(df["transaction_datetime"])
    df = df.sort_values(["customer_id", "transaction_datetime"]).reset_index(drop=True)

    df["next_transaction_date"] = df.groupby("customer_id")["transaction_datetime"].shift(-1)
    df["likelihood_prediction"] = (
        df["next_transaction_date"] - df["transaction_datetime"]
    ).dt.days
    df["likelihood_prediction"] = df["likelihood_prediction"].fillna(0)

    df["customer_transaction_count"] = df.groupby("customer_id")["transaction_id"].transform(
        "count"
    )
    df["customer_vendor_txn_count"] = df.groupby(["customer_id", "vendor"])[
        "transaction_id"
    ].transform("count")

    df["days_since_first_purchase"] = (
        df["transaction_datetime"]
        - df.groupby("customer_id")["transaction_datetime"].transform("min")
    ).dt.days

    df["transaction_month"] = df["transaction_datetime"].dt.month
    df["transaction_weekday"] = df["transaction_datetime"].dt.weekday

    df["customer_avg_spend"] = df.groupby("customer_id")["amount"].transform("mean")
    df["customer_avg_gap"] = df.groupby("customer_id")["likelihood_prediction"].transform("mean")

    df["days_since_last_transaction"] = (
        df["transaction_datetime"]
        - df.groupby("customer_id")["transaction_datetime"].shift(1)
    ).dt.days

    df["lag_1_gap"] = df.groupby("customer_id")["likelihood_prediction"].shift(1)
    df["lag_2_gap"] = df.groupby("customer_id")["likelihood_prediction"].shift(2)
    df["lag_3_gap"] = df.groupby("customer_id")["likelihood_prediction"].shift(3)

    df["rolling_avg_gap_7"] = df.groupby("customer_id")["likelihood_prediction"].transform(
        lambda x: x.shift(1).rolling(7, min_periods=2).mean()
    )
    df["rolling_avg_gap_3"] = df.groupby("customer_id")["likelihood_prediction"].transform(
        lambda x: x.shift(1).rolling(3, min_periods=2).mean()
    )
    df["rolling_avg_gap_14"] = df.groupby("customer_id")["likelihood_prediction"].transform(
        lambda x: x.shift(1).rolling(14, min_periods=5).mean()
    )

    df["gap_trend_short"] = df["rolling_avg_gap_3"] - df["rolling_avg_gap_7"]
    df["gap_trend_long"] = df["rolling_avg_gap_7"] - df["rolling_avg_gap_14"]

    df["rolling_spend_3"] = df.groupby("customer_id")["amount"].transform(
        lambda x: x.shift(1).rolling(3, min_periods=2).mean()
    )
    df["rolling_spend_7"] = df.groupby("customer_id")["amount"].transform(
        lambda x: x.shift(1).rolling(7, min_periods=3).mean()
    )
    df["spend_trend"] = df["rolling_spend_3"] - df["rolling_spend_7"]

    vendor_avg_gap = df.groupby(["customer_id", "vendor"])["likelihood_prediction"].transform(
        "mean"
    )
    df["vendor_gap_vs_avg"] = vendor_avg_gap - df["customer_avg_gap"]

    vendor_avg_spend = df.groupby(["customer_id", "vendor"])["amount"].transform("mean")
    df["vendor_spend_vs_avg"] = vendor_avg_spend - df["customer_avg_spend"]

    vendor_category_map = {
        "American Airlines": "airline",
        "Delta Airlines": "airline",
        "United Airlines": "airline",
        "Walmart": "retail",
        "Amazon": "retail",
        "Costco": "retail",
        "Starbucks": "food",
        "Chipotle": "food",
        "Subway": "food",
        "Chick-Fil-A": "food",
        "Panera Bread": "food",
        "Macdonalds": "food",
        "CVS Pharmacy": "pharmacy",
    }
    cat_map = {"food": 0, "pharmacy": 1, "retail": 2, "airline": 3, "other": 4}
    df["vendor_category"] = df["vendor"].map(vendor_category_map).fillna("other")
    df["vendor_category_code"] = df["vendor_category"].map(cat_map)

    df["transaction_day"] = df["transaction_datetime"].dt.day
    df["vendor_preferred_day"] = (
        df.groupby(["customer_id", "vendor"])["transaction_day"].transform("mean").round(0)
    )
    df["vendor_day_std"] = (
        df.groupby(["customer_id", "vendor"])["transaction_day"].transform("std").fillna(0)
    )
    df["vendor_preferred_month"] = (
        df.groupby(["customer_id", "vendor"])["transaction_month"].transform("mean").round(0)
    )
    df["vendor_month_std"] = (
        df.groupby(["customer_id", "vendor"])["transaction_month"].transform("std").fillna(0)
    )

    txn_count = df.groupby(["customer_id", "vendor"])["transaction_id"].transform("count")
    month_nunique = df.groupby(["customer_id", "vendor"])["transaction_month"].transform("nunique")
    month_nunique = month_nunique.replace(0, 1)
    df["vendor_monthly_frequency"] = (txn_count / month_nunique).round(2)

    # Preserve row count: fill missing rolling/lag values (notebook used dropna here).
    num_cols = df.select_dtypes(include=[np.number]).columns
    df[num_cols] = df[num_cols].replace([np.inf, -np.inf], 0).fillna(0)

    return df


def main() -> None:
    out_path = Path(__file__).resolve().parent / "data" / "dataset1.csv"

    raw, first_ten_customers = build_raw_transactions()
    columns = [
        "first_name",
        "last_name",
        "customer_id",
        "transaction_id",
        "transaction_datetime",
        "amount",
        "vendor",
        "transaction_type",
    ]
    df = pd.DataFrame(raw, columns=columns)
    df = engineer_features(df)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False)

    print(f"Wrote: {out_path}")
    print(f"Total rows: {len(df)} (expected {EXPECTED_ROWS})")
    print(f"Columns: {len(df.columns)}")
    print("First 10 customers (verification):")
    for i, (fn, ln, cid) in enumerate(first_ten_customers, start=1):
        print(f"  {i:2}. {fn} {ln}  ({cid})")


if __name__ == "__main__":
    main()
