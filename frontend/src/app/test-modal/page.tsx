'use client';

import React, { useState } from 'react';
import { Button } from '@/components/ui/button';

export default function TestModalPage() {
  const [isOpen, setIsOpen] = useState(false);
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  const testModal = async () => {
    console.log('Test modal button clicked');
    setIsOpen(true);
    setLoading(true);
    
    try {
      const response = await fetch('/api/documents/11/analysis');
      const result = await response.json();
      console.log('API response:', result);
      setData(result);
    } catch (error) {
      console.error('API error:', error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="p-8">
      <h1 className="text-2xl font-bold mb-4">Test Modal</h1>
      <Button onClick={testModal} className="mb-4">
        Test Modal
      </Button>
      
      {isOpen && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white p-6 rounded-lg max-w-2xl max-h-96 overflow-y-auto">
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-xl font-bold">Test Modal Content</h2>
              <Button onClick={() => setIsOpen(false)} variant="outline" size="sm">
                Close
              </Button>
            </div>
            
            {loading ? (
              <div>Loading...</div>
            ) : data ? (
              <div>
                <h3 className="font-bold mb-2">Analysis Data:</h3>
                <pre className="text-xs bg-gray-100 p-2 rounded overflow-auto">
                  {JSON.stringify(data, null, 2)}
                </pre>
              </div>
            ) : (
              <div>No data loaded</div>
            )}
          </div>
        </div>
      )}
    </div>
  );
} 