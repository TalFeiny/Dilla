/**
 * Chart Data Fixer Utility
 * Attempts to repair and normalize malformed chart data structures
 */

export interface FixedChartData {
  type: string;
  data: any;
  title?: string;
  fixed: boolean;
  fixes: string[];
}

/**
 * Fix heatmap data structure
 * Handles: {dimensions, companies, scores} or [{x, y, value}]
 */
export function fixHeatmapData(rawData: any): FixedChartData {
  const fixes: string[] = [];
  let data = rawData;

  // If data is null/undefined, return empty structure
  if (!data) {
    return {
      type: 'heatmap',
      data: { dimensions: [], companies: [], scores: [] },
      fixed: false,
      fixes: ['Data was null/undefined']
    };
  }

  // If it's already in backend format {dimensions, companies, scores}
  if (data.dimensions && data.companies && data.scores) {
    // Ensure arrays are actually arrays
    if (!Array.isArray(data.dimensions)) {
      fixes.push('Converted dimensions to array');
      data.dimensions = Array.isArray(data.dimensions) ? data.dimensions : [];
    }
    if (!Array.isArray(data.companies)) {
      fixes.push('Converted companies to array');
      data.companies = Array.isArray(data.companies) ? data.companies : [];
    }
    if (!Array.isArray(data.scores)) {
      fixes.push('Converted scores to array');
      data.scores = Array.isArray(data.scores) ? data.scores : [];
    }
    return { type: 'heatmap', data, fixed: fixes.length > 0, fixes };
  }

  // If it's in frontend format [{x, y, value}]
  if (Array.isArray(data)) {
    if (data.length > 0 && (data[0].x !== undefined || data[0].y !== undefined)) {
      return { type: 'heatmap', data, fixed: false, fixes: [] };
    }
  }

  // Try to extract from nested structure
  if (data.data && (data.data.dimensions || Array.isArray(data.data))) {
    fixes.push('Extracted data from nested structure');
    return fixHeatmapData(data.data);
  }

  // If we have raw scores but missing structure, try to reconstruct
  if (data.scores && Array.isArray(data.scores)) {
    fixes.push('Reconstructed dimensions and companies from scores');
    const dimensions = data.dimensions || [];
    const companies = data.companies || [];
    
    // If we have scores but missing dimensions/companies, create defaults
    if (dimensions.length === 0 && companies.length === 0 && data.scores.length > 0) {
      // Try to infer from scores structure
      const firstScore = data.scores[0];
      if (Array.isArray(firstScore)) {
        // Assume scores is a 2D array
        const numDimensions = firstScore.length;
        const numCompanies = data.scores.length;
        return {
          type: 'heatmap',
          data: {
            dimensions: Array.from({ length: numDimensions }, (_, i) => `Dimension ${i + 1}`),
            companies: Array.from({ length: numCompanies }, (_, i) => `Company ${i + 1}`),
            scores: data.scores
          },
          fixed: true,
          fixes: [...fixes, 'Inferred dimensions and companies from scores structure']
        };
      }
    }
    
    return {
      type: 'heatmap',
      data: { dimensions, companies, scores: data.scores },
      fixed: true,
      fixes
    };
  }

  return {
    type: 'heatmap',
    data: { dimensions: [], companies: [], scores: [] },
    fixed: false,
    fixes: [...fixes, 'Could not fix heatmap data structure']
  };
}

/**
 * Fix line chart data structure
 * Handles: {labels: [], datasets: [{label, data: []}]}
 */
