"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { ROUTES } from "@/lib/routes";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
const RECOMMENDATIONS_ME_URL = `${API_BASE}/api/recommendations/me/`;
const LOGOUT_URL = `${API_BASE}/api/auth/logout/`;

type Customer = {
  customer_id: string;
  first_name: string;
  last_name: string;
};

type RecommendationItem = {
  vendor: string;
  score: number;
  bucket: string;
  confidence: number;
  pattern: {
    predicted_date: string;
    avg_gap_days?: number;
    window_start?: string;
    window_end?: string;
    num_purchases?: number;
    avg_spend?: number;
  };
  offer: {
    deal_price: number;
    avg_spend?: number;
    category?: string;
    unit?: string;
    action?: string;
    window_start?: string;
    window_end?: string;
  };
  message: string;
};

type RecommendationsPayload = {
  customer?: Customer;
  transaction_count?: number;
  recommendations?: RecommendationItem[];
  detail?: string;
};

function clearAuthTokens() {
  localStorage.removeItem("access_token");
  localStorage.removeItem("refresh_token");
}

/** Map vendor name to a small emoji for quick visual scanning. */
function vendorEmoji(vendor: string): string {
  const v = vendor.toLowerCase();
  if (
    v.includes("american airline") ||
    v.includes("delta airline") ||
    v.includes("united airline") ||
    v.includes("airline")
  ) {
    return "✈️";
  }
  if (v.includes("amazon")) return "📦";
  if (v.includes("walmart") || v.includes("costco")) return "🛒";
  if (v.includes("starbucks")) return "☕";
  if (
    v.includes("chipotle") ||
    v.includes("subway") ||
    v.includes("macdonald") ||
    v.includes("chick-fil") ||
    v.includes("panera")
  ) {
    return "🍔";
  }
  if (v.includes("cvs")) return "💊";
  return "🏪";
}

function formatBucket(bucket: string): string {
  const b = bucket?.toLowerCase() ?? "";
  if (b === "soon" || b === "medium" || b === "later") return b;
  return bucket || "—";
}

function bucketBadgeClass(bucket: string): string {
  const b = bucket?.toLowerCase() ?? "";
  if (b === "soon") {
    return "bg-emerald-100 text-emerald-900 dark:bg-emerald-900/45 dark:text-emerald-100";
  }
  if (b === "medium") {
    return "bg-amber-100 text-amber-950 dark:bg-amber-900/40 dark:text-amber-100";
  }
  if (b === "later") {
    return "bg-zinc-200 text-zinc-700 dark:bg-zinc-600 dark:text-zinc-100";
  }
  return "bg-zinc-100 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300";
}

function computeSavings(rec: RecommendationItem): number | null {
  const deal = rec.offer?.deal_price;
  const avg = rec.offer?.avg_spend ?? rec.pattern?.avg_spend;
  if (typeof deal !== "number" || typeof avg !== "number") return null;
  const s = avg - deal;
  return Number.isFinite(s) ? s : null;
}

/** Primary headline: "Hi, {first_name}" or fallback (uses existing `customer` state). */
function headlineGreeting(
  customer: Customer | null | undefined,
  loading: boolean,
): string {
  if (loading) return "Welcome back";
  const fn = customer?.first_name?.trim();
  if (fn) return `Hi, ${fn}`;
  return "Welcome back";
}

