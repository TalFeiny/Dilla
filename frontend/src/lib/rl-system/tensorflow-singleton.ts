'use client';

let tf: any = null;
let initialized = false;

export async function getTensorFlow() {
  if (!tf && typeof window !== 'undefined') {
    // Only import TensorFlow once on the client side
    if (!initialized) {
      initialized = true;
      try {
        const tfModule = await import('@tensorflow/tfjs');
        tf = tfModule;
        console.log('TensorFlow.js initialized');
      } catch (error) {
        console.error('Failed to load TensorFlow.js:', error);
      }
    }
  }
  return tf;
}

export function getTensorFlowSync() {
  return tf;
}