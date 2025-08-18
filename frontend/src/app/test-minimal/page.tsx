'use client';

import React, { useState, useCallback } from 'react';
import { Button } from '../../components/ui/button';

export default function TestMinimal() {
  const [isOpen, setIsOpen] = useState(false);
  const [test, setTest] = useState('test');

  // Test 1: Just useState
  const [data1, setData1] = useState<string>('hello');

  // Test 2: useState with object
  const [data2, setData2] = useState<any>({ id: '11', name: 'test' });

  // Test 3: useCallback
  const handleClick = useCallback(() => {
    console.log('Button clicked');
  }, []);

  // Test 4: API call
  const fetchData = useCallback(async () => {
    try {
      const response = await fetch('/api/documents/11/analysis');
      const data = await response.json();
      console.log('API data:', data);
      setData2(data);
    } catch (error) {
      console.error('API error:', error);
    }
  }, []);

  return (
    <div className="max-w-6xl mx-auto px-4 py-6">
      <h1 className="text-3xl font-bold mb-8">Minimal Test</h1>
      
      <div className="space-y-4 mb-8">
        <Button onClick={() => setIsOpen(true)}>
          Open Modal
        </Button>
        <Button onClick={handleClick}>
          Test useCallback
        </Button>
        <Button onClick={fetchData}>
          Test API Call
        </Button>
        <Button onClick={() => setData1('updated')}>
          Update Data 1
        </Button>
        <Button onClick={() => setData2({ id: '12', name: 'updated' })}>
          Update Data 2
        </Button>
      </div>

      <div className="space-y-2">
        <p>Data 1: {data1}</p>
        <p>Data 2 ID: {data2?.id}</p>
        <p>Data 2 Name: {data2?.name}</p>
      </div>

      {isOpen && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg shadow-xl max-w-md w-full p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-xl font-semibold">Minimal Modal</h2>
              <Button onClick={() => setIsOpen(false)} variant="ghost" size="sm">
                ✕
              </Button>
            </div>
            
            <div className="space-y-4">
              <p>Modal is open!</p>
              <p>Data 1: {data1}</p>
              <p>Data 2 ID: {data2?.id}</p>
              <p>Data 2 Name: {data2?.name}</p>
              <Button onClick={() => setIsOpen(false)}>
                Close Modal
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
} 