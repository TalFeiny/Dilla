export default function StaticTestPage() {
  return (
    <div className="p-8">
      <h1 className="text-2xl font-bold mb-4">Static Test Page</h1>
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
        <p className="text-blue-800">This is a static page with no client-side JavaScript.</p>
        <p className="mt-2">If you can see this, the server is working correctly.</p>
        <p className="mt-2">Current time: {new Date().toISOString()}</p>
      </div>
      
      <div className="mt-4">
        <h2 className="text-lg font-semibold mb-2">Test Links:</h2>
        <ul className="space-y-2">
          <li><a href="/documents" className="text-blue-600 hover:underline">Documents Page</a></li>
          <li><a href="/test-simple" className="text-blue-600 hover:underline">Simple Test Page</a></li>
          <li><a href="/api/documents" className="text-blue-600 hover:underline">API Endpoint</a></li>
        </ul>
      </div>
    </div>
  );
} 