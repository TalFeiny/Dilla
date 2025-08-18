'use client';

import React, { useState } from 'react';
import { Button } from '../../components/ui/button';

export default function TestSimpleModal() {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <div className="max-w-6xl mx-auto px-4 py-6">
      <h1 className="text-3xl font-bold mb-8">Simple Modal Test</h1>
      
      <Button onClick={() => setIsOpen(true)}>
        Open Simple Modal
      </Button>

      {isOpen && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg shadow-xl max-w-md w-full p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-xl font-semibold">Simple Test Modal</h2>
              <Button onClick={() => setIsOpen(false)} variant="ghost" size="sm">
                ✕
              </Button>
            </div>
            
            <div className="space-y-4">
              <p>This is a simple test modal.</p>
              <p>If you can see this, the modal component works.</p>
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