"use client";

/**
 * CheckoutButton — initiates a Stripe Checkout session.
 *
 * On click:
 *   1. POSTs to /api/billing/checkout with {plan_id, success_url, cancel_url}
 *   2. Redirects to the returned Stripe checkout URL
 *   3. Shows a loading spinner during the round-trip
 *   4. Shows an inline error if the request fails (no alert())
 */

import { useState } from "react";
import { getToken } from "@/lib/auth";

interface CheckoutButtonProps {
  planId: "team" | "pro";
  label?: string;
  highlight?: boolean;
  disabled?: boolean;
}

export function CheckoutButton({
  planId,
  label = "申请试用",
  highlight = false,
  disabled = false,
}: CheckoutButtonProps) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleClick = async () => {
    setLoading(true);
    setError("");

    try {
      const token = getToken();
      if (!token) {
        // Not logged in — redirect to login which will send back here
        window.location.href = `/login?redirect=/pricing`;
        return;
      }

      const origin = window.location.origin;
      const res = await fetch("/api/billing/checkout", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          plan_id: planId,
          success_url: `${origin}/billing/success?plan=${planId}`,
          cancel_url: `${origin}/pricing`,
        }),
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        setError(data?.detail ?? `Error ${res.status} — please try again`);
        return;
      }

      const { checkout_url } = await res.json();
      window.location.href = checkout_url;
    } catch (err) {
      setError("Network error — please check your connection");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <button
        onClick={handleClick}
        disabled={disabled || loading}
        style={{
          display: "block",
          width: "100%",
          textAlign: "center",
          padding: "12px 0",
          borderRadius: 10,
          fontSize: 14,
          fontWeight: 700,
          border: "none",
          cursor: disabled || loading ? "not-allowed" : "pointer",
          background: highlight ? "#fff" : "#EEF2FF",
          color: "#1E3A8A",
          opacity: disabled || loading ? 0.7 : 1,
          transition: "opacity 0.15s",
          fontFamily: "inherit",
          marginBottom: error ? 8 : 24,
        }}
      >
        {loading ? "处理中…" : label}
      </button>
      {error && (
        <p
          style={{
            fontSize: 12,
            color: highlight ? "#FCA5A5" : "#DC2626",
            margin: "0 0 24px",
            lineHeight: 1.5,
          }}
        >
          {error}
        </p>
      )}
    </div>
  );
}
