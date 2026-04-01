import os
from datetime import datetime

import pandas as pd
import joblib
from pathlib import Path
from openai import OpenAI

MODEL_DIR = Path(__file__).parent / "models"
DATA_DIR = Path(__file__).parent / "data"

model = joblib.load(MODEL_DIR / "timing_model.pkl")
features = joblib.load(MODEL_DIR / "feature_list.pkl")
boundaries = joblib.load(MODEL_DIR / "bucket_boundaries.pkl")
df = pd.read_csv(DATA_DIR / "dataset1.csv")

q33 = boundaries["q33"]
q66 = boundaries["q66"]

BUCKET_RANGES = {0: (1, int(q33)), 1: (int(q33), int(q66)), 2: (int(q66), 365)}
BUCKET_LABELS = {0: "soon", 1: "medium", 2: "later"}

# Vendor-aware typical price ranges
VENDOR_PRICE_CONTEXT = {
    "American Airlines": {"category": "flight", "unit": "ticket", "action": "fly"},
    "Delta Airlines": {"category": "flight", "unit": "ticket", "action": "fly"},
    "United Airlines": {"category": "flight", "unit": "ticket", "action": "fly"},
    "Walmart": {"category": "groceries", "unit": "order", "action": "shop"},
    "Amazon": {"category": "online order", "unit": "order", "action": "order"},
    "Costco": {"category": "bulk goods", "unit": "trip", "action": "shop"},
    "Starbucks": {"category": "coffee", "unit": "drink", "action": "grab coffee"},
    "Chipotle": {"category": "food", "unit": "meal", "action": "eat"},
    "Subway": {"category": "food", "unit": "meal", "action": "eat"},
    "Chick-Fil-A": {"category": "food", "unit": "meal", "action": "eat"},
    "Panera Bread": {"category": "food", "unit": "meal", "action": "eat"},
    "Macdonalds": {"category": "food", "unit": "meal", "action": "grab a bite"},
    "CVS Pharmacy": {"category": "pharmacy", "unit": "purchase", "action": "pick up"},
}

client = None  # lazily created in generate_message()


def load_api_key() -> str:
    """Read OPENAI_API_KEY from the environment; raise if missing or blank."""
    key = os.environ.get("OPENAI_API_KEY")
    if key is None or not str(key).strip():
        raise RuntimeError(
            "OPENAI_API_KEY is not set or is empty. Set it in your environment "
            "(e.g. export OPENAI_API_KEY=sk-...) before calling generate_message()."
        )
    return str(key).strip()


def predict_window(customer_id: str, vendor: str):
    mask = (df["customer_id"] == customer_id) & (df["vendor"] == vendor)
    rows = df[mask].sort_values("transaction_datetime")
    if rows.empty:
        return None
    last = rows.iloc[-1]
    X = pd.DataFrame([last[features].fillna(0)])
    bucket = int(model.predict(X)[0])
    proba = model.predict_proba(X)[0]
    day_min, day_max = BUCKET_RANGES[bucket]
    last_date = pd.to_datetime(last["transaction_datetime"])
    window_start = last_date + pd.Timedelta(days=day_min)
    window_end = last_date + pd.Timedelta(days=day_max)
    avg_spend = round(float(last["customer_avg_spend"]), 2)
    return {
        "customer_id": customer_id,
        "vendor": vendor,
        "bucket": BUCKET_LABELS[bucket],
        "confidence": round(float(proba[bucket]), 2),
        "window_start": window_start.strftime("%B %d"),
        "window_end": window_end.strftime("%B %d"),
        "avg_spend": avg_spend,
        "last_amount": round(float(last["amount"]), 2),
    }


def detect_purchase_pattern(customer_id: str, vendor: str):
    """
    Detect recurring purchase pattern for a customer+vendor pair.
    Returns predicted next window based on historical cycle.
    """
    mask = (df["customer_id"] == customer_id) & (df["vendor"] == vendor)
    history = df[mask].sort_values("transaction_datetime").copy()
    history["transaction_datetime"] = pd.to_datetime(history["transaction_datetime"])

    if len(history) < 3:
        return None  # not enough history to detect a pattern

    # Extract day-of-month and month for each purchase
    history["day_of_month"] = history["transaction_datetime"].dt.day
    history["month"] = history["transaction_datetime"].dt.month

    # Detect average day-of-month (e.g. always buys around the 5th)
    avg_day = int(history["day_of_month"].mean())
    std_day = history["day_of_month"].std()

    # Detect average gap in days between purchases
    gaps = history["transaction_datetime"].diff().dt.days.dropna()
    avg_gap = gaps.mean()

    if pd.isna(avg_gap) or avg_gap <= 0:
        return None

    # Predict next purchase date from last known purchase
    last_date = history["transaction_datetime"].iloc[-1]
    today = pd.Timestamp(datetime.today().date())
    next_date = last_date + pd.Timedelta(days=avg_gap)

    # If next_date is already past, roll forward by avg_gap until it's future
    while next_date < today:
        next_date += pd.Timedelta(days=avg_gap)

    # Window = next_date ± std_day (how variable their purchase day is)
    window_days = max(3, int(std_day)) if not pd.isna(std_day) else 5
    window_start = next_date - pd.Timedelta(days=window_days)
    window_end = next_date + pd.Timedelta(days=window_days)

    # Clamp window start to today
    if window_start < today:
        window_start = today

    avg_spend = history["amount"].mean()

    return {
        "customer_id": customer_id,
        "vendor": vendor,
        "avg_gap_days": round(avg_gap, 1),
        "avg_day_of_month": avg_day,
        "predicted_date": next_date.strftime("%B %d"),
        "window_start": window_start.strftime("%B %d"),
        "window_end": window_end.strftime("%B %d"),
        "window_start_dt": window_start,
        "window_end_dt": window_end,
        "avg_spend": round(float(avg_spend), 2),
        "num_purchases": len(history),
    }


