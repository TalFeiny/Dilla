/**
 * Chart.js Setup and Registration
 * REQUIRED for Chart.js v4+ to work
 * Ensures registration happens client-side only
 */

import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  LineElement,
  PointElement,
  ArcElement,
  RadialLinearScale,
  Title,
  Tooltip,
  Legend,
  Filler,
} from 'chart.js';

// Track if Chart.js has been registered
let isRegistered = false;

// Register Chart.js components (client-side only)
if (typeof window !== 'undefined') {
  try {
    if (!isRegistered) {
      ChartJS.register(
        CategoryScale,
        LinearScale,
        BarElement,
        LineElement,
        PointElement,
        ArcElement,
        RadialLinearScale,
        Title,
        Tooltip,
        Legend,
        Filler
      );
      isRegistered = true;
      console.log('[Chart Setup] Chart.js components registered successfully');
    }
  } catch (error) {
    console.error('[Chart Setup] Error registering Chart.js components:', error);
  }
} else {
  // Server-side: register anyway (might be needed for SSR)
  if (!isRegistered) {
    ChartJS.register(
      CategoryScale,
      LinearScale,
      BarElement,
      LineElement,
      PointElement,
      ArcElement,
      RadialLinearScale,
      Title,
      Tooltip,
      Legend,
      Filler
    );
    isRegistered = true;
  }
}

// Export for use in other files if needed
export { ChartJS };

// Export function to ensure registration (useful for dynamic imports)
export function ensureChartJSRegistered() {
  if (typeof window === 'undefined') return;
  
  if (!isRegistered) {
    try {
      ChartJS.register(
        CategoryScale,
        LinearScale,
        BarElement,
        LineElement,
        PointElement,
        ArcElement,
        RadialLinearScale,
        Title,
        Tooltip,
        Legend,
        Filler
      );
      isRegistered = true;
      console.log('[Chart Setup] Chart.js components registered via ensureChartJSRegistered');
    } catch (error) {
      console.error('[Chart Setup] Error in ensureChartJSRegistered:', error);
    }
  }
}
