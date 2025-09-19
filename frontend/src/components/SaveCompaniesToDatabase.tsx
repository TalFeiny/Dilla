'use client';

import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Save, Loader2, CheckCircle, AlertCircle } from 'lucide-react';
import { useSession } from 'next-auth/react';
import { createClientComponentClient } from '@supabase/auth-helpers-nextjs';

interface SaveCompaniesToDatabaseProps {
  companies: any[];
  onSaveComplete?: (savedCount: number) => void;
}

export default function SaveCompaniesToDatabase({ 
  companies, 
  onSaveComplete 
}: SaveCompaniesToDatabaseProps) {
  const [isSaving, setIsSaving] = useState(false);
  const [saveStatus, setSaveStatus] = useState<'idle' | 'success' | 'error'>('idle');
  const [savedCount, setSavedCount] = useState(0);
  const [errorMessage, setErrorMessage] = useState('');
  const { data: session } = useSession();
  const supabase = createClientComponentClient();

  const handleSaveCompanies = async () => {
    if (!session?.user?.id) {
      setErrorMessage('Please sign in to save companies');
      setSaveStatus('error');
      return;
    }

    setIsSaving(true);
    setSaveStatus('idle');
    setErrorMessage('');

    try {
      const validCompanies = companies.filter(c => !c.error && c.company);
      let successCount = 0;

      for (const company of validCompanies) {
        try {
          // Prepare company data for existing companies table with user association
          const companyRecord = {
            name: company.company || company.name,
            website: company.website || '',
            description: company.description || '',
            funding_stage: company.funding_analysis?.stage || '',
            total_raised: company.funding_analysis?.total_raised || 0,
            last_funding_date: company.funding_analysis?.last_round_date || null,
            revenue: parseFloat(company.revenue) || 0,
            arr: parseFloat(company.arr) || 0,
            growth_rate: parseFloat(company.growth_rate) || 0,
            employee_count: company.metrics?.employees || company.employees || 0,
            valuation: company.estimated_valuation?.estimated_valuation || 0,
            metrics: {
              overall_score: company.overall_score || 0,
              fund_fit_score: company.fund_fit_score || 0,
              market_score: company.market_score || 0,
              team_score: company.team_score || 0,
              customer_quality_score: company.customer_analysis?.customer_quality_score || 0
            },
            customers: company.customer_analysis?.customers || [],
            ai_category: company.ai_category || null,
            data: company, // Store full data in JSONB field
            created_by: session.user.id, // User who saved this company
            visibility: 'private', // Only visible to this user
            user_id: session.user.id, // Associate with user for RLS
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString()
          };

          // Check if company exists for this user
          const { data: existing } = await supabase
            .from('companies')
            .select('id')
            .eq('name', companyRecord.name)
            .eq('user_id', session.user.id)
            .single();

          let result: any;
          if (existing) {
            // Update existing private company owned by this user
            result = await supabase
              .from('companies')
              .update({
                ...companyRecord,
                updated_at: new Date().toISOString()
              })
              .eq('id', existing.id)
              .eq('user_id', session.user.id) // Ensure user owns this record
              .eq('visibility', 'private'); // Can only update private companies
          } else {
            // Insert new private company for this user
            result = await supabase
              .from('companies')
              .insert({
                ...companyRecord,
                visibility: 'private', // Always private for user-saved companies
                user_id: session.user.id // Always associated with the user
              });
          }

          if (!result.error) {
            successCount++;
          }
        } catch (err) {
          console.error(`Failed to save ${company.company}:`, err);
        }
      }

      // Log activity
      await supabase
        .from('user_activities')
        .insert({
          user_id: session.user.id,
          activity_type: 'companies_saved',
          details: {
            saved_count: successCount,
            companies: validCompanies.map(c => c.company || c.name)
          },
          created_at: new Date().toISOString()
        });

      setSavedCount(successCount);
      setSaveStatus('success');
      onSaveComplete?.(successCount);

      // Reset status after 3 seconds
      setTimeout(() => {
        setSaveStatus('idle');
      }, 3000);

    } catch (error) {
      console.error('Save error:', error);
      setErrorMessage('Failed to save companies. Please try again.');
      setSaveStatus('error');
    } finally {
      setIsSaving(false);
    }
  };

  if (!companies || companies.length === 0) {
    return null;
  }

  const validCompanyCount = companies.filter(c => !c.error && c.company).length;

  return (
    <div className="flex items-center gap-2">
      <Button
        onClick={handleSaveCompanies}
        disabled={isSaving || validCompanyCount === 0}
        variant={saveStatus === 'success' ? 'default' : 'outline'}
        className={`
          ${saveStatus === 'success' ? 'bg-green-600 hover:bg-green-700' : ''}
          ${saveStatus === 'error' ? 'border-red-500 text-red-500' : ''}
        `}
      >
        {isSaving ? (
          <>
            <Loader2 className="w-4 h-4 mr-2 animate-spin" />
            Saving...
          </>
        ) : saveStatus === 'success' ? (
          <>
            <CheckCircle className="w-4 h-4 mr-2" />
            Saved {savedCount} companies
          </>
        ) : saveStatus === 'error' ? (
          <>
            <AlertCircle className="w-4 h-4 mr-2" />
            {errorMessage}
          </>
        ) : (
          <>
            <Save className="w-4 h-4 mr-2" />
            Save {validCompanyCount} companies to database
          </>
        )}
      </Button>
      
      {!session && (
        <span className="text-sm text-gray-500">
          Sign in to save companies
        </span>
      )}
    </div>
  );
}