def select_offer(prediction: dict):
    """
    Simulate a vendor-appropriate deal near the customer's avg spend at that vendor.
    Later replaced by real scraper output.
    """
    vendor = prediction["vendor"]
    avg_spend = prediction["avg_spend"]

    # Vendor-aware price simulation
    if vendor in ["American Airlines", "Delta Airlines", "United Airlines"]:
        deal_price = round(avg_spend * 0.88, 2)  # flights: 12% off
    elif vendor in ["Walmart", "Amazon", "Costco"]:
        deal_price = round(avg_spend * 0.90, 2)  # retail: 10% off
    elif vendor in [
        "Starbucks",
        "Chipotle",
        "Subway",
        "Chick-Fil-A",
        "Panera Bread",
        "Macdonalds",
    ]:
        deal_price = round(avg_spend * 0.80, 2)  # food: 20% off (promo)
    else:
        deal_price = round(avg_spend * 0.85, 2)

    context = VENDOR_PRICE_CONTEXT.get(
        vendor,
        {"category": "purchase", "unit": "visit", "action": "shop"},
    )

    return {
        "vendor": vendor,
        "deal_price": deal_price,
        "avg_spend": avg_spend,
        "window_start": prediction["window_start"],
        "window_end": prediction["window_end"],
        "category": context["category"],
        "unit": context["unit"],
        "action": context["action"],
    }


def generate_message(prediction: dict, offer: dict) -> str:
    global client
    savings = round(offer["avg_spend"] - offer["deal_price"], 2)
    best_time = offer.get("predicted_date", offer["window_start"])
    extra = f" Saving you about ${savings}." if savings > 0 else ""
    fallback = (
        f"Check {offer['vendor']} for {offer['category']} around ${offer['deal_price']} per {offer['unit']}. "
        f"Best time to {offer['action']} is around {best_time}.{extra}"
    )

    try:
        api_key = load_api_key()
    except RuntimeError:
        return fallback

    if client is None:
        client = OpenAI(api_key=api_key)

    prompt = f"""
You are a friendly deal alert assistant. Write a short 1-2 sentence message.

Rules:
- Sound like a helpful friend, NOT a bank or data system
- NEVER mention transactions, history, data, or averages
- Focus on: the deal price, the vendor, and the time window
- If savings > 0, mention it naturally (e.g. "saving you $X")
- Be specific to what the vendor sells

Deal:
- Vendor: {offer['vendor']}
- What they sell: {offer['category']}
- Deal price: ${offer['deal_price']} per {offer['unit']}
- Best time to {offer['action']}: around {offer.get('predicted_date', offer['window_start'])}
- Normal price: ${offer['avg_spend']}
- Savings: ${savings}

Write only the message:
"""
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=80,
            temperature=0.7,
        )
        content = response.choices[0].message.content
        return content.strip() if content else fallback
    except Exception:
        return fallback


def run_pipeline(customer_id: str, vendor: str):
    print(f"\nRunning pipeline for {customer_id[:8]}... | {vendor}")
    prediction = predict_window(customer_id, vendor)
    if not prediction:
        print("No history found for this customer+vendor pair.")
        return
    print(f"Prediction: {prediction['bucket']} (confidence: {prediction['confidence']})")
    print(f"Scrape window: {prediction['window_start']} → {prediction['window_end']}")
    offer = select_offer(prediction)
    print(f"Offer: ${offer['deal_price']} at {offer['vendor']}")
    message = generate_message(prediction, offer)
    print(f"\nGenerated message:\n{message}")
    return message


