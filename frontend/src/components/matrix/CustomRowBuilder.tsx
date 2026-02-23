'use client';

import React, { useState } from 'react';
import { Plus, X, Map, Sparkles } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { MatrixRow, MatrixColumn, MatrixCell } from './UnifiedMatrix';
import { transformServiceOutput, ServiceOutput, suggestFieldMappings, detectSchema } from '@/lib/matrix/service-transformer';
import { Badge } from '@/components/ui/badge';

interface CustomRowBuilderProps {
  columns: MatrixColumn[];
  onAddRow: (row: MatrixRow) => void;
  onCancel: () => void;
  serviceOutput?: any; // Optional service output to transform
}

export function CustomRowBuilder({
  columns,
  onAddRow,
  onCancel,
  serviceOutput,
}: CustomRowBuilderProps) {
  const [mode, setMode] = useState<'manual' | 'service'>(serviceOutput ? 'service' : 'manual');
  const [fieldValues, setFieldValues] = useState<Record<string, any>>({});
  const [fieldMappings, setFieldMappings] = useState<Array<{ source: string; target: string }>>([]);
  const [serviceSchema, setServiceSchema] = useState<any>(null);

  // If service output provided, detect schema and suggest mappings
  React.useEffect(() => {
    if (serviceOutput && mode === 'service') {
      const schema = detectSchema(serviceOutput);
      setServiceSchema(schema);
      
      const mappings = suggestFieldMappings(schema, columns);
      setFieldMappings(
        mappings.map(m => ({
          source: m.sourceField,
          target: m.targetColumn,
        }))
      );
    }
  }, [serviceOutput, mode, columns]);

  const handleFieldChange = (columnId: string, value: any) => {
    setFieldValues(prev => ({
      ...prev,
      [columnId]: value,
    }));
  };

  const handleMappingChange = (index: number, field: 'source' | 'target', value: string) => {
    setFieldMappings(prev => {
      const updated = [...prev];
      updated[index] = {
        ...updated[index],
        [field]: value,
      };
      return updated;
    });
  };

  const handleAddMapping = () => {
    setFieldMappings(prev => [
      ...prev,
      { source: '', target: '' },
    ]);
  };

  const handleRemoveMapping = (index: number) => {
    setFieldMappings(prev => prev.filter((_, i) => i !== index));
  };

  const handleCreateRow = () => {
    if (mode === 'service' && serviceOutput) {
      // Transform service output
      const serviceOutputObj: ServiceOutput = {
        type: Array.isArray(serviceOutput) ? 'array' : typeof serviceOutput === 'object' ? 'object' : 'scalar',
        data: serviceOutput,
        schema: serviceSchema,
      };

      const mappings = fieldMappings
        .filter(m => m.source && m.target)
        .map(m => ({
          sourceField: m.source,
          targetColumn: m.target,
        }));

      const rows = transformServiceOutput(serviceOutputObj, columns, mappings);
      
      // Add all transformed rows
      rows.forEach(row => onAddRow(row));
    } else {
      // Manual row creation
      const cells: Record<string, MatrixCell> = {};
      columns.forEach(col => {
        cells[col.id] = {
          value: fieldValues[col.id] || null,
          source: 'manual',
          lastUpdated: new Date().toISOString(),
        };
      });

      const row: MatrixRow = {
        id: `custom-row-${Date.now()}-${Math.random().toString(36).slice(2)}`,
        cells,
      };

      onAddRow(row);
    }
  };

  const getAvailableSourceFields = () => {
    if (!serviceSchema?.properties) return [];
    return Object.keys(serviceSchema.properties);
  };

  return (
    <Dialog open={true} onOpenChange={onCancel}>
      <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Add Custom Row</DialogTitle>
          <DialogDescription>
            {mode === 'service'
              ? 'Map service output fields to matrix columns'
              : 'Create a new row with custom field values'}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-4">
          {/* Mode selector */}
          <div>
            <Label>Creation Mode</Label>
            <Select value={mode} onValueChange={(value: 'manual' | 'service') => setMode(value)}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="manual">Manual Entry</SelectItem>
                <SelectItem value="service" disabled={!serviceOutput}>
                  Transform Service Output {serviceOutput && <Badge className="ml-2">Available</Badge>}
                </SelectItem>
              </SelectContent>
            </Select>
          </div>

          {mode === 'manual' ? (
            // Manual entry form
            <div className="space-y-4">
              {columns.map((column) => (
                <div key={column.id}>
                  <Label htmlFor={column.id}>{column.name}</Label>
                  <Input
                    id={column.id}
                    type={column.type === 'number' || column.type === 'currency' ? 'number' : 'text'}
                    value={fieldValues[column.id] || ''}
                    onChange={(e) => {
                      const value = column.type === 'number' || column.type === 'currency'
                        ? (isNaN(parseFloat(e.target.value)) ? null : parseFloat(e.target.value))
                        : e.target.value;
                      handleFieldChange(column.id, value);
                    }}
                    placeholder={`Enter ${column.name.toLowerCase()}`}
                  />
                </div>
              ))}
            </div>
          ) : (
            // Service output transformation
            <div className="space-y-4">
              {serviceSchema && (
                <div className="p-3 bg-blue-50 dark:bg-blue-900/20 rounded-lg">
                  <div className="flex items-center gap-2 mb-2">
                    <Sparkles className="w-4 h-4 text-blue-600" />
                    <span className="text-sm font-medium">Detected Schema</span>
                  </div>
                  <pre className="text-xs overflow-auto max-h-32">
                    {JSON.stringify(serviceSchema, null, 2)}
                  </pre>
                </div>
              )}

              <div>
                <div className="flex items-center justify-between mb-2">
                  <Label>Field Mappings</Label>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={handleAddMapping}
                  >
                    <Plus className="w-4 h-4 mr-1" />
                    Add Mapping
                  </Button>
                </div>

                <div className="space-y-2">
                  {fieldMappings.map((mapping, index) => (
                    <div key={index} className="flex items-center gap-2">
                      <Select
                        value={mapping.source}
                        onValueChange={(value) => handleMappingChange(index, 'source', value)}
                      >
                        <SelectTrigger className="flex-1">
                          <SelectValue placeholder="Source field" />
                        </SelectTrigger>
                        <SelectContent>
                          {getAvailableSourceFields().map(field => (
                            <SelectItem key={field} value={field}>
                              {field}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>

                      <Map className="w-4 h-4 text-gray-400" />

                      <Select
                        value={mapping.target}
                        onValueChange={(value) => handleMappingChange(index, 'target', value)}
                      >
                        <SelectTrigger className="flex-1">
                          <SelectValue placeholder="Target column" />
                        </SelectTrigger>
                        <SelectContent>
                          {columns.map(col => (
                            <SelectItem key={col.id} value={col.id}>
                              {col.name}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>

                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => handleRemoveMapping(index)}
                      >
                        <X className="w-4 h-4" />
                      </Button>
                    </div>
                  ))}

                  {fieldMappings.length === 0 && (
                    <div className="text-sm text-gray-500 text-center py-4">
                      No mappings defined. Add a mapping to transform service output.
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

          <div className="flex justify-end gap-2 pt-4 border-t">
            <Button variant="outline" onClick={onCancel}>
              Cancel
            </Button>
            <Button onClick={handleCreateRow}>
              <Plus className="w-4 h-4 mr-2" />
              {mode === 'service' ? 'Transform & Add' : 'Add Row'}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
