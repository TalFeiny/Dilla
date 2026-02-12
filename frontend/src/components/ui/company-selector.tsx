'use client';

import React, { useState, useMemo, useCallback, useRef, useEffect } from 'react';
import { Check, ChevronsUpDown, Search, Building2, Plus } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover';

interface Company {
  id: string;
  name: string;
  current_arr_usd?: number;
  sector?: string;
  current_valuation_usd?: number;
  year_founded?: number;
}

interface CompanySelectorProps {
  companies: Company[];
  value?: string;
  onSelect: (companyId: string) => void;
  placeholder?: string;
  disabled?: boolean;
  loading?: boolean;
  allowManualEntry?: boolean;
}

export function CompanySelector({
  companies,
  value,
  onSelect,
  placeholder = "Select company...",
  disabled = false,
  loading = false,
  allowManualEntry = true,
}: CompanySelectorProps) {
  const [open, setOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [displayLimit, setDisplayLimit] = useState(100);
  const BATCH_SIZE = 100;

  // Filter companies based on search
  const filteredCompanies = useMemo(() => {
    let filtered = companies;
    
    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase();
      filtered = companies.filter(company => 
        company.name.toLowerCase().includes(query) ||
        company.sector?.toLowerCase().includes(query)
      );
    }
    
    return filtered;
  }, [companies, searchQuery]);

  // Get companies to display based on limit
  const displayedCompanies = useMemo(() => {
    return filteredCompanies.slice(0, displayLimit);
  }, [filteredCompanies, displayLimit]);

  const hasMore = filteredCompanies.length > displayLimit;

  // Get selected company
  const selectedCompany = useMemo(() => {
    if (value === 'manual') return null;
    return companies.find(c => c.id === value);
  }, [companies, value]);

  // Format ARR for display
  const formatARR = (arr?: number) => {
    if (!arr) return null;
    const millions = arr / 1000000;
    return millions >= 1 
      ? `$${millions.toFixed(1)}M ARR`
      : `$${(arr / 1000).toFixed(0)}K ARR`;
  };

  const handleCompanySelect = (companyId: string) => {
    onSelect(companyId);
    setOpen(false);
    setSearchQuery("");
    setDisplayLimit(100); // Reset limit when closing
  };

  const handleShowMore = () => {
    setDisplayLimit(prev => prev + BATCH_SIZE);
  };

  // Reset display limit when search changes
  useEffect(() => {
    setDisplayLimit(100);
  }, [searchQuery]);

  if (loading) {
    return (
      <div className="flex h-10 w-full items-center gap-2 rounded-lg border border-input bg-background px-3 py-2">
        <Skeleton className="h-4 w-4 rounded" />
        <Skeleton className="h-4 flex-1" />
      </div>
    );
  }

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          role="combobox"
          aria-expanded={open}
          disabled={disabled}
          className="w-full justify-between"
        >
          <span className="flex items-center gap-2 truncate">
            <Building2 className="h-4 w-4 flex-shrink-0" />
            {value === 'manual' ? (
              'Manual Entry'
            ) : selectedCompany ? (
              <span className="truncate">
                {selectedCompany.name}
                {selectedCompany.current_arr_usd && (
                  <span className="ml-2 text-muted-foreground text-xs">
                    {formatARR(selectedCompany.current_arr_usd)}
                  </span>
                )}
              </span>
            ) : (
              placeholder
            )}
          </span>
          <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-[400px] p-0" align="start">
        <div className="flex flex-col">
          {/* Search Input */}
          <div className="flex items-center border-b px-3">
            <Search className="mr-2 h-4 w-4 shrink-0 opacity-50" />
            <input
              className="flex h-10 w-full rounded-md bg-transparent py-3 text-sm outline-none placeholder:text-muted-foreground"
              placeholder="Search companies..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>

          {/* Company List */}
          <div className="max-h-[400px] overflow-y-auto p-1">
            {allowManualEntry && (
              <button
                className="flex w-full items-center px-2 py-2 text-sm rounded-sm hover:bg-accent hover:text-accent-foreground cursor-pointer outline-none"
                onClick={() => handleCompanySelect('manual')}
              >
                <Plus className="mr-2 h-4 w-4" />
                <span className="font-medium">Enter Company Manually</span>
              </button>
            )}

            {filteredCompanies.length === 0 ? (
              <div className="py-6 text-center text-sm text-muted-foreground">
                No companies found.
                {searchQuery && (
                  <div className="mt-2 text-xs">
                    Try a different search term
                  </div>
                )}
              </div>
            ) : (
              <>
                <div className="px-2 py-1.5 text-xs font-medium text-muted-foreground">
                  {searchQuery.trim() ? (
                    <>Showing {filteredCompanies.length} of {companies.length} companies</>
                  ) : (
                    <>Companies ({companies.length} total)</>
                  )}
                </div>
                {displayedCompanies.map((company) => (
                  <button
                    key={company.id}
                    className={cn(
                      "flex w-full items-center px-2 py-2 text-sm rounded-sm hover:bg-accent hover:text-accent-foreground cursor-pointer outline-none",
                      value === company.id && "bg-accent"
                    )}
                    onClick={() => handleCompanySelect(company.id)}
                  >
                    <Check
                      className={cn(
                        "mr-2 h-4 w-4",
                        value === company.id ? "opacity-100" : "opacity-0"
                      )}
                    />
                    <div className="flex-1 text-left">
                      <div className="font-medium">{company.name}</div>
                      {company.current_arr_usd && (
                        <div className="text-xs text-muted-foreground">
                          {formatARR(company.current_arr_usd)}
                          {company.sector && (
                            <span className="ml-2">{company.sector}</span>
                          )}
                        </div>
                      )}
                    </div>
                  </button>
                ))}
                {hasMore && (
                  <button
                    className="flex w-full items-center justify-center px-2 py-2 text-sm font-medium text-muted-foreground hover:bg-accent hover:text-accent-foreground rounded-sm outline-none"
                    onClick={handleShowMore}
                  >
                    Show {Math.min(BATCH_SIZE, filteredCompanies.length - displayLimit)} more...
                  </button>
                )}
              </>
            )}
          </div>
        </div>
      </PopoverContent>
    </Popover>
  );
}