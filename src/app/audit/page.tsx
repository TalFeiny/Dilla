'use client';

import React, { useState, useEffect } from 'react';
import supabase from '@/lib/supabase';

interface AuditLog {
  id: string;
  action: string;
  table_name: string;
  record_id: string;
  old_values?: any;
  new_values?: any;
  user_id?: string;
  ip_address?: string;
  created_at: string;
}

interface ComplianceRecord {
  id: string;
  company_id: string;
  compliance_type: string;
  status: string;
  due_date: string;
  completed_date?: string;
  description: string;
  created_at: string;
}

export default function AuditPage() {
  const [auditLogs, setAuditLogs] = useState<AuditLog[]>([]);
  const [complianceRecords, setComplianceRecords] = useState<ComplianceRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [actionFilter, setActionFilter] = useState('all');
  const [tableFilter, setTableFilter] = useState('all');
  const [complianceFilter, setComplianceFilter] = useState('all');

  // Fetch audit data from Supabase
  const fetchAuditData = async () => {
    try {
      setLoading(true);
      
      // Fetch audit logs (if audit_logs table exists)
      let { data: logs, error: logsError } = await supabase
        .from('audit_logs')
        .select('*')
        .order('created_at', { ascending: false })
        .limit(100);

      if (logsError && logsError.message.includes('relation "audit_logs" does not exist')) {
        console.log('audit_logs table not found, using mock data');
        logs = generateMockAuditLogs();
      }

      // Fetch compliance records (if compliance table exists)
      let { data: compliance, error: complianceError } = await supabase
        .from('compliance')
        .select('*')
        .order('due_date', { ascending: true });

      if (complianceError && complianceError.message.includes('relation "compliance" does not exist')) {
        console.log('compliance table not found, using mock data');
        compliance = generateMockComplianceRecords();
      }

      setAuditLogs(logs || []);
      setComplianceRecords(compliance || []);
    } catch (error) {
      console.error('Error fetching audit data:', error);
      setAuditLogs(generateMockAuditLogs());
      setComplianceRecords(generateMockComplianceRecords());
    } finally {
      setLoading(false);
    }
  };

  // Generate mock audit logs for demonstration
  const generateMockAuditLogs = (): AuditLog[] => {
    return [
      {
        id: '1',
        action: 'INSERT',
        table_name: 'companies',
        record_id: 'comp_001',
        new_values: { name: 'TechCorp Inc', industry: 'Technology' },
        user_id: 'user_001',
        ip_address: '192.168.1.100',
        created_at: new Date().toISOString()
      },
      {
        id: '2',
        action: 'UPDATE',
        table_name: 'lps',
        record_id: 'lp_001',
        old_values: { status: 'prospect' },
        new_values: { status: 'active' },
        user_id: 'user_002',
        ip_address: '192.168.1.101',
        created_at: new Date(Date.now() - 86400000).toISOString()
      },
      {
        id: '3',
        action: 'DELETE',
        table_name: 'documents',
        record_id: 'doc_001',
        old_values: { document_name: 'old_contract.pdf' },
        user_id: 'user_003',
        ip_address: '192.168.1.102',
        created_at: new Date(Date.now() - 172800000).toISOString()
      }
    ];
  };

  // Generate mock compliance records for demonstration
  const generateMockComplianceRecords = (): ComplianceRecord[] => {
    return [
      {
        id: '1',
        company_id: 'comp_001',
        compliance_type: 'KYC Review',
        status: 'pending',
        due_date: new Date(Date.now() + 86400000 * 7).toISOString(),
        description: 'Annual KYC review for TechCorp Inc',
        created_at: new Date().toISOString()
      },
      {
        id: '2',
        company_id: 'comp_002',
        compliance_type: 'Regulatory Filing',
        status: 'completed',
        due_date: new Date(Date.now() - 86400000).toISOString(),
        completed_date: new Date(Date.now() - 86400000).toISOString(),
        description: 'Q4 regulatory filing for HealthTech Ltd',
        created_at: new Date(Date.now() - 86400000 * 30).toISOString()
      },
      {
        id: '3',
        company_id: 'comp_003',
        compliance_type: 'Audit Review',
        status: 'overdue',
        due_date: new Date(Date.now() - 86400000 * 14).toISOString(),
        description: 'Annual audit review for FinTech Solutions',
        created_at: new Date(Date.now() - 86400000 * 60).toISOString()
      }
    ];
  };

  useEffect(() => {
    fetchAuditData();
  }, []);

  // Filter audit logs
  const filteredAuditLogs = React.useMemo(() => {
    return auditLogs.filter(log => {
      const matchesSearch = log.action.toLowerCase().includes(searchTerm.toLowerCase()) ||
                           log.table_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
                           log.record_id.toLowerCase().includes(searchTerm.toLowerCase());
      const matchesAction = actionFilter === 'all' || log.action === actionFilter;
      const matchesTable = tableFilter === 'all' || log.table_name === tableFilter;
      
      return matchesSearch && matchesAction && matchesTable;
    });
  }, [auditLogs, searchTerm, actionFilter, tableFilter]);

  // Filter compliance records
  const filteredComplianceRecords = React.useMemo(() => {
    return complianceRecords.filter(record => {
      const matchesSearch = record.compliance_type.toLowerCase().includes(searchTerm.toLowerCase()) ||
                           record.description.toLowerCase().includes(searchTerm.toLowerCase());
      const matchesStatus = complianceFilter === 'all' || record.status === complianceFilter;
      
      return matchesSearch && matchesStatus;
    });
  }, [complianceRecords, searchTerm, complianceFilter]);

  const getActionColor = (action: string) => {
    switch (action) {
      case 'INSERT': return 'bg-green-100 text-green-800';
      case 'UPDATE': return 'bg-blue-100 text-blue-800';
      case 'DELETE': return 'bg-red-100 text-red-800';
      default: return 'bg-gray-100 text-gray-800';
    }
  };

  const getComplianceStatusColor = (status: string) => {
    switch (status) {
      case 'completed': return 'bg-green-100 text-green-800';
      case 'pending': return 'bg-yellow-100 text-yellow-800';
      case 'overdue': return 'bg-red-100 text-red-800';
      default: return 'bg-gray-100 text-gray-800';
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="animate-spin rounded-full h-32 w-32 border-b-2 border-gray-600"></div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header with gradient */}
      <div className="bg-gradient-to-r from-gray-700 to-gray-800 shadow-lg">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="py-8">
            <h1 className="text-4xl font-bold text-white tracking-tight">Audit & Compliance</h1>
            <p className="mt-2 text-lg text-gray-100">Track system changes and regulatory compliance</p>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Key Metrics Cards */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
            <p className="text-sm font-medium text-gray-600">Total Audit Logs</p>
            <p className="text-2xl font-bold text-gray-900">{auditLogs.length}</p>
          </div>

          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
            <p className="text-sm font-medium text-gray-600">Compliance Records</p>
            <p className="text-2xl font-bold text-gray-900">{complianceRecords.length}</p>
          </div>

          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
            <p className="text-sm font-medium text-gray-600">Pending Reviews</p>
            <p className="text-2xl font-bold text-gray-900">
              {complianceRecords.filter(record => record.status === 'pending').length}
            </p>
          </div>

          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
            <p className="text-sm font-medium text-gray-600">Overdue Items</p>
            <p className="text-2xl font-bold text-red-600">
              {complianceRecords.filter(record => record.status === 'overdue').length}
            </p>
          </div>
        </div>

        {/* Search and Filters */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-8">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Search</label>
              <input
                type="text"
                placeholder="Search audit logs and compliance..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-gray-500 focus:border-transparent"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Action Type</label>
              <select
                value={actionFilter}
                onChange={(e) => setActionFilter(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-gray-500 focus:border-transparent"
              >
                <option value="all">All Actions</option>
                <option value="INSERT">Insert</option>
                <option value="UPDATE">Update</option>
                <option value="DELETE">Delete</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Table</label>
              <select
                value={tableFilter}
                onChange={(e) => setTableFilter(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-gray-500 focus:border-transparent"
              >
                <option value="all">All Tables</option>
                <option value="companies">Companies</option>
                <option value="lps">LPs</option>
                <option value="documents">Documents</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Compliance Status</label>
              <select
                value={complianceFilter}
                onChange={(e) => setComplianceFilter(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-gray-500 focus:border-transparent"
              >
                <option value="all">All Statuses</option>
                <option value="completed">Completed</option>
                <option value="pending">Pending</option>
                <option value="overdue">Overdue</option>
              </select>
            </div>
          </div>
        </div>

        {/* Audit Logs Section */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-8">
          <h2 className="text-2xl font-bold text-gray-900 mb-6">Recent Audit Logs</h2>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Action</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Table</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Record ID</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">User</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">IP Address</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Date</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {filteredAuditLogs.map((log) => (
                  <tr key={log.id} className="hover:bg-gray-50">
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className={`px-2 py-1 text-xs font-semibold rounded-full ${getActionColor(log.action)}`}>
                        {log.action}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">{log.table_name}</td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">{log.record_id}</td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">{log.user_id}</td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">{log.ip_address}</td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      {new Date(log.created_at).toLocaleDateString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Compliance Records Section */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
          <h2 className="text-2xl font-bold text-gray-900 mb-6">Compliance Records</h2>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Type</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Description</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Due Date</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Completed</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {filteredComplianceRecords.map((record) => (
                  <tr key={record.id} className="hover:bg-gray-50">
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">{record.compliance_type}</td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className={`px-2 py-1 text-xs font-semibold rounded-full ${getComplianceStatusColor(record.status)}`}>
                        {record.status}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-900">{record.description}</td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      {new Date(record.due_date).toLocaleDateString()}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      {record.completed_date ? new Date(record.completed_date).toLocaleDateString() : '-'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}
