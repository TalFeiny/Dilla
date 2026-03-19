'use client';

import React, { useState, useCallback } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Loader2, Play, Plus, MessageSquare, ChevronDown, ChevronRight } from 'lucide-react';
import type { EventChain, EventNode, CausalLink } from './CascadeModelView';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface ModelSpecEditorProps {
  eventChain: EventChain | null;
  onToggleEvent: (eventId: string, enabled: boolean) => void;
  onChangeProbability: (eventId: string, probability: number) => void;
  onRePrompt: (prompt: string) => void;
  onRun: () => void;
  loading?: boolean;
  readOnly?: boolean;
}

// ---------------------------------------------------------------------------
// Event card
// ---------------------------------------------------------------------------

function EventCard({
  event,
  links,
  enabled,
  onToggle,
  onChangeProbability,
  readOnly,
}: {
  event: EventNode;
  links: CausalLink[];
  enabled: boolean;
  onToggle: (enabled: boolean) => void;
  onChangeProbability: (p: number) => void;
  readOnly?: boolean;
}) {
  const [expanded, setExpanded] = useState(false);

  // Outgoing links from this event
  const outgoing = links.filter(l => l.source === event.id);

  return (
    <div className={`rounded border px-3 py-2 transition-colors ${
      enabled
        ? 'border-border bg-background'
        : 'border-border/30 bg-muted/30 opacity-60'
    }`}>
      <div className="flex items-center gap-2">
        {!readOnly && (
          <input
            type="checkbox"
            checked={enabled}
            onChange={e => onToggle(e.target.checked)}
            className="h-3.5 w-3.5 rounded border-border accent-primary"
          />
        )}
        <button
          className="flex items-center gap-1 flex-1 text-left"
          onClick={() => setExpanded(!expanded)}
        >
          {expanded ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
          <span className="text-xs font-medium truncate">{event.event}</span>
        </button>
        <div className="flex items-center gap-1">
          <span className="text-[10px] text-muted-foreground">p=</span>
          {readOnly ? (
            <span className="text-[10px] tabular-nums">{event.probability.toFixed(2)}</span>
          ) : (
            <input
              type="number"
              min={0}
              max={1}
              step={0.05}
              value={event.probability}
              onChange={e => onChangeProbability(parseFloat(e.target.value) || 0)}
              className="w-12 h-5 text-[10px] tabular-nums text-right border rounded px-1 bg-background"
            />
          )}
        </div>
        <span className="text-[9px] text-muted-foreground/70 px-1 py-0.5 rounded bg-muted/50 font-mono">
          {event.category}
        </span>
      </div>

      {expanded && (
        <div className="mt-2 pl-6 space-y-1">
          {event.timing && (
            <div className="text-[10px] text-muted-foreground">Timing: {event.timing}</div>
          )}
          {event.reasoning && (
            <div className="text-[10px] text-muted-foreground">{event.reasoning}</div>
          )}
          {outgoing.length > 0 && (
            <div className="mt-1 space-y-0.5">
              <div className="text-[10px] font-medium text-muted-foreground">Ripple:</div>
              {outgoing.map((link, i) => (
                <div key={i} className="text-[10px] text-muted-foreground flex items-center gap-1 pl-2">
                  <span>&rarr;</span>
                  <span className="font-mono">{link.target}</span>
                  <span>({link.effect}{link.magnitude != null && `, ${link.magnitude > 0 ? '+' : ''}${link.magnitude}`})</span>
                  {link.delay_months != null && link.delay_months > 0 && (
                    <span className="text-muted-foreground/50">[{link.delay_months}mo]</span>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main editor
// ---------------------------------------------------------------------------

export function ModelSpecEditor({
  eventChain,
  onToggleEvent,
  onChangeProbability,
  onRePrompt,
  onRun,
  loading = false,
  readOnly = false,
}: ModelSpecEditorProps) {
  const [rePromptInput, setRePromptInput] = useState('');
  const [disabledEvents, setDisabledEvents] = useState<Set<string>>(new Set());

  const handleToggle = useCallback((eventId: string, enabled: boolean) => {
    setDisabledEvents(prev => {
      const next = new Set(prev);
      if (enabled) next.delete(eventId);
      else next.add(eventId);
      return next;
    });
    onToggleEvent(eventId, enabled);
  }, [onToggleEvent]);

  const handleRePrompt = useCallback(() => {
    if (!rePromptInput.trim()) return;
    onRePrompt(rePromptInput.trim());
    setRePromptInput('');
  }, [rePromptInput, onRePrompt]);

  if (!eventChain || eventChain.events.length === 0) {
    return (
      <div className="space-y-3">
        <div className="text-[11px] text-muted-foreground text-center py-4">
          No event chain yet. Enter a prompt above and run to see events.
        </div>
        {!readOnly && (
          <div className="flex items-center gap-2">
            <div className="relative flex-1">
              <MessageSquare className="absolute left-2 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
              <Input
                className="h-8 pl-7 text-sm"
                placeholder="Build me a 24-month forecast with Series A..."
                value={rePromptInput}
                onChange={e => setRePromptInput(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && handleRePrompt()}
                disabled={loading}
              />
            </div>
            <Button
              variant="outline"
              size="sm"
              className="h-8 text-[11px] gap-1"
              onClick={handleRePrompt}
              disabled={loading || !rePromptInput.trim()}
            >
              {loading ? <Loader2 className="h-3 w-3 animate-spin" /> : <Play className="h-3 w-3" />}
              Run
            </Button>
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <div className="text-[11px] font-medium text-muted-foreground uppercase tracking-wide">
        Events ({eventChain.events.length})
      </div>

      {/* Event cards */}
      <div className="space-y-1.5">
        {eventChain.events.map(evt => (
          <EventCard
            key={evt.id}
            event={evt}
            links={eventChain.links}
            enabled={!disabledEvents.has(evt.id)}
            onToggle={(en) => handleToggle(evt.id, en)}
            onChangeProbability={(p) => onChangeProbability(evt.id, p)}
            readOnly={readOnly}
          />
        ))}
      </div>

      {/* Param origins */}
      {eventChain.param_origins && Object.keys(eventChain.param_origins).length > 0 && (
        <div className="mt-3 pt-2 border-t border-border/30">
          <div className="text-[10px] font-medium text-muted-foreground mb-1">Parameter origins</div>
          <div className="grid grid-cols-2 gap-x-4 gap-y-0.5">
            {Object.entries(eventChain.param_origins).map(([param, origins]) => (
              <div key={param} className="text-[10px] text-muted-foreground truncate">
                <span className="font-mono">{param}</span>
                <span className="mx-1">&larr;</span>
                <span>{origins.join(', ')}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Re-prompt + Run */}
      {!readOnly && (
        <div className="flex items-center gap-2 pt-2 border-t border-border/30">
          <div className="relative flex-1">
            <Plus className="absolute left-2 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
            <Input
              className="h-7 pl-7 text-xs"
              placeholder="Add event or adjust..."
              value={rePromptInput}
              onChange={e => setRePromptInput(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleRePrompt()}
              disabled={loading}
            />
          </div>
          <Button
            variant="outline"
            size="sm"
            className="h-7 text-[11px] gap-1"
            onClick={onRun}
            disabled={loading}
          >
            {loading ? <Loader2 className="h-3 w-3 animate-spin" /> : <Play className="h-3 w-3" />}
            Run
          </Button>
        </div>
      )}
    </div>
  );
}
