import { NextRequest, NextResponse } from 'next/server';
import { supabaseService } from '@/lib/supabase';

export async function GET(request: NextRequest) {
  try {
    if (!supabaseService) {
      return NextResponse.json({ error: 'Supabase service not configured' }, { status: 500 });
    }

    const { searchParams } = new URL(request.url);
    const type = searchParams.get('type') || 'all';
    const limit = parseInt(searchParams.get('limit') || '100', 10);

    let auditLogs = [];
    let complianceRecords = [];

    // Fetch audit logs if audit_logs table exists
    try {
      const { data: logs, error: logsError } = await supabaseService
        .from('audit_logs')
        .select('*')
        .order('created_at', { ascending: false })
        .limit(limit);

      if (!logsError) {
        auditLogs = logs || [];
      }
    } catch (error) {
      console.log('audit_logs table not found or error occurred');
    }

    // Fetch compliance records if compliance table exists
    try {
      const { data: compliance, error: complianceError } = await supabaseService
        .from('compliance')
        .select('*')
        .order('due_date', { ascending: true })
        .limit(limit);

      if (!complianceError) {
        complianceRecords = compliance || [];
      }
    } catch (error) {
      console.log('compliance table not found or error occurred');
    }

    return NextResponse.json({
      auditLogs,
      complianceRecords,
      totalAuditLogs: auditLogs.length,
      totalComplianceRecords: complianceRecords.length
    });
  } catch (error) {
    console.error('API error:', error);
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
  }
}

export async function POST(request: NextRequest) {
  try {
    if (!supabaseService) {
      return NextResponse.json({ error: 'Supabase service not configured' }, { status: 500 });
    }

    const body = await request.json();
    const { type, data } = body;

    let result;

    if (type === 'audit_log') {
      const { data: insertedData, error } = await supabaseService
        .from('audit_logs')
        .insert([data])
        .select();

      if (error) {
        console.error('Supabase error:', error);
        return NextResponse.json({ error: 'Failed to create audit log' }, { status: 500 });
      }

      result = insertedData?.[0] || {};
    } else if (type === 'compliance') {
      const { data: insertedData, error } = await supabaseService
        .from('compliance')
        .insert([data])
        .select();

      if (error) {
        console.error('Supabase error:', error);
        return NextResponse.json({ error: 'Failed to create compliance record' }, { status: 500 });
      }

      result = insertedData?.[0] || {};
    } else {
      return NextResponse.json({ error: 'Invalid type specified' }, { status: 400 });
    }

    return NextResponse.json(result);
  } catch (error) {
    console.error('API error:', error);
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
  }
} 