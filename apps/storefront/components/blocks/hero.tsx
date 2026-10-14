export default function HeroBlock({ data }: { data: any }) {
  return (
    <section className="bg-gradient-to-r from-blue-500 to-purple-600 text-white py-20">
      <div className="max-w-7xl mx-auto px-4 text-center">
        <h1 className="text-4xl md:text-5xl font-bold mb-4">{data.title}</h1>
        <p className="text-xl mb-8">{data.subtitle}</p>
        {data.cta_text && (
          <button className="bg-white text-blue-600 px-6 py-3 rounded-lg font-semibold">
            {data.cta_text}
          </button>
        )}
      </div>
    </section>
  );
}
