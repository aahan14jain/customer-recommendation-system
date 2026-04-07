import os
import sys
from datetime import datetime
from pathlib import Path

import joblib
import pandas as pd
from openai import OpenAI

# Repo root contains top-level `services/` (e.g. offer_fetcher).
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from services.offer_fetcher import match_best_offer, match_top_offers

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


def _catalog_vendor_for_offers(vendor: str) -> str | None:
    """Map dataset vendor name to mock-offer catalog vendor, if any."""
    if vendor in ("Walmart", "Amazon"):
        return vendor
    if vendor in ("American Airlines", "Delta Airlines", "United Airlines"):
        return "Airlines"
    return None


def _preferred_category_for_offers(vendor: str) -> str | None:
    """
    Soft category hint for match_top_offers (mock catalog uses groceries, electronics,
    flights, home). None when we cannot map cleanly.
    """
    if vendor in ("American Airlines", "Delta Airlines", "United Airlines"):
        return "flights"
    if vendor == "Walmart":
        return "groceries"
    return None


def _serialize_alternate_offer_row(offer: dict) -> dict:
    """JSON-serializable alternate offer (matches mock offer_fetcher shape)."""
    return {
        "vendor": str(offer["vendor"]),
        "price": float(offer["price"]),
        "category": str(offer["category"]),
        "title": str(offer["title"]),
        "url": str(offer["url"]),
        "valid_until": str(offer["valid_until"]),
    }


def _catalog_alternate_offers(
    catalog_vendor: str,
    avg_spend: float,
    preferred_category: str | None,
) -> list[dict]:
    """Up to 3 ranked mock offers for the catalog vendor."""
    rows = match_top_offers(
        catalog_vendor,
        float(avg_spend),
        preferred_category=preferred_category,
        limit=3,
    )
    return [_serialize_alternate_offer_row(o) for o in rows]


def _synthetic_deal_price(vendor: str, avg_spend: float) -> float:
    """Legacy simulated deal price when no mock offer exists for this vendor."""
    if vendor in ["American Airlines", "Delta Airlines", "United Airlines"]:
        return round(avg_spend * 0.88, 2)
    if vendor in ["Walmart", "Amazon", "Costco"]:
        return round(avg_spend * 0.90, 2)
    if vendor in [
        "Starbucks",
        "Chipotle",
        "Subway",
        "Chick-Fil-A",
        "Panera Bread",
        "Macdonalds",
    ]:
        return round(avg_spend * 0.80, 2)
    return round(avg_spend * 0.85, 2)


