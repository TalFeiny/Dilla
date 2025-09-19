// Polyfill for EventTarget if not available
if (typeof globalThis !== 'undefined') {
  // @ts-ignore
  if (!globalThis.EventTarget) {
    // @ts-ignore
    globalThis.EventTarget = class EventTargetPolyfill {
      private listeners: Map<string, Function[]> = new Map();
      
      addEventListener(type: string, listener: Function) {
        if (!this.listeners.has(type)) {
          this.listeners.set(type, []);
        }
        this.listeners.get(type)?.push(listener);
      }
      
      removeEventListener(type: string, listener: Function) {
        const listeners = this.listeners.get(type);
        if (listeners) {
          const index = listeners.indexOf(listener);
          if (index !== -1) {
            listeners.splice(index, 1);
          }
        }
      }
      
      dispatchEvent(event: any) {
        const listeners = this.listeners.get(event.type);
        if (listeners) {
          listeners.forEach(listener => listener(event));
        }
        return true;
      }
    };
  }
}

// Ensure Target is defined for Safari/older browsers
if (typeof window !== 'undefined' && typeof (window as any).Target === 'undefined') {
  (window as any).Target = (window as any).EventTarget || {};
}

export {};