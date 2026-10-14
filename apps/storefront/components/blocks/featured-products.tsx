export default function FeaturedProductsBlock({ data }: { data: any }) {
  return (
    <section className="py-12">
      <div className="max-w-7xl mx-auto px-4">
        <h2 className="text-2xl font-bold mb-6">Featured Products</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {data.product_ids?.map((id: string) => (
            <div key={id} className="border rounded-lg p-4">
              <p>Product {id}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
