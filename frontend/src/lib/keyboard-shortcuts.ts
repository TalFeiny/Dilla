import { useHotkeys } from 'react-hotkeys-hook'
import { useCallback, RefObject } from 'react'

/**
 * Global keyboard shortcuts
 */

export function useSaveShortcut(onSave: () => void, enabled = true) {
  useHotkeys(
    'mod+s',
    (e) => {
      e.preventDefault()
      onSave()
    },
    { enabled, preventDefault: true }
  )
}

export function useCommandPaletteShortcut(onOpen: () => void, enabled = true) {
  useHotkeys(
    'mod+k',
    (e) => {
      e.preventDefault()
      onOpen()
    },
    { enabled, preventDefault: true }
  )
}

/**
 * Table keyboard shortcuts
 * For navigating and editing tables
 */
export function useTableKeyboard(
  options: {
    onArrowUp?: () => void
    onArrowDown?: () => void
    onArrowLeft?: () => void
    onArrowRight?: () => void
    onEnter?: () => void
    onEscape?: () => void
    onDelete?: () => void
    enabled?: boolean
    scope?: RefObject<HTMLElement>
  } = {}
) {
  const {
    onArrowUp,
    onArrowDown,
    onArrowLeft,
    onArrowRight,
    onEnter,
    onEscape,
    onDelete,
    enabled = true,
    scope,
  } = options

  useHotkeys(
    'arrowup',
    (e) => {
      e.preventDefault()
      onArrowUp?.()
    },
    { enabled, enableOnContentEditable: true }
  )

  useHotkeys(
    'arrowdown',
    (e) => {
      e.preventDefault()
      onArrowDown?.()
    },
    { enabled, enableOnContentEditable: true }
  )

  useHotkeys(
    'arrowleft',
    (e) => {
      e.preventDefault()
      onArrowLeft?.()
    },
    { enabled, enableOnContentEditable: true }
  )

  useHotkeys(
    'arrowright',
    (e) => {
      e.preventDefault()
      onArrowRight?.()
    },
    { enabled, enableOnContentEditable: true }
  )

  useHotkeys(
    'enter',
    (e) => {
      e.preventDefault()
      onEnter?.()
    },
    { enabled, enableOnContentEditable: true }
  )

  useHotkeys(
    'escape',
    (e) => {
      e.preventDefault()
      onEscape?.()
    },
    { enabled, enableOnContentEditable: true }
  )

  useHotkeys(
    'delete',
    (e) => {
      e.preventDefault()
      onDelete?.()
    },
    { enabled, enableOnContentEditable: true }
  )
}

/**
 * Document-specific shortcuts
 */
export function useDocumentShortcuts(
  options: {
    onSave?: () => void
    onExport?: () => void
    onClose?: () => void
    enabled?: boolean
  } = {}
) {
  const { onSave, onExport, onClose, enabled = true } = options

  useSaveShortcut(() => onSave?.(), enabled && !!onSave)
  
  useHotkeys(
    'mod+e',
    (e) => {
      e.preventDefault()
      onExport?.()
    },
    { enabled: enabled && !!onExport, preventDefault: true }
  )

  useHotkeys(
    'mod+w',
    (e) => {
      e.preventDefault()
      onClose?.()
    },
    { enabled: enabled && !!onClose, preventDefault: true }
  )
}

/**
 * Unified keyboard shortcuts hook
 * Combines multiple shortcut types
 */
export function useKeyboardShortcuts(
  config: {
    save?: () => void
    commandPalette?: () => void
    table?: {
      onArrowUp?: () => void
      onArrowDown?: () => void
      onArrowLeft?: () => void
      onArrowRight?: () => void
      onEnter?: () => void
      onEscape?: () => void
      onDelete?: () => void
      scope?: RefObject<HTMLElement>
    }
    document?: {
      onSave?: () => void
      onExport?: () => void
      onClose?: () => void
    }
    enabled?: boolean
  } = {}
) {
  const { save, commandPalette, table, document, enabled = true } = config

  useSaveShortcut(() => save?.(), enabled && !!save)
  useCommandPaletteShortcut(() => commandPalette?.(), enabled && !!commandPalette)
  
  if (table) {
    useTableKeyboard({ ...table, enabled })
  }
  
  if (document) {
    useDocumentShortcuts({ ...document, enabled })
  }
}
