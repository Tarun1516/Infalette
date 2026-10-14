export default function CartSummary({ cart }: { cart: any }) {
  return (
    <div className="border rounded-lg p-4">
      <h3 className="font-semibold mb-4">Cart Summary</h3>
      <p>Total: ₹{(cart.total_cents / 100).toFixed(2)}</p>
    </div>
  );
}