export function fixLineChartData(rawData: any): FixedChartData {
  const fixes: string[] = [];
  let data = rawData;

  if (!data) {
    return {
      type: 'line',
      data: { labels: [], datasets: [] },
      fixed: false,
      fixes: ['Data was null/undefined']
    };
  }

  // If already in correct format, validate and fix arrays
  if (data.labels || data.datasets) {
    const labels = Array.isArray(data.labels) ? data.labels : (data.labels ? [data.labels] : []);
    const datasets = Array.isArray(data.datasets) ? data.datasets : (data.datasets ? [data.datasets] : []);

    // Fix each dataset
    const fixedDatasets = datasets.map((dataset: any, idx: number) => {
      if (!dataset) return { label: `Series ${idx + 1}`, data: [] };
      
      const label = dataset.label || `Series ${idx + 1}`;
      let datasetData = dataset.data;
      
      if (!Array.isArray(datasetData)) {
        fixes.push(`Fixed dataset ${idx + 1} data to array`);
        datasetData = datasetData !== undefined ? [datasetData] : [];
      }
      
      return { ...dataset, label, data: datasetData };
    });

    if (labels.length !== data.labels?.length || datasets.length !== data.datasets?.length) {
      fixes.push('Normalized labels and datasets arrays');
    }

    return {
      type: 'line',
      data: { labels, datasets: fixedDatasets },
      fixed: fixes.length > 0,
      fixes
    };
  }

  // Try to extract from nested structure
  if (data.data) {
    fixes.push('Extracted data from nested structure');
    return fixLineChartData(data.data);
  }

  // If data is an array of objects, try to convert
  if (Array.isArray(data)) {
    if (data.length > 0 && typeof data[0] === 'object') {
      fixes.push('Converted array of objects to line chart format');
      // Try to infer labels from first object keys
      const firstObj = data[0];
      const keys = Object.keys(firstObj).filter(k => k !== 'name' && k !== 'label');
      const labels = data.map((item: any) => item.name || item.label || String(item));
      const datasets = keys.map((key, idx) => ({
        label: key,
        data: data.map((item: any) => {
          const val = item[key];
          return typeof val === 'number' ? val : parseFloat(val) || 0;
        })
      }));

      return {
        type: 'line',
        data: { labels, datasets },
        fixed: true,
        fixes
      };
    }
  }

  // If it's a single array of numbers, create a simple line chart
  if (Array.isArray(data) && data.length > 0 && typeof data[0] === 'number') {
    fixes.push('Converted number array to line chart format');
    return {
      type: 'line',
      data: {
        labels: data.map((_, i) => `Point ${i + 1}`),
        datasets: [{ label: 'Value', data }]
      },
      fixed: true,
      fixes
    };
  }

  return {
    type: 'line',
    data: { labels: [], datasets: [] },
    fixed: false,
    fixes: [...fixes, 'Could not fix line chart data structure']
  };
}

/**
 * Fix probability cloud data structure
 * Handles: {scenario_curves: [...]}
 */
export function fixProbabilityCloudData(rawData: any): FixedChartData {
  const fixes: string[] = [];
  let data = rawData;

  if (!data) {
    return {
      type: 'probability_cloud',
      data: { scenario_curves: [] },
      fixed: false,
      fixes: ['Data was null/undefined']
    };
  }

  // If already has scenario_curves
  if (data.scenario_curves) {
    if (!Array.isArray(data.scenario_curves)) {
      fixes.push('Converted scenario_curves to array');
      data.scenario_curves = [data.scenario_curves];
    }
    return { type: 'probability_cloud', data, fixed: fixes.length > 0, fixes };
  }

  // Try to extract from nested structure
  if (data.data) {
    if (data.data.scenario_curves) {
      fixes.push('Extracted scenario_curves from nested structure');
      return fixProbabilityCloudData(data.data);
    }
  }

  // If data is an array, assume it's scenario_curves
  if (Array.isArray(data)) {
    fixes.push('Converted array to scenario_curves');
    return {
      type: 'probability_cloud',
      data: { scenario_curves: data },
      fixed: true,
      fixes
    };
  }

  // If it's an object with array-like properties, try to find curves
  if (typeof data === 'object') {
    const keys = Object.keys(data);
    const arrayKey = keys.find(k => Array.isArray(data[k]) && data[k].length > 0);
    if (arrayKey) {
      fixes.push(`Extracted ${arrayKey} as scenario_curves`);
      return {
        type: 'probability_cloud',
        data: { scenario_curves: data[arrayKey] },
        fixed: true,
        fixes
      };
    }
  }

  return {
    type: 'probability_cloud',
    data: { scenario_curves: [] },
    fixed: false,
    fixes: [...fixes, 'Could not fix probability cloud data structure']
  };
}

/**
 * Fix sankey data structure
 * Handles: {nodes: [], links: []}
 */
