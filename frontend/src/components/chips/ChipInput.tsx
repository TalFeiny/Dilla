'use client';

import React, {
  useRef,
  useCallback,
  useEffect,
  forwardRef,
  useImperativeHandle,
  KeyboardEvent,
} from 'react';
import { nanoid } from 'nanoid';
import type { ChipDef, ActiveChip as ActiveChipType, InputSegment } from '@/lib/chips/types';
import { CHIP_BY_ID } from '@/lib/chips/registry';
import { DOMAIN_COLORS } from './Chip';
import { cn } from '@/lib/utils';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface ChipInputRef {
  /** Insert a chip at the current cursor position */
  insertChip: (def: ChipDef) => void;
  /** Get the current content as InputSegments */
  getSegments: () => InputSegment[];
  /** Clear all content */
  clear: () => void;
  /** Focus the input */
  focus: () => void;
  /** Check if the input has any content */
  hasContent: () => boolean;
}

interface ChipInputProps {
  /** Called when user presses Enter (without Shift) */
  onSubmit: (segments: InputSegment[]) => void;
  /** Called whenever content changes */
  onChange?: (segments: InputSegment[]) => void;
  placeholder?: string;
  disabled?: boolean;
  className?: string;
  /** Min/max height */
  minHeight?: number;
  maxHeight?: number;
}

// ---------------------------------------------------------------------------
// Marker for chip elements in the contentEditable
// ---------------------------------------------------------------------------

const CHIP_ATTR = 'data-chip-id';
const CHIP_INSTANCE_ATTR = 'data-chip-instance';

function createChipElement(def: ChipDef, instanceId: string, values: Record<string, any>): HTMLSpanElement {
  const el = document.createElement('span');
  el.setAttribute(CHIP_ATTR, def.id);
  el.setAttribute(CHIP_INSTANCE_ATTR, instanceId);
  el.setAttribute('data-chip-values', JSON.stringify(values));
  el.contentEditable = 'false';
  el.className = chipClassName(def.domain);

  // Build label with param display
  const paramParts = def.params
    .map((p) => {
      const val = values[p.key] ?? p.default;
      if (p.chipDisplay) return p.chipDisplay(val);
      if (p.type === 'percent') return `${val}%`;
      if (p.type === 'select') {
        const opt = p.options?.find((o) => o.value === val);
        return opt?.label ?? val;
      }
      if (val === '' || val === p.default) return null;
      return String(val);
    })
    .filter(Boolean);

  el.textContent = def.label + (paramParts.length ? ' ' + paramParts.join(' ') : '');
  el.title = def.description;

  // Click to configure (will be handled by parent)
  el.style.cursor = 'pointer';

  return el;
}

