'use client';

import React, { useState, useMemo } from 'react';
import { ColumnDef } from '@tanstack/react-table';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { 
  RefreshCw, 
  Edit, 
  MoreVertical
} from 'lucide-react';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { DataTable } from '@/components/ui/data-table';

interface PortfolioCompany {
  id: string;
  name: string;
  sector?: string;
  investmentLead?: string;
  cashInBank?: number;
  burnRate?: number;
  runwayMonths?: number;
  currentArr?: number;
  grossMargin?: number;
  lastContacted?: string;
  cashUpdatedAt?: string;
  burnRateUpdatedAt?: string;
  runwayUpdatedAt?: string;
  revenueUpdatedAt?: string;
  grossMarginUpdatedAt?: string;
}

interface PortfolioCompaniesTableProps {
  companies: PortfolioCompany[];
  fundId: string;
  onRefresh?: () => void;
  onEdit?: (company: PortfolioCompany) => void;
}

const formatCurrency = (value?: number) => {
  if (!value) return 'N/A';
  if (value >= 1000000) return `$${(value / 1000000).toFixed(1)}M`;
  if (value >= 1000) return `$${(value / 1000).toFixed(0)}K`;
  return `$${value.toLocaleString()}`;
};

const formatPercentage = (value?: number) => {
  if (!value) return 'N/A';
  return `${(value * 100).toFixed(0)}%`;
};

const formatDate = (dateString?: string) => {
  if (!dateString) return 'N/A';
  const date = new Date(dateString);
  return date.toLocaleDateString('en-US', { month: '2-digit', day: '2-digit', year: '2-digit' });
};

const formatUpdateDate = (dateString?: string) => {
  if (!dateString) return null;
  const date = new Date(dateString);
  return date.toLocaleDateString('en-US', { month: '2-digit', day: '2-digit', year: '2-digit' });
};

export function PortfolioCompaniesTable({ 
  companies, 
  fundId, 
  onRefresh,
  onEdit 
}: PortfolioCompaniesTableProps) {
  const [refreshing, setRefreshing] = useState<string | null>(null);

  const handleRefresh = async (companyId: string) => {
    setRefreshing(companyId);
    try {
      const response = await fetch(`/api/portfolio/${fundId}/companies/${companyId}/refresh`, {
        method: 'POST',
      });
      if (response.ok) {
        onRefresh?.();
      }
    } catch (error) {
      console.error('Error refreshing company:', error);
    } finally {
      setRefreshing(null);
    }
  };

  const columns = useMemo<ColumnDef<PortfolioCompany>[]>(() => [
    {
      accessorKey: 'name',
      header: 'COMPANY',
      cell: ({ row }) => {
        const company = row.original;
        return (
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center text-sm font-semibold">
              {company.name.charAt(0).toUpperCase()}
            </div>
            <span className="font-medium">{company.name}</span>
          </div>
        );
      },
    },
    {
      accessorKey: 'investmentLead',
      header: 'INVESTMENT LEAD',
      cell: ({ row }) => {
        const company = row.original;
        return company.investmentLead ? (
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded-full bg-blue-500 text-white text-xs flex items-center justify-center">
              {company.investmentLead.charAt(0).toUpperCase()}
            </div>
            <span>{company.investmentLead}</span>
          </div>
        ) : (
          <span className="text-muted-foreground">—</span>
        );
      },
    },
    {
      accessorKey: 'sector',
      header: 'SECTOR',
      cell: ({ row }) => {
        const company = row.original;
        return company.sector ? (
          <Badge variant="outline">{company.sector}</Badge>
        ) : (
          <span className="text-muted-foreground">—</span>
        );
      },
    },
    {
      accessorKey: 'cashInBank',
      header: 'CASH IN BANK',
      cell: ({ row }) => {
        const company = row.original;
        return (
          <div className="flex flex-col">
            <span className="font-medium">{formatCurrency(company.cashInBank)}</span>
            {company.cashUpdatedAt && (
              <span className="text-xs text-muted-foreground">
                Updated {formatUpdateDate(company.cashUpdatedAt)}
              </span>
            )}
          </div>
        );
      },
    },
    {
      accessorKey: 'burnRate',
      header: 'NET BURN',
      cell: ({ row }) => {
        const company = row.original;
        return (
          <div className="flex flex-col">
            <span className={`font-medium ${company.burnRate && company.burnRate < 0 ? 'text-red-600' : ''}`}>
              {formatCurrency(company.burnRate)}
            </span>
            {company.burnRateUpdatedAt && (
              <span className="text-xs text-muted-foreground">
                Updated {formatUpdateDate(company.burnRateUpdatedAt)}
              </span>
            )}
          </div>
        );
      },
    },
    {
      accessorKey: 'runwayMonths',
      header: 'EST. RUNWAY',
      cell: ({ row }) => {
        const company = row.original;
        return (
          <div className="flex flex-col">
            <span className="font-medium">
              {company.runwayMonths ? `${company.runwayMonths} mos` : 'N/A'}
            </span>
            {company.runwayUpdatedAt && (
              <span className="text-xs text-muted-foreground">
                Updated {formatUpdateDate(company.runwayUpdatedAt)}
              </span>
            )}
          </div>
        );
      },
    },
    {
      accessorKey: 'currentArr',
      header: 'REVENUE',
      cell: ({ row }) => {
        const company = row.original;
        return (
          <div className="flex flex-col">
            <span className="font-medium">{formatCurrency(company.currentArr)}</span>
            {company.revenueUpdatedAt && (
              <span className="text-xs text-green-600">
                Updated {formatUpdateDate(company.revenueUpdatedAt)}
              </span>
            )}
          </div>
        );
      },
    },
    {
      accessorKey: 'grossMargin',
      header: 'GROSS MARGIN',
      cell: ({ row }) => {
        const company = row.original;
        return (
          <div className="flex flex-col">
            <span className="font-medium">{formatPercentage(company.grossMargin)}</span>
            {company.grossMarginUpdatedAt && (
              <span className="text-xs text-muted-foreground">
                Updated {formatUpdateDate(company.grossMarginUpdatedAt)}
              </span>
            )}
          </div>
        );
      },
    },
    {
      accessorKey: 'lastContacted',
      header: 'LAST CONTACTED',
      cell: ({ row }) => {
        const company = row.original;
        return company.lastContacted ? formatDate(company.lastContacted) : (
          <span className="text-muted-foreground">—</span>
        );
      },
    },
    {
      id: 'actions',
      header: 'ACTIONS',
      cell: ({ row }) => {
        const company = row.original;
        return (
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="sm">
                <MoreVertical className="w-4 h-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem onClick={() => onEdit?.(company)}>
                <Edit className="w-4 h-4 mr-2" />
                Edit
              </DropdownMenuItem>
              <DropdownMenuItem 
                onClick={() => handleRefresh(company.id)}
                disabled={refreshing === company.id}
              >
                <RefreshCw className={`w-4 h-4 mr-2 ${refreshing === company.id ? 'animate-spin' : ''}`} />
                {refreshing === company.id ? 'Refreshing...' : 'Refresh Data'}
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        );
      },
    },
  ], [refreshing, fundId, onRefresh, onEdit]);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-end">
        <Button variant="outline" size="sm" onClick={() => onRefresh?.()}>
          <RefreshCw className="w-4 h-4 mr-2" />
          Refresh All
        </Button>
      </div>
      <DataTable
        columns={columns}
        data={companies}
        searchable={true}
        searchPlaceholder="Search companies..."
        enablePagination={true}
        pageSize={20}
        exportable={true}
        exportFileName="portfolio-companies"
      />
    </div>
  );
}
