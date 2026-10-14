"use client";

import { toast } from "@/components/toaster";

import { useState } from "react";

interface Props {
  onSubmit: (data: any) => void;
  loading?: boolean;
}

export default function CheckoutForm({ onSubmit, loading }: Props) {
  const [email, setEmail] = useState("");
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [phone, setPhone] = useState("");
  const [address, setAddress] = useState("");
  const [city, setCity] = useState("");
  const [state, setState] = useState("");
  const [country, setCountry] = useState("India");
  const [pincode, setPincode] = useState("");
  const [coupon, setCoupon] = useState("");
  const [paymentMethod, setPaymentMethod] = useState<"razorpay" | "stripe" | "cod">("razorpay");
  const [agreed, setAgreed] = useState(false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!agreed) {
      toast({ kind: "info", title: "Please accept the terms and privacy policy" });
      return;
    }
    onSubmit({
      customer: { email, first_name: firstName, last_name: lastName, phone },
      shipping: { address, city, state, country, pincode, phone },
      billing: { address, city, state, country, pincode },
      discount_codes: coupon ? [coupon] : [],
      payment_provider: paymentMethod,
    });
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-5 bg-white p-6 rounded-2xl border">
      {/* Customer */}
      <div>
        <h3 className="text-sm font-semibold text-gray-900 mb-3">Contact Information</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Email *</label>
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@example.com" className="w-full p-2.5 border rounded-lg text-sm" required />
            <p className="text-[11px] text-gray-400 mt-1">Order confirmation sent here. Consent can be withdrawn anytime.</p>
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Phone</label>
            <input type="tel" value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="+91 98765 43210" className="w-full p-2.5 border rounded-lg text-sm" />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">First Name *</label>
            <input type="text" value={firstName} onChange={(e) => setFirstName(e.target.value)} placeholder="First name" className="w-full p-2.5 border rounded-lg text-sm" required />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Last Name</label>
            <input type="text" value={lastName} onChange={(e) => setLastName(e.target.value)} placeholder="Last name" className="w-full p-2.5 border rounded-lg text-sm" />
          </div>
        </div>
      </div>

      {/* Shipping */}
      <div>
        <h3 className="text-sm font-semibold text-gray-900 mb-3">Shipping Address</h3>
        <div className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Street Address *</label>
            <input type="text" value={address} onChange={(e) => setAddress(e.target.value)} placeholder="House no, street, landmark" className="w-full p-2.5 border rounded-lg text-sm" required />
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">City *</label>
              <input type="text" value={city} onChange={(e) => setCity(e.target.value)} className="w-full p-2.5 border rounded-lg text-sm" required />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">State *</label>
              <input type="text" value={state} onChange={(e) => setState(e.target.value)} placeholder="Karnataka" className="w-full p-2.5 border rounded-lg text-sm" required />
              <p className="text-[11px] text-gray-400">GST applied per product tax class (18% standard / 5% reduced)</p>
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Pincode *</label>
              <input type="text" value={pincode} onChange={(e) => setPincode(e.target.value)} placeholder="560001" className="w-full p-2.5 border rounded-lg text-sm" required />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Country *</label>
              <select value={country} onChange={(e) => setCountry(e.target.value)} className="w-full p-2.5 border rounded-lg text-sm bg-white">
                <option value="India">India</option>
                <option value="USA">USA</option>
                <option value="UAE">UAE</option>
                <option value="UK">UK</option>
              </select>
            </div>
          </div>
        </div>
      </div>

      {/* Coupon */}
      <div className="border-t pt-4">
        <label className="block text-xs font-medium text-gray-600 mb-1">Coupon Code</label>
        <div className="flex gap-2">
          <input type="text" value={coupon} onChange={(e) => setCoupon(e.target.value)} placeholder="SAVE10, FREESHIP" className="flex-1 p-2.5 border rounded-lg text-sm" />
          <span className="text-xs text-gray-400 self-center">Applied at checkout — validates per tenant</span>
        </div>
      </div>

      {/* Payment */}
      <div className="border-t pt-4">
        <h3 className="text-sm font-semibold text-gray-900 mb-3">Payment Method</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          {[
            { id: "razorpay", label: "Razorpay", desc: "Cards, UPI, NetBanking (India)" },
            { id: "stripe", label: "Stripe", desc: "International cards" },
            { id: "cod", label: "Cash on Delivery", desc: "Pay on delivery, where available" },
          ].map((m) => (
            <label key={m.id} className={`border rounded-xl p-3 cursor-pointer flex gap-3 items-start ${paymentMethod === m.id ? "border-blue-600 bg-blue-50" : "hover:bg-gray-50"}`}>
              <input type="radio" name="paymentMethod" value={m.id} checked={paymentMethod === m.id} onChange={(e) => setPaymentMethod(e.target.value as any)} className="mt-1" />
              <div>
                <p className="text-sm font-medium">{m.label}</p>
                <p className="text-xs text-gray-500">{m.desc}</p>
              </div>
            </label>
          ))}
        </div>
        {paymentMethod === "cod" && (
          <p className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-lg p-2 mt-3">COD orders are confirmed immediately without online payment. Our team will confirm shipping.</p>
        )}
        {paymentMethod !== "cod" && (
          <p className="text-xs text-gray-500 mt-2">You will be redirected to a secure hosted payment page. The signed webhook is authoritative — do not trust browser redirect alone. Idempotency-Key prevents double charge on retry.</p>
        )}
      </div>

      <label className="flex gap-2 items-start text-xs text-gray-600">
        <input type="checkbox" checked={agreed} onChange={(e) => setAgreed(e.target.checked)} required className="mt-0.5" />
        <span>I agree to the privacy policy, terms, return policy and consent to store my data per DPDP. I confirm ingredients / age suitability warnings have been read.</span>
      </label>

      <button type="submit" disabled={!!loading} className="w-full bg-blue-600 text-white py-3 rounded-full font-semibold disabled:opacity-50">
        {loading ? "Creating checkout…" : paymentMethod === "cod" ? "Place COD Order" : "Proceed to Secure Payment"}
      </button>
    </form>
  );
}