export default function DashboardPage() {
  const router = useRouter();
  const [customer, setCustomer] = useState<Customer | null>(null);
  const [transactionCount, setTransactionCount] = useState<number | null>(null);
  const [recommendations, setRecommendations] = useState<RecommendationItem[]>(
    [],
  );
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [loggingOut, setLoggingOut] = useState(false);

  const handleLogout = useCallback(async () => {
    setLoggingOut(true);
    const refresh = localStorage.getItem("refresh_token");
    if (refresh) {
      try {
        await fetch(LOGOUT_URL, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ refresh }),
        });
      } catch {
        /* still clear local session */
      }
    }
    clearAuthTokens();
    router.replace(ROUTES.login);
  }, [router]);

  useEffect(() => {
    let cancelled = false;

    async function loadRecommendations() {
      const token = localStorage.getItem("access_token");
      if (!token) {
        if (!cancelled) setLoading(false);
        router.replace(ROUTES.login);
        return;
      }

      setLoading(true);
      setError(null);

      try {
        const res = await fetch(RECOMMENDATIONS_ME_URL, {
          headers: { Authorization: `Bearer ${token}` },
        });
        const data = (await res.json()) as RecommendationsPayload;
        console.log("Dashboard recommendations API response:", data);

        if (cancelled) return;

        if (res.status === 401) {
          clearAuthTokens();
          router.replace(ROUTES.login);
          return;
        }

        if (!res.ok) {
          setError("Failed to load recommendations");
          setCustomer(null);
          setTransactionCount(null);
          setRecommendations([]);
          return;
        }

        setCustomer(data.customer ?? null);
        setTransactionCount(
          typeof data.transaction_count === "number"
            ? data.transaction_count
            : null,
        );
        setRecommendations(
          Array.isArray(data.recommendations) ? data.recommendations : [],
        );
      } catch {
        if (!cancelled) {
          setError("Failed to load recommendations");
          setCustomer(null);
          setTransactionCount(null);
          setRecommendations([]);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    void loadRecommendations();
    return () => {
      cancelled = true;
    };
  }, [router]);

  const headline = headlineGreeting(loading ? null : customer, loading);
  const customerDisplayName = customer
    ? [customer.first_name, customer.last_name].filter(Boolean).join(" ").trim()
    : null;

  return (
    <div className="mx-auto min-h-full w-full max-w-5xl px-4 py-10 sm:px-6 sm:py-14">
      {/* Top product header */}
      <header
        className={`relative overflow-hidden rounded-2xl border border-zinc-200/90 bg-gradient-to-br from-white via-zinc-50/80 to-zinc-100/40 px-6 py-10 shadow-sm ring-1 ring-zinc-950/5 sm:px-10 sm:py-12 dark:border-zinc-800 dark:from-zinc-950 dark:via-zinc-950 dark:to-zinc-900/80 dark:ring-white/10 ${
          loading ? "[&_h1]:opacity-80" : ""
        }`}
      >
        <div className="flex flex-col gap-8 lg:flex-row lg:items-start lg:justify-between lg:gap-12">
          <div className="min-w-0 flex-1">
            <h1 className="text-4xl font-semibold tracking-tight text-zinc-900 sm:text-5xl lg:text-6xl lg:leading-[1.08] dark:text-white">
              {headline}
            </h1>
            <p className="mt-5 max-w-2xl text-base leading-relaxed text-zinc-600 sm:text-lg dark:text-zinc-400">
              Here are your personalized recommendations based on recent
              transaction behavior
            </p>
          </div>
          <div className="flex shrink-0 flex-col items-end gap-3">
            <button
              type="button"
              onClick={handleLogout}
              disabled={loggingOut}
              className="rounded-xl bg-zinc-900 px-5 py-2.5 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-zinc-800 disabled:cursor-not-allowed disabled:opacity-60 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-white"
            >
              {loggingOut ? "Signing out…" : "Log out"}
            </button>
            <Link
              href={ROUTES.home}
              className="text-sm font-medium text-zinc-500 underline-offset-4 transition-colors hover:text-zinc-800 hover:underline dark:text-zinc-400 dark:hover:text-zinc-200"
            >
              Home
            </Link>
          </div>
        </div>
      </header>

      {/* Account summary */}
      {!loading && !error && (
        <div className="mt-10 grid gap-5 sm:grid-cols-2 lg:mt-12">
          <div className="rounded-xl border border-zinc-200 bg-white p-5 shadow-sm dark:border-zinc-800 dark:bg-zinc-950">
            <p className="text-xs font-medium uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
              Customer
            </p>
            <p className="mt-1 text-lg font-semibold text-zinc-900 dark:text-zinc-50">
              {customerDisplayName || "—"}
            </p>
            {customer?.customer_id ? (
              <p className="mt-1 font-mono text-xs text-zinc-500 dark:text-zinc-400">
                ID: {customer.customer_id}
              </p>
            ) : null}
          </div>
          <div className="rounded-xl border border-zinc-200 bg-white p-5 shadow-sm dark:border-zinc-800 dark:bg-zinc-950">
            <p className="text-xs font-medium uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
              Transactions on file
            </p>
            <p className="mt-1 text-3xl font-semibold tabular-nums text-zinc-900 dark:text-zinc-50">
              {transactionCount ?? "—"}
            </p>
          </div>
        </div>
      )}

      {/* Loading */}
      {loading ? (
        <div className="mt-12 flex flex-col items-center justify-center gap-4 py-16">
          <div
            className="h-10 w-10 animate-spin rounded-full border-2 border-zinc-200 border-t-zinc-700 dark:border-zinc-700 dark:border-t-zinc-200"
            aria-hidden
          />
          <p className="text-sm font-medium text-zinc-600 dark:text-zinc-400">
            Loading recommendations…
          </p>
        </div>
      ) : null}

      {/* Error */}
      {!loading && error ? (
        <div className="mt-10 rounded-xl border border-red-200 bg-red-50 px-4 py-6 text-center dark:border-red-900/50 dark:bg-red-950/30">
          <p className="font-medium text-red-800 dark:text-red-300">{error}</p>
          <p className="mt-1 text-sm text-red-600/90 dark:text-red-400/90">
            Check that you are logged in and the API is running.
          </p>
        </div>
      ) : null}

      {/* Recommendations list */}
      {!loading && !error ? (
        <div className="mt-10">
          <h2 className="text-lg font-semibold text-zinc-900 dark:text-zinc-50">
            Your recommendations
          </h2>
          {recommendations.length === 0 ? (
            <div className="mt-4 rounded-xl border border-dashed border-zinc-300 bg-zinc-50 px-6 py-14 text-center dark:border-zinc-700 dark:bg-zinc-900/40">
              <p className="text-base font-medium text-zinc-700 dark:text-zinc-300">
                No recommendations available yet
              </p>
              <p className="mx-auto mt-2 max-w-md text-sm leading-relaxed text-zinc-500 dark:text-zinc-400">
                When your profile has enough transaction history, personalized
                offers will appear here.
              </p>
            </div>
          ) : (
            <ul className="mt-4 flex flex-col gap-4">
              {recommendations.map((rec, index) => {
                const savings = computeSavings(rec);
                const emoji = vendorEmoji(rec.vendor);
                return (
                  <li
                    key={`${rec.vendor}-${index}`}
                    className="rounded-xl border border-zinc-200 bg-white p-5 shadow-sm dark:border-zinc-800 dark:bg-zinc-950"
                  >
                    <div className="flex flex-wrap items-start justify-between gap-2">
                      <h3 className="flex items-center gap-2 text-lg font-semibold text-zinc-900 dark:text-zinc-50">
                        <span className="text-xl" aria-hidden>
                          {emoji}
                        </span>
                        <span>{rec.vendor}</span>
                      </h3>
                      <span
                        className={`rounded-full px-2.5 py-0.5 text-xs font-medium capitalize ${bucketBadgeClass(rec.bucket)}`}
                      >
                        {formatBucket(rec.bucket)}
                      </span>
                    </div>
                    <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-2">
                      <div>
                        <dt className="text-zinc-500 dark:text-zinc-400">
                          Confidence
                        </dt>
                        <dd className="font-medium text-zinc-900 dark:text-zinc-100">
                          {typeof rec.confidence === "number"
                            ? `${Math.round(rec.confidence * 100)}%`
                            : "—"}
                        </dd>
                      </div>
                      <div>
                        <dt className="text-zinc-500 dark:text-zinc-400">
                          Predicted date
                        </dt>
                        <dd className="font-medium text-zinc-900 dark:text-zinc-100">
                          {rec.pattern?.predicted_date ?? "—"}
                        </dd>
                      </div>
                      <div className="sm:col-span-2">
                        <dt className="text-zinc-500 dark:text-zinc-400">
                          Deal price
                        </dt>
                        <dd className="mt-0.5 text-zinc-900 dark:text-zinc-100">
                          {typeof rec.offer?.deal_price === "number" ? (
                            <span className="text-lg font-bold tabular-nums">
                              ${rec.offer.deal_price.toFixed(2)}
                            </span>
                          ) : (
                            "—"
                          )}
                          {typeof rec.offer?.avg_spend === "number" ? (
                            <span className="ml-2 text-zinc-500 dark:text-zinc-400">
                              (typical ~${rec.offer.avg_spend.toFixed(2)})
                            </span>
                          ) : null}
                        </dd>
                        {savings !== null && savings > 0 ? (
                          <dd className="mt-1 text-sm font-medium text-emerald-700 dark:text-emerald-400">
                            Save ${savings.toFixed(2)} vs typical spend
                          </dd>
                        ) : null}
                      </div>
                    </dl>
                    <p className="mt-4 border-t border-zinc-100 pt-4 text-sm leading-relaxed text-zinc-700 dark:border-zinc-800 dark:text-zinc-300">
                      {rec.message}
                    </p>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      ) : null}
    </div>
  );
}