def select_offer(prediction: dict):
    """
    Pick a deal: matched mock offer from services.offer_fetcher when available,
    otherwise synthetic pricing (legacy behavior).
    """
    vendor = prediction["vendor"]
    avg_spend = float(prediction["avg_spend"])
    window_start = prediction["window_start"]
    window_end = prediction["window_end"]

    context = VENDOR_PRICE_CONTEXT.get(
        vendor,
        {"category": "purchase", "unit": "visit", "action": "shop"},
    )

    catalog_vendor = _catalog_vendor_for_offers(vendor)
    best = (
        match_best_offer(catalog_vendor, avg_spend) if catalog_vendor else None
    )
    preferred = _preferred_category_for_offers(vendor)
    alternate_offers = (
        _catalog_alternate_offers(catalog_vendor, avg_spend, preferred)
        if catalog_vendor
        else []
    )

    predicted_spend = round(avg_spend, 2)
    if best is not None:
        deal_price = round(float(best["price"]), 2)
        return {
            "vendor": vendor,
            "deal_price": deal_price,
            "avg_spend": predicted_spend,
            "predicted_spend": predicted_spend,
            "window_start": window_start,
            "window_end": window_end,
            "category": str(best["category"]),
            "unit": context["unit"],
            "action": context["action"],
            "recommended_title": str(best["title"]),
            "offer_url": str(best["url"]),
            "valid_until": str(best["valid_until"]),
            "offer_category": str(best["category"]),
            "alternate_offers": alternate_offers,
        }

    deal_price = _synthetic_deal_price(vendor, avg_spend)
    return {
        "vendor": vendor,
        "deal_price": deal_price,
        "avg_spend": predicted_spend,
        "predicted_spend": predicted_spend,
        "window_start": window_start,
        "window_end": window_end,
        "category": context["category"],
        "unit": context["unit"],
        "action": context["action"],
        "recommended_title": "No live offer available right now",
        "offer_url": None,
        "valid_until": None,
        "offer_category": None,
        "alternate_offers": [],
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
    print(
        f"Offer: {offer['recommended_title']} | ${offer['deal_price']} at {offer['vendor']} "
        f"(url={offer['offer_url']!r}, valid_until={offer['valid_until']!r})"
    )
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

        offer_snapshot = select_offer(
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
                "offer_price": offer_snapshot["deal_price"],
                "offer_snapshot": offer_snapshot,
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
        snap = r["offer_snapshot"]
        offer = {
            **snap,
            "predicted_date": r["predicted_date"],
        }
        message = generate_message(r, offer)
        out.append(
            {
                "vendor": r["vendor"],
                "predicted_spend": float(snap["predicted_spend"]),
                "recommended_title": snap["recommended_title"],
                "deal_price": float(snap["deal_price"]),
                "offer_url": snap["offer_url"],
                "valid_until": snap["valid_until"],
                "offer_category": snap["offer_category"],
                "alternate_offers": snap.get("alternate_offers", []),
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
                    "deal_price": float(snap["deal_price"]),
                    "avg_spend": float(snap["avg_spend"]),
                    "category": snap["category"],
                    "unit": snap["unit"],
                    "action": snap["action"],
                    "window_start": snap["window_start"],
                    "window_end": snap["window_end"],
                    "recommended_title": snap["recommended_title"],
                    "offer_url": snap["offer_url"],
                    "valid_until": snap["valid_until"],
                    "offer_category": snap["offer_category"],
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
        snap = r["offer_snapshot"]
        offer = {**snap, "predicted_date": r["predicted_date"]}
        message = generate_message(r, offer)
        print(
            f"\n{r['vendor']} | cycle: every {r['avg_gap_days']} days | next: {r['predicted_date']}"
        )
        print(
            f"  title: {snap['recommended_title']} | ${snap['deal_price']} | "
            f"url={snap['offer_url']!r} | until={snap['valid_until']!r}"
        )
        ao = snap.get("alternate_offers") or []
        if ao:
            print(
                f"  alternate_offers ({len(ao)}): "
                f"{[a.get('title', '') for a in ao]}"
            )
        print(f"  {message}")

    return results


if __name__ == "__main__":
    # Single vendor demo (airline → mock "Airlines" catalog)
    sample = df[df["vendor"].isin(["American Airlines", "Delta Airlines", "United Airlines"])].iloc[0]
    run_pipeline(sample["customer_id"], sample["vendor"])

    # Verify mock matcher: Walmart should surface a catalog title/URL, not only synthetic price
    walmart_rows = df[df["vendor"] == "Walmart"]
    if not walmart_rows.empty:
        w = walmart_rows.iloc[0]
        print("\n" + "=" * 60)
        print("MOCK OFFER CHECK (Walmart)")
        print("=" * 60)
        demo_pred = predict_window(w["customer_id"], "Walmart")
        if demo_pred:
            w_offer = select_offer(demo_pred)
            print(
                f"predicted_spend={w_offer['predicted_spend']} → "
                f"title={w_offer['recommended_title']!r} deal_price={w_offer['deal_price']} "
                f"url={w_offer['offer_url']!r}"
            )

    print("\n" + "=" * 60)
    print("ALL VENDORS FOR SAME CUSTOMER")
    print("=" * 60)

    # All vendors for same customer
    run_for_all_vendors(sample["customer_id"], top_n=3)

    print("\n" + "=" * 60)
    print("RECOMMENDATION JSON SAMPLE (first item fields + alternate_offers)")
    print("=" * 60)
    payload = get_recommendations_for_customer(sample["customer_id"], top_n=1)
    if payload["recommendations"]:
        rec0 = payload["recommendations"][0]
        print(
            {
                "vendor": rec0["vendor"],
                "predicted_spend": rec0["predicted_spend"],
                "recommended_title": rec0["recommended_title"],
                "deal_price": rec0["deal_price"],
                "offer_url": rec0["offer_url"],
                "valid_until": rec0["valid_until"],
                "offer_category": rec0["offer_category"],
                "alternate_offers": rec0.get("alternate_offers", []),
            }
        )
