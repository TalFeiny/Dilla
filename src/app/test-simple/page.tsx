'use client';

import React, { useState, useEffect } from 'react';

export default function TestPage() {
  const [count, setCount] = useState(0);
  const [mounted, setMounted] = useState(false);

  // Simple useEffect to test if hooks work
  useEffect(() => {
    console.log('TestPage: useEffect executed');
    setMounted(true);
  }, []);

  // Simple click handler
  const handleClick = () => {
    console.log('TestPage: Button clicked');
    setCount(count + 1);
  };

  // Add immediate console log to see if component renders
  console.log('TestPage: Component rendering, mounted:', mounted, 'count:', count);

  return (
    <div className="p-8">
      <h1 className="text-2xl font-bold mb-4">Simple React Test</h1>
      
      <div className="space-y-4">
        <p className="text-sm text-gray-500">Mounted: {mounted ? 'true' : 'false'}</p>
        <p className="text-sm text-gray-500">Count: {count}</p>
        
        <button 
          onClick={handleClick}
          className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
        >
          Increment Count ({count})
        </button>
        
        <div className="mt-4 p-4 bg-gray-100 rounded">
          <p className="text-sm">
            If you can see this and the button works, React hooks are functioning.
          </p>
          <p className="text-sm mt-2">
            If the count stays at 0 and mounted stays false, there's a hooks issue.
          </p>
          <p className="text-sm mt-2 text-red-500">
            Check browser console for JavaScript errors!
          </p>
        </div>

        {/* Test if basic JavaScript works */}
        <div className="mt-4 p-4 bg-yellow-100 rounded">
          <p className="text-sm font-bold">JavaScript Test:</p>
          <button 
            onClick={() => alert('Basic JavaScript works!')}
            className="px-4 py-2 bg-yellow-500 text-white rounded hover:bg-yellow-600 mt-2"
          >
            Test Basic JavaScript
          </button>
        </div>
      </div>
    </div>
  );
} 