'use client';

import { useState, useEffect } from 'react';

interface DashboardData {
  companies: number;
  lps: number;
  activeInvestments: number;
  totalDeals: number;
}

export default function HomePage() {
  const [dashboardData, setDashboardData] = useState<DashboardData>({
    companies: 0,
    lps: 0,
    activeInvestments: 0,
    totalDeals: 0,
  });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchDashboardData();
  }, []);

  const fetchDashboardData = async () => {
    try {
      setLoading(true);
      // Use a single optimized API call instead of multiple calls
      const response = await fetch('/api/dashboard');
      if (response.ok) {
        const data = await response.json();
        setDashboardData(data);
      }
    } catch (error) {
      console.error('Error fetching dashboard data:', error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-6 py-8 sm:px-8 lg:px-12">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900 mb-2">Dilla AI</h1>
        <p className="text-gray-600 text-lg">Welcome to your VC Platform dashboard</p>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <StatCard label="Total Companies" value={loading ? '...' : dashboardData.companies} />
        <StatCard label="Active Investments" value={loading ? '...' : dashboardData.activeInvestments} />
        <StatCard label="Total LP Onboarded" value={loading ? '...' : dashboardData.lps} />
        <StatCard label="Total Deals" value={loading ? '...' : dashboardData.totalDeals} />
      </div>
      <div className="mt-8 grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Recent Activity</h3>
          <ul className="space-y-2 text-gray-600 text-sm">
            <li>Dashboard connected to Supabase</li>
            <li>Real-time data from companies and LPs</li>
            <li>Data connections now connected to database</li>
          </ul>
        </div>
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Quick Actions</h3>
          <div className="space-y-2">
            <button className="w-full text-left px-3 py-2 text-sm text-gray-700 rounded-md hover:bg-gray-100">
              Add New Company
            </button>
            <button className="w-full text-left px-3 py-2 text-sm text-gray-700 rounded-md hover:bg-gray-100">
              Add New LP
            </button>
            <button className="w-full text-left px-3 py-2 text-sm text-gray-700 rounded-md hover:bg-gray-100">
              View Portfolio Report
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function StatCard({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 flex flex-col items-start">
      <p className="text-sm font-medium text-gray-600">{label}</p>
      <p className="text-2xl font-bold text-gray-900">{value}</p>
    </div>
  );
}