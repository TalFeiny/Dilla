'use client';

import DataRoomManager from '@/components/data-room/DataRoomManager';

export default function DataRoomPage() {
  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 p-6">
      <div className="max-w-7xl mx-auto">
        <DataRoomManager />
      </div>
    </div>
  );
}