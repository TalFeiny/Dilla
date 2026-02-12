'use client';

import React, { useState } from 'react';
import { ICellRendererParams } from 'ag-grid-community';
import { ChevronRight, ChevronDown, Building2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';

interface MasterDetailRendererParams extends ICellRendererParams {
  onExpand?: (rowId: string) => void;
  detailComponent?: React.ComponentType<{ rowData: any }>;
}

export const MasterDetailRenderer = React.memo(function MasterDetailRenderer(params: MasterDetailRendererParams) {
  const { value, data, onExpand, detailComponent: DetailComponent } = params;
  const [isExpanded, setIsExpanded] = useState(false);

  const handleToggle = () => {
    setIsExpanded(!isExpanded);
    if (onExpand && data?.id) {
      onExpand(data.id);
    }
  };

  return (
    <div className="w-full">
      <div className="flex items-center gap-2">
        <Button
          variant="ghost"
          size="sm"
          className="h-6 w-6 p-0"
          onClick={handleToggle}
        >
          {isExpanded ? (
            <ChevronDown className="h-4 w-4" />
          ) : (
            <ChevronRight className="h-4 w-4" />
          )}
        </Button>
        <span className="flex-1">{value || '—'}</span>
      </div>

      {isExpanded && DetailComponent && data && (
        <div className="mt-2 ml-8 border-l-2 border-gray-200 pl-4">
          <DetailComponent rowData={data} />
        </div>
      )}
    </div>
  );
});

// Default detail component for company details
export const CompanyDetailComponent = React.memo(function CompanyDetailComponent({ rowData }: { rowData: any }) {
  const company = rowData._originalRow || rowData;
  
  return (
    <Card className="mt-2">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm flex items-center gap-2">
          <Building2 className="h-4 w-4" />
          Company Details
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-2 text-sm">
        {company.companyId && (
          <div>
            <span className="font-medium">ID:</span> {company.companyId}
          </div>
        )}
        {company.companyName && (
          <div>
            <span className="font-medium">Name:</span> {company.companyName}
          </div>
        )}
        {/* Add more company details as needed */}
      </CardContent>
    </Card>
  );
});