def _compute_ranked_recommendations(customer_id: str):
    """
    Ranked vendor recommendations for a customer using the training dataset (ML features).
    Returns a list of dicts with pattern fields, bucket, confidence, offer_price, score.
    """
    customer_df = df[df["customer_id"] == customer_id]
    if customer_df.empty:
        return []

    vendors = customer_df["vendor"].unique()
    today = pd.Timestamp(datetime.today().date())
    results = []
    for vendor in vendors:
        pattern = detect_purchase_pattern(customer_id, vendor)
        if not pattern:
            continue

        ml_pred = predict_window(customer_id, vendor)
        confidence = ml_pred["confidence"] if ml_pred else 0.5
        bucket = ml_pred["bucket"] if ml_pred else "medium"

        days_until = (pattern["window_start_dt"] - today).days
        urgency = max(0, 100 - days_until)
        score = round((urgency / 100) * confidence, 3)

        offer = select_offer(
            {
                "vendor": vendor,
                "avg_spend": pattern["avg_spend"],
                "window_start": pattern["window_start"],
                "window_end": pattern["window_end"],
            }
        )

        results.append(
            {
                **pattern,
                "bucket": bucket,
                "confidence": confidence,
                "offer_price": offer["deal_price"],
                "score": score,
            }
        )

    return sorted(results, key=lambda x: x["score"], reverse=True)


def get_recommendations_for_customer(customer_id: str, top_n: int = 5):
    """
    Run the recommendation pipeline for one customer and return JSON-serializable data.
    Uses the same dataset as the ML model (dataset1.csv). Does not query Django ORM.
    """
    results = _compute_ranked_recommendations(customer_id)
    out = []
    for r in results[:top_n]:
        ctx = VENDOR_PRICE_CONTEXT.get(r["vendor"], {})
        offer = {
            "vendor": r["vendor"],
            "deal_price": r["offer_price"],
            "window_start": r["window_start"],
            "window_end": r["window_end"],
            "category": ctx.get("category", "purchase"),
            "unit": ctx.get("unit", "visit"),
            "action": ctx.get("action", "shop"),
            "avg_spend": r["avg_spend"],
            "predicted_date": r["predicted_date"],
        }
        message = generate_message(r, offer)
        out.append(
            {
                "vendor": r["vendor"],
                "score": r["score"],
                "bucket": r["bucket"],
                "confidence": r["confidence"],
                "pattern": {
                    "avg_gap_days": r["avg_gap_days"],
                    "predicted_date": r["predicted_date"],
                    "window_start": r["window_start"],
                    "window_end": r["window_end"],
                    "num_purchases": r["num_purchases"],
                    "avg_spend": r["avg_spend"],
                },
                "offer": {
                    "deal_price": float(offer["deal_price"]),
                    "avg_spend": float(offer["avg_spend"]),
                    "category": offer["category"],
                    "unit": offer["unit"],
                    "action": offer["action"],
                    "window_start": offer["window_start"],
                    "window_end": offer["window_end"],
                },
                "message": message,
            }
        )

    return {"recommendations": out}


def run_for_all_vendors(customer_id: str, top_n: int = 5):
    """
    Run the full pipeline for all vendors this customer has history with.
    Uses cycle-aware windows from detect_purchase_pattern; ML bucket/confidence from predict_window.
    """
    customer_df = df[df["customer_id"] == customer_id]
    if customer_df.empty:
        print(f"No history found for customer {customer_id[:8]}...")
        return []

    vendors = customer_df["vendor"].unique()
    print(f"\nCustomer {customer_id[:8]}... | {len(vendors)} vendors in history")
    print("=" * 60)

    results = _compute_ranked_recommendations(customer_id)

    print(f"\n{'Vendor':<22} {'Cycle':<10} {'Predicted date':<18} {'Window':<28} {'Offer'}")
    print("-" * 90)
    for r in results:
        window = f"{r['window_start']} → {r['window_end']}"
        print(
            f"{r['vendor']:<22} {r['avg_gap_days']:<10} {r['predicted_date']:<18} "
            f"{window:<28} ${r['offer_price']}"
        )

    print(f"\nGenerating messages for top {top_n} recommendations...")
    print("=" * 60)
    for r in results[:top_n]:
        ctx = VENDOR_PRICE_CONTEXT.get(r["vendor"], {})
        offer = {
            "vendor": r["vendor"],
            "deal_price": r["offer_price"],
            "window_start": r["window_start"],
            "window_end": r["window_end"],
            "category": ctx.get("category", "purchase"),
            "unit": ctx.get("unit", "visit"),
            "action": ctx.get("action", "shop"),
            "avg_spend": r["avg_spend"],
            "predicted_date": r["predicted_date"],
        }
        message = generate_message(r, offer)
        print(
            f"\n{r['vendor']} | cycle: every {r['avg_gap_days']} days | next: {r['predicted_date']}"
        )
        print(f"  {message}")

    return results


if __name__ == "__main__":
    # Single vendor demo
    sample = df[df["vendor"].isin(["American Airlines", "Delta Airlines", "United Airlines"])].iloc[0]
    run_pipeline(sample["customer_id"], sample["vendor"])

    print("\n" + "=" * 60)
    print("ALL VENDORS FOR SAME CUSTOMER")
    print("=" * 60)

    # All vendors for same customer
    run_for_all_vendors(sample["customer_id"], top_n=3)
