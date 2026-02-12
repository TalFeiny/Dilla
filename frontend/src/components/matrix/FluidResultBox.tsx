'use client';

import React from 'react';
import { 
  FileText, 
  Building, 
  TrendingUp, 
  DollarSign, 
  FileSpreadsheet,
  Link as LinkIcon,
  ExternalLink
} from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';

export type ResultType = 'matrix' | 'company' | 'metric' | 'document' | 'text';

export interface FluidResultBoxProps {
  type: ResultType;
  data: any;
  index?: number;
  onExpand?: () => void;
}

export function FluidResultBox({ type, data, index = 0 }: FluidResultBoxProps) {
  const renderContent = () => {
    switch (type) {
      case 'matrix':
        return (
          <div className="space-y-3">
            <div className="flex items-center gap-2">
              <FileSpreadsheet className="w-5 h-5 text-blue-500" />
              <h3 className="font-semibold text-lg">{data.title || 'Matrix'}</h3>
            </div>
            {data.columns && data.rows && (
              <div className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      {data.columns.slice(0, 4).map((col: any) => (
                        <TableHead key={col.id}>
                          {col.name}
                        </TableHead>
                      ))}
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {data.rows.slice(0, 3).map((row: any, idx: number) => (
                      <TableRow key={idx}>
                        {data.columns.slice(0, 4).map((col: any) => (
                          <TableCell key={col.id}>
                            {row.cells?.[col.id]?.displayValue || row.cells?.[col.id]?.value || '-'}
                          </TableCell>
                        ))}
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
                {data.rows.length > 3 && (
                  <p className="text-xs text-muted-foreground mt-2">
                    +{data.rows.length - 3} more rows
                  </p>
                )}
              </div>
            )}
          </div>
        );

      case 'company':
        return (
          <div className="space-y-3">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-blue-500 to-purple-500 flex items-center justify-center text-white font-semibold">
                {data.name?.[0]?.toUpperCase() || 'C'}
              </div>
              <div className="flex-1">
                <h3 className="font-semibold text-lg">{data.name || 'Company'}</h3>
                <p className="text-sm text-gray-500 dark:text-gray-400">{data.sector || data.industry || 'Unknown sector'}</p>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              {data.arr && (
                <div>
                  <p className="text-xs text-gray-500 dark:text-gray-400">ARR</p>
                  <p className="text-lg font-semibold">${(data.arr / 1000000).toFixed(1)}M</p>
                </div>
              )}
              {data.valuation && (
                <div>
                  <p className="text-xs text-gray-500 dark:text-gray-400">Valuation</p>
                  <p className="text-lg font-semibold">${(data.valuation / 1000000).toFixed(1)}M</p>
                </div>
              )}
            </div>
            {data.documents && data.documents.length > 0 && (
              <div className="flex items-center gap-2 text-xs text-gray-500 dark:text-gray-400">
                <FileText className="w-3 h-3" />
                <span>{data.documents.length} document{data.documents.length !== 1 ? 's' : ''}</span>
              </div>
            )}
          </div>
        );

      case 'metric':
        return (
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <TrendingUp className="w-5 h-5 text-green-500" />
              <h3 className="font-semibold text-lg">{data.label || 'Metric'}</h3>
            </div>
            <div className="space-y-1">
              <p className="text-3xl font-bold tabular-nums">{data.value}</p>
              {data.unit && (
                <p className="text-sm text-gray-500 dark:text-gray-400">{data.unit}</p>
              )}
              {data.trend && (
                <Badge variant={data.trend > 0 ? 'default' : 'secondary'} className="text-xs">
                  {data.trend > 0 ? '↑' : '↓'} {Math.abs(data.trend)}%
                </Badge>
              )}
            </div>
            {data.description && (
              <p className="text-sm text-gray-600 dark:text-gray-400">{data.description}</p>
            )}
          </div>
        );

      case 'document':
        return (
          <div className="space-y-3">
            <div className="flex items-start gap-3">
              <FileText className="w-6 h-6 text-blue-500 mt-1" />
              <div className="flex-1">
                <h3 className="font-semibold text-lg">{data.title || 'Document'}</h3>
                {data.type && (
                  <Badge variant="outline" className="text-xs mt-1">
                    {data.type}
                  </Badge>
                )}
              </div>
              {data.url && (
                <a 
                  href={data.url} 
                  target="_blank" 
                  rel="noopener noreferrer"
                  className="text-blue-500 hover:text-blue-600"
                >
                  <ExternalLink className="w-4 h-4" />
                </a>
              )}
            </div>
            {data.snippet && (
              <p className="text-sm text-gray-600 dark:text-gray-400 line-clamp-3">
                {data.snippet}
              </p>
            )}
            {data.date && (
              <p className="text-xs text-gray-500 dark:text-gray-400">
                {new Date(data.date).toLocaleDateString()}
              </p>
            )}
          </div>
        );

      case 'text':
        return (
          <div className="space-y-2">
            <h3 className="font-semibold text-lg">{data.title || 'Analysis'}</h3>
            <div className="prose prose-sm dark:prose-invert max-w-none">
              <p className="text-gray-700 dark:text-gray-300 whitespace-pre-wrap">
                {data.content || data.text || ''}
              </p>
            </div>
            {data.citations && data.citations.length > 0 && (
              <div className="flex items-center gap-2 text-xs text-gray-500 dark:text-gray-400 pt-2 border-t border-gray-200 dark:border-gray-700">
                <LinkIcon className="w-3 h-3" />
                <span>{data.citations.length} source{data.citations.length !== 1 ? 's' : ''}</span>
              </div>
            )}
          </div>
        );

      default:
        return <div>{JSON.stringify(data)}</div>;
    }
  };

  return (
    <div className="group">
      {renderContent()}
    </div>
  );
}
