'use client';

import { useState } from 'react';

export function Logo() {
  const [imageError, setImageError] = useState(false);

  return (
    <div className="p-3 border-b border-gray-200 text-center">
      {!imageError ? (
        <img 
          src="/logo.png" 
          alt="Company Logo" 
          className="w-8 h-8 mx-auto object-contain"
          onError={() => setImageError(true)}
        />
      ) : (
        <div className="w-8 h-8 mx-auto bg-gradient-to-br from-gray-600 to-gray-800 rounded-md flex items-center justify-center text-white font-bold">
          D
        </div>
      )}
    </div>
  );
}