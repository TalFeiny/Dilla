'use client';

export default function MinimalPage() {
  return (
    <>
      <style jsx>{`
        .test-blue {
          background-color: blue !important;
          color: white !important;
          padding: 2rem !important;
        }
      `}</style>
      <div className="test-blue">
        If this is blue with white text, inline styles work
      </div>
      <div className="bg-red-500 text-white p-8">
        If this is red with white text, Tailwind works
      </div>
    </>
  );
}