function chipClassName(domain: string): string {
  const colors = DOMAIN_COLORS[domain] ?? DOMAIN_COLORS.data;
  return [
    'inline-flex items-center rounded-full border px-1.5 py-px mx-0.5',
    'text-[11px] font-medium leading-tight select-none whitespace-nowrap',
    'align-middle',
    colors.bg, colors.text, colors.border,
  ].join(' ');
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * ChipInput — a contentEditable div that supports inline chip badges mixed with text.
 * Chips are non-editable inline elements. Text flows around them naturally.
 * Drop chips from the tray, or click tray chips to insert at cursor.
 */
export const ChipInput = forwardRef<ChipInputRef, ChipInputProps>(function ChipInput(
  { onSubmit, onChange, placeholder, disabled, className, minHeight = 36, maxHeight = 120 },
  ref,
) {
  const editorRef = useRef<HTMLDivElement>(null);

  // -------------------------------------------------------------------------
  // Parse the DOM content into InputSegments
  // -------------------------------------------------------------------------

  const getSegments = useCallback((): InputSegment[] => {
    const el = editorRef.current;
    if (!el) return [];

    const segments: InputSegment[] = [];

    for (const node of Array.from(el.childNodes)) {
      if (node.nodeType === Node.TEXT_NODE) {
        const text = node.textContent ?? '';
        if (text) segments.push({ type: 'text', text });
      } else if (node instanceof HTMLElement && node.hasAttribute(CHIP_ATTR)) {
        const chipId = node.getAttribute(CHIP_ATTR)!;
        const instanceId = node.getAttribute(CHIP_INSTANCE_ATTR)!;
        const values = JSON.parse(node.getAttribute('data-chip-values') || '{}');
        const def = CHIP_BY_ID[chipId];
        if (def) {
          segments.push({
            type: 'chip',
            chip: { instanceId, def, values },
          });
        }
      } else if (node.nodeType === Node.ELEMENT_NODE) {
        // BR or other inline elements → treat as text
        const text = node.textContent ?? '';
        if (text) segments.push({ type: 'text', text });
      }
    }

    return segments;
  }, []);

  const hasContent = useCallback(() => {
    const el = editorRef.current;
    if (!el) return false;
    return el.textContent?.trim() !== '' || el.querySelector(`[${CHIP_ATTR}]`) !== null;
  }, []);

  const clear = useCallback(() => {
    if (editorRef.current) {
      editorRef.current.innerHTML = '';
    }
  }, []);

  const focus = useCallback(() => {
    editorRef.current?.focus();
  }, []);

  // -------------------------------------------------------------------------
  // Insert a chip at the current cursor position
  // -------------------------------------------------------------------------

  const insertChip = useCallback((def: ChipDef) => {
    const el = editorRef.current;
    if (!el) return;

    const instanceId = nanoid(8);
    const defaults: Record<string, any> = {};
    for (const p of def.params) {
      defaults[p.key] = p.default;
    }

    const chipEl = createChipElement(def, instanceId, defaults);

    // Insert at cursor or at end
    const sel = window.getSelection();
    if (sel && sel.rangeCount > 0 && el.contains(sel.anchorNode)) {
      const range = sel.getRangeAt(0);
      range.deleteContents();
      range.insertNode(chipEl);
      // Move cursor after the chip
      range.setStartAfter(chipEl);
      range.setEndAfter(chipEl);
      sel.removeAllRanges();
      sel.addRange(range);
    } else {
      // No selection in editor — append at end
      el.appendChild(chipEl);
    }

    // Add a space after the chip for natural typing
    const space = document.createTextNode('\u00A0');
    chipEl.after(space);

    // Move cursor after space
    const newRange = document.createRange();
    newRange.setStartAfter(space);
    newRange.setEndAfter(space);
    const newSel = window.getSelection();
    newSel?.removeAllRanges();
    newSel?.addRange(newRange);

    el.focus();
    onChange?.(getSegments());
  }, [onChange, getSegments]);

  // -------------------------------------------------------------------------
  // Imperative handle
  // -------------------------------------------------------------------------

  useImperativeHandle(ref, () => ({
    insertChip,
    getSegments,
    clear,
    focus,
    hasContent,
  }), [insertChip, getSegments, clear, focus, hasContent]);

  // -------------------------------------------------------------------------
  // Keyboard handling
  // -------------------------------------------------------------------------

  const handleKeyDown = useCallback((e: KeyboardEvent<HTMLDivElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (hasContent()) {
        onSubmit(getSegments());
      }
    }
  }, [onSubmit, getSegments, hasContent]);

  // -------------------------------------------------------------------------
  // Drop handling (chips dragged from tray)
  // -------------------------------------------------------------------------

  const handleDragOver = useCallback((e: React.DragEvent) => {
    if (e.dataTransfer.types.includes('application/chip-id')) {
      e.preventDefault();
      e.dataTransfer.dropEffect = 'copy';
    }
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    const chipId = e.dataTransfer.getData('application/chip-id');
    if (!chipId) return;
    e.preventDefault();

    const def = CHIP_BY_ID[chipId];
    if (!def) return;

    // Place cursor at drop position
    const el = editorRef.current;
    if (el) {
      const range = document.caretRangeFromPoint?.(e.clientX, e.clientY);
      if (range) {
        const sel = window.getSelection();
        sel?.removeAllRanges();
        sel?.addRange(range);
      }
    }

    insertChip(def);
  }, [insertChip]);

  // -------------------------------------------------------------------------
  // Input event (for onChange)
  // -------------------------------------------------------------------------

  const handleInput = useCallback(() => {
    onChange?.(getSegments());
  }, [onChange, getSegments]);

  // -------------------------------------------------------------------------
  // Placeholder handling
  // -------------------------------------------------------------------------

  const [showPlaceholder, setShowPlaceholder] = React.useState(true);

  const updatePlaceholder = useCallback(() => {
    setShowPlaceholder(!hasContent());
  }, [hasContent]);

  useEffect(() => {
    const el = editorRef.current;
    if (!el) return;
    const observer = new MutationObserver(updatePlaceholder);
    observer.observe(el, { childList: true, characterData: true, subtree: true });
    return () => observer.disconnect();
  }, [updatePlaceholder]);

  // -------------------------------------------------------------------------
  // Render
  // -------------------------------------------------------------------------

  return (
    <div className="relative flex-1 min-w-0">
      {showPlaceholder && placeholder && (
        <div
          className="absolute inset-0 flex items-center px-3 text-xs text-muted-foreground pointer-events-none select-none"
          aria-hidden
        >
          {placeholder}
        </div>
      )}
      <div
        ref={editorRef}
        contentEditable={!disabled}
        suppressContentEditableWarning
        onKeyDown={handleKeyDown}
        onDragOver={handleDragOver}
        onDrop={handleDrop}
        onInput={handleInput}
        onFocus={updatePlaceholder}
        onBlur={updatePlaceholder}
        role="textbox"
        aria-multiline="true"
        aria-placeholder={placeholder}
        className={cn(
          'w-full rounded-lg px-3 py-2 text-sm',
          'border-0 bg-transparent',
          'focus-visible:outline-none',
          'overflow-y-auto',
          'whitespace-pre-wrap break-words',
          '[&_[data-chip-id]]:inline-flex [&_[data-chip-id]]:align-baseline',
          disabled && 'opacity-50 cursor-not-allowed',
          className,
        )}
        style={{ minHeight, maxHeight }}
      />
    </div>
  );
});
