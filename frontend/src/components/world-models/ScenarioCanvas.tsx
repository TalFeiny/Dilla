"use client";

import React, { useState, useCallback, useRef } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import { getBackendUrl } from '@/lib/backend-url';

interface ScenarioEvent {
  id: string;
  entity_name: string;
  event_type: string;
  event_description: string;
  timing?: string;
  parameters: Record<string, any>;
  impact_factors: string[];
  x: number;
  y: number;
}

interface ScenarioCanvasProps {
  modelId?: string;
  fundId?: string;
  onScenarioComposed?: (scenario: any) => void;
}

export function ScenarioCanvas({ modelId, fundId, onScenarioComposed }: ScenarioCanvasProps) {
  const [query, setQuery] = useState('');
  const [events, setEvents] = useState<ScenarioEvent[]>([]);
  const [isComposing, setIsComposing] = useState(false);
  const [composedScenario, setComposedScenario] = useState<any>(null);
  const canvasRef = useRef<HTMLDivElement>(null);
  const [draggedEvent, setDraggedEvent] = useState<string | null>(null);

  const parseWhatIf = useCallback(async () => {
    if (!query.trim()) return;

    setIsComposing(true);
    try {
      const backendUrl = getBackendUrl();
      const response = await fetch(`${backendUrl}/api/nl-scenarios/what-if`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query, fund_id: fundId }),
      });

      if (!response.ok) throw new Error('Failed to parse query');

      const data = await response.json();
      const scenario = data.composed_scenario;

      // Convert events to canvas events with positions
      const newEvents: ScenarioEvent[] = scenario.events.map((e: any, i: number) => ({
        id: `event-${Date.now()}-${i}`,
        entity_name: e.entity_name,
        event_type: e.event_type,
        event_description: e.event_description,
        timing: e.timing,
        parameters: e.parameters,
        impact_factors: e.impact_factors,
        x: 100 + (i * 250),
        y: 100 + (Math.random() * 100),
      }));

      setEvents(newEvents);
      setComposedScenario(scenario);
    } catch (error) {
      console.error('Error parsing what-if query:', error);
    } finally {
      setIsComposing(false);
    }
  }, [query, fundId]);

  const composeScenario = useCallback(async () => {
    if (!modelId || !composedScenario) return;

    setIsComposing(true);
    try {
      const backendUrl = getBackendUrl();
      const response = await fetch(`${backendUrl}/api/nl-scenarios/compose`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query,
          model_id: modelId,
          fund_id: fundId,
        }),
      });

      if (!response.ok) throw new Error('Failed to compose scenario');

      const data = await response.json();
      
      if (onScenarioComposed) {
        onScenarioComposed(data);
      }

      return data;
    } catch (error) {
      console.error('Error composing scenario:', error);
    } finally {
      setIsComposing(false);
    }
  }, [query, modelId, fundId, composedScenario, onScenarioComposed]);

  const handleDragStart = (eventId: string) => {
    setDraggedEvent(eventId);
  };

  const handleDragEnd = () => {
    setDraggedEvent(null);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    if (!draggedEvent || !canvasRef.current) return;

    const rect = canvasRef.current.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;

    setEvents(prev => prev.map(evt =>
      evt.id === draggedEvent
        ? { ...evt, x, y }
        : evt
    ));
  };

  const getEventColor = (eventType: string) => {
    const colors: Record<string, string> = {
      growth_change: 'bg-blue-500',
      partnership: 'bg-green-500',
      funding: 'bg-purple-500',
      exit: 'bg-yellow-500',
      competitive: 'bg-red-500',
      operational: 'bg-orange-500',
      custom: 'bg-gray-500',
    };
    return colors[eventType] || 'bg-gray-500';
  };

  return (
    <div className="w-full h-full flex flex-col">
      {/* Natural Language Input */}
      <Card className="mb-4">
        <CardHeader>
          <CardTitle>Paint Your Scenario</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <Textarea
              placeholder="What happens if growth decelerates in YX in year 2, but Tundex starts a commercial pilot with a tier 1 aerospace company..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className="min-h-[100px]"
            />
            <div className="flex gap-2">
              <Button
                onClick={parseWhatIf}
                disabled={!query.trim() || isComposing}
              >
                {isComposing ? 'Parsing...' : 'Parse & Paint'}
              </Button>
              {composedScenario && modelId && (
                <Button
                  onClick={composeScenario}
                  disabled={isComposing}
                  variant="default"
                >
                  Compose Scenario
                </Button>
              )}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Canvas */}
      <Card className="flex-1 relative">
        <CardContent className="p-0 h-full">
          <div
            ref={canvasRef}
            className="w-full h-full relative bg-gradient-to-br from-gray-50 to-gray-100 overflow-auto"
            onDrop={handleDrop}
            onDragOver={(e) => e.preventDefault()}
          >
            {events.map((event) => (
              <div
                key={event.id}
                draggable
                onDragStart={() => handleDragStart(event.id)}
                onDragEnd={handleDragEnd}
                className={`absolute ${getEventColor(event.event_type)} text-white p-4 rounded-lg shadow-lg cursor-move min-w-[200px] max-w-[250px]`}
                style={{
                  left: `${event.x}px`,
                  top: `${event.y}px`,
                }}
              >
                <div className="font-semibold mb-2">{event.entity_name}</div>
                <div className="text-sm mb-1 opacity-90">
                  {event.event_type.replace('_', ' ').toUpperCase()}
                </div>
                <div className="text-xs mb-2 opacity-75">
                  {event.event_description}
                </div>
                {event.timing && (
                  <Badge variant="secondary" className="text-xs">
                    {event.timing}
                  </Badge>
                )}
                <div className="mt-2 text-xs opacity-75">
                  Impacts: {event.impact_factors.join(', ')}
                </div>
              </div>
            ))}

            {events.length === 0 && (
              <div className="absolute inset-0 flex items-center justify-center text-gray-400">
                <div className="text-center">
                  <p className="text-lg mb-2">Empty Canvas</p>
                  <p className="text-sm">Type a "what if" question above and click "Parse & Paint"</p>
                </div>
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Scenario Summary */}
      {composedScenario && (
        <Card className="mt-4">
          <CardHeader>
            <CardTitle>Composed Scenario</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              <div>
                <strong>Name:</strong> {composedScenario.scenario_name}
              </div>
              <div>
                <strong>Events:</strong> {composedScenario.events.length}
              </div>
              <div>
                <strong>Description:</strong> {composedScenario.description}
              </div>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
