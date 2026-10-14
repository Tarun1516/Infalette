"use client";

import { useState } from "react";
import Link from "next/link";
import { storefrontApi } from "@/lib/api";
import CheckoutForm from "@/components/checkout/checkout-form";

export default function CheckoutPage({ params }: { params: { tenant: string } }) {
  const [step, setStep] = useState<1 | 2 | 3>(1);
  const [checkout, setCheckout] = useState<any>(null);
  const [order, setOrder] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [paymentMethod, setPaymentMethod] = useState<string>("razorpay");

  const handleCheckout = async (data: any) => {
    setLoading(true);
    setError(null);
    setPaymentMethod(data.payment_provider || "razorpay");
    try {
      const res = await storefrontApi.createCheckout(params.tenant, {
        customer_data: {
          email: data.customer.email,
          first_name: data.customer.first_name,
          last_name: data.customer.last_name,
          phone: data.customer.phone,
        },
        shipping_address: data.shipping,
        billing_address: data.billing,
        discount_codes: data.discount_codes,
      });
      setCheckout(res);
      const checkoutId = res.id || res.checkout_id;

      try {
        const payRes = await storefrontApi.initiatePayment(params.tenant, checkoutId, data.payment_provider || "razorpay");
        if (payRes.cod || payRes.order_id) {
          setOrder(payRes);
          setStep(3);
          return;
        }
        const paymentUrl = payRes.payment_url || payRes.url;
        if (paymentUrl) {
          setCheckout({ ...res, ...payRes });
          setStep(2);
          setTimeout(() => {
            window.location.href = paymentUrl;
          }, 900);
          return;
        }
      } catch (payErr: any) {
        console.warn("Payment initiation failed, showing checkout:", payErr);
      }

      setStep(2);
    } catch (e: any) {
      const msg = e?.response?.data?.detail || e?.response?.data?.message || e.message || "Checkout failed";
      setError(Array.isArray(msg) ? msg.join(", ") : String(msg));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-3xl mx-auto px-4 sm:px-6 py-12">
      <header className="mb-10">
        <p className="text-[12px] uppercase tracking-[0.18em] text-gray-500 dark:text-neutral-500">
          Checkout
        </p>
        <h1 className="mt-2 text-[36px] sm:text-[44px] font-semibold tracking-tight text-gray-900 dark:text-neutral-100">
          Complete your order.
        </h1>
      </header>

      <div className="flex items-center gap-2 mb-8">
        {[
          { id: 1, label: "Details" },
          { id: 2, label: "Payment" },
          { id: 3, label: "Confirmation" },
        ].map((s, idx) => (
          <div key={s.id} className="flex items-center gap-2">
            <span
              className={`inline-flex h-7 w-7 items-center justify-center rounded-full text-[12px] font-medium ${
                step >= s.id
                  ? "bg-gray-900 text-white dark:bg-white dark:text-black"
                  : "bg-gray-100 text-gray-500 dark:bg-neutral-900 dark:text-neutral-500"
              }`}
            >
              {idx + 1}
            </span>
            <span
              className={`text-[13px] ${
                step >= s.id ? "text-gray-900 dark:text-neutral-100" : "text-gray-500 dark:text-neutral-500"
              }`}
            >
              {s.label}
            </span>
            {idx < 2 && <span className="text-gray-300 dark:text-neutral-700 mx-2">/</span>}
          </div>
        ))}
      </div>

      {error && (
        <div className="rounded-2xl border border-red-200 bg-red-50 dark:bg-red-900/10 dark:border-red-900 text-red-700 dark:text-red-300 px-4 py-3 text-[14px] mb-6">
          {error}
        </div>
      )}

      {step === 1 && <CheckoutForm onSubmit={handleCheckout} loading={loading} />}

      {step === 2 && (
        <div className="rounded-2xl border border-gray-100 dark:border-neutral-900 bg-white dark:bg-neutral-950 p-10 text-center">
          <div className="w-12 h-12 mx-auto rounded-full border-4 border-gray-100 dark:border-neutral-900 border-t-blue-600 animate-spin" />
          <h2 className="mt-5 text-[20px] font-semibold text-gray-900 dark:text-neutral-100">
            Checkout created
          </h2>
          <p className="mt-2 text-[14px] text-gray-500 dark:text-neutral-500">
            Total: ₹{checkout ? (checkout.total_cents / 100).toFixed(2) : "—"}
          </p>
          <p className="mt-1 text-[12px] text-gray-400 dark:text-neutral-600">
            Reservation expires in 2 hours.
          </p>
          <p className="mt-4 text-[13px] text-gray-600 dark:text-neutral-400">
            Redirecting to {paymentMethod} secure payment page…
          </p>
          {checkout?.payment_url && (
            <a
              href={checkout.payment_url}
              className="mt-6 inline-flex h-11 px-6 items-center justify-center rounded-full bg-blue-600 text-white text-[14px] font-medium hover:bg-blue-700 transition-colors"
            >
              Pay now
            </a>
          )}
          <button
            onClick={() => setStep(3)}
            className="block mt-4 text-[12px] text-gray-500 dark:text-neutral-500 hover:underline"
          >
            I&apos;ve completed payment — show confirmation
          </button>
        </div>
      )}

      {step === 3 && (
        <div className="rounded-2xl border border-gray-100 dark:border-neutral-900 bg-white dark:bg-neutral-950 p-10 text-center">
          <div className="mx-auto w-14 h-14 rounded-full bg-green-50 dark:bg-green-900/30 flex items-center justify-center">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="w-7 h-7 text-green-600 dark:text-green-400">
              <polyline points="20 6 9 17 4 12" />
            </svg>
          </div>
          <h2 className="mt-5 text-[24px] font-semibold text-gray-900 dark:text-neutral-100">
            {order?.cod ? "Order confirmed (COD)" : "Order placed"}
          </h2>
          <p className="mt-2 text-[14px] text-gray-600 dark:text-neutral-400 max-w-md mx-auto">
            {order?.cod
              ? "Pay on delivery. You'll receive tracking as soon as it ships."
              : "Thank you. A confirmation email is on the way. Tracking will update once the order ships."}
          </p>
          {order?.order_id && (
            <Link
              href={`/${params.tenant}/orders`}
              className="mt-6 inline-flex h-11 px-6 items-center justify-center rounded-full bg-gray-900 dark:bg-white text-white dark:text-black text-[14px] font-medium hover:opacity-90 transition-opacity"
            >
              View my orders
            </Link>
          )}
        </div>
      )}
    </div>
  );
}