export function fixSankeyData(rawData: any): FixedChartData {
  const fixes: string[] = [];
  let data = rawData;

  if (!data) {
    return {
      type: 'sankey',
      data: { nodes: [], links: [] },
      fixed: false,
      fixes: ['Data was null/undefined']
    };
  }

  // If already has nodes and links
  if (data.nodes && data.links) {
    if (!Array.isArray(data.nodes)) {
      fixes.push('Converted nodes to array');
      data.nodes = [];
    }
    if (!Array.isArray(data.links)) {
      fixes.push('Converted links to array');
      data.links = [];
    }
    return { type: 'sankey', data, fixed: fixes.length > 0, fixes };
  }

  // Try to extract from nested structure
  if (data.data) {
    if (data.data.nodes || data.data.links) {
      fixes.push('Extracted nodes/links from nested structure');
      return fixSankeyData(data.data);
    }
  }

  // If data is an object with array properties, try to infer
  if (typeof data === 'object') {
    const keys = Object.keys(data);
    const nodesKey = keys.find(k => k.toLowerCase().includes('node'));
    const linksKey = keys.find(k => k.toLowerCase().includes('link') || k.toLowerCase().includes('edge'));
    
    if (nodesKey || linksKey) {
      fixes.push(`Mapped ${nodesKey || 'nodes'} and ${linksKey || 'links'}`);
      return {
        type: 'sankey',
        data: {
          nodes: nodesKey && Array.isArray(data[nodesKey]) ? data[nodesKey] : [],
          links: linksKey && Array.isArray(data[linksKey]) ? data[linksKey] : []
        },
        fixed: true,
        fixes
      };
    }
  }

  return {
    type: 'sankey',
    data: { nodes: [], links: [] },
    fixed: false,
    fixes: [...fixes, 'Could not fix sankey data structure']
  };
}

/**
 * Fix bar chart data structure (similar to line chart)
 */
export function fixBarChartData(rawData: any): FixedChartData {
  const result = fixLineChartData(rawData);
  return { ...result, type: 'bar' };
}

/**
 * Main fixer function that routes to appropriate fixer based on chart type
 */
export function fixChartData(chartType: string, rawData: any): FixedChartData {
  if (!rawData) {
    return {
      type: chartType,
      data: null,
      fixed: false,
      fixes: ['Data was null/undefined']
    };
  }

  switch (chartType) {
    case 'heatmap':
      return fixHeatmapData(rawData);
    case 'line':
      return fixLineChartData(rawData);
    case 'bar':
      return fixBarChartData(rawData);
    case 'probability_cloud':
      return fixProbabilityCloudData(rawData);
    case 'sankey':
      return fixSankeyData(rawData);
    default:
      // Generic fix: try to ensure data is an object/array
      if (typeof rawData === 'object' && rawData !== null) {
        return { type: chartType, data: rawData, fixed: false, fixes: [] };
      }
      return {
        type: chartType,
        data: null,
        fixed: false,
        fixes: [`Unknown chart type: ${chartType}`]
      };
  }
}

/**
 * Fix chart_data object that might have type and data properties
 */
export function fixChartDataObject(chartData: any): { type: string; data: any; title?: string; fixed: boolean; fixes: string[] } | null {
  if (!chartData) return null;

  const fixes: string[] = [];
  let type = chartData.type;
  let data = chartData.data;
  let title = chartData.title;

  // If type is missing, try to infer from data structure
  if (!type) {
    if (data?.scenario_curves) {
      type = 'probability_cloud';
      fixes.push('Inferred type as probability_cloud from data structure');
    } else if (data?.nodes && data?.links) {
      type = 'sankey';
      fixes.push('Inferred type as sankey from data structure');
    } else if (data?.dimensions && data?.companies && data?.scores) {
      type = 'heatmap';
      fixes.push('Inferred type as heatmap from data structure');
    } else if (data?.labels && data?.datasets) {
      type = 'line';
      fixes.push('Inferred type as line from data structure');
    }
  }

  // If we have a type but data is malformed, try to fix it
  if (type && data) {
    const fixed = fixChartData(type, data);
    if (fixed.fixed) {
      fixes.push(...fixed.fixes);
      data = fixed.data;
    }
  }

  return {
    type: type || 'bar',
    data,
    title,
    fixed: fixes.length > 0,
    fixes
  };
}

