'use client';

import { useState, useEffect, useRef } from 'react';
import { Bot, Play, Loader2, Trash2, Copy, Check, Brain, TrendingUp, BarChart3 } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useGrid } from '@/contexts/GridContext';
import AgentChartGenerator from '@/components/AgentChartGenerator';

// Helper function to convert grid data to commands
function convertGridDataToCommands(grid: any): string[] {
  const commands: string[] = [];
  
  // Convert data array to write commands
  if (grid.data && Array.isArray(grid.data)) {
    grid.data.forEach((row: any[], rowIndex: number) => {
      row.forEach((cell: any, colIndex: number) => {
        const cellAddress = String.fromCharCode(65 + colIndex) + (rowIndex + 1);
        let value = cell;
        
        // Format the value based on type
        if (typeof value === 'string') {
          value = `"${value}"`;
        } else if (typeof value === 'number') {
          // Keep numbers as is
        } else if (value === null || value === undefined) {
          value = '""';
        } else {
          value = `"${String(value)}"`;
        }
        
        commands.push(`grid.write("${cellAddress}", ${value})`);
      });
    });
  }
  
  // Add style commands for headers (first row)
  if (grid.data && grid.data.length > 0) {
    const headerCount = grid.data[0].length;
    for (let i = 0; i < headerCount; i++) {
      const cellAddress = String.fromCharCode(65 + i) + '1';
      commands.push(`grid.style("${cellAddress}", { fontWeight: "bold", backgroundColor: "#f0f0f0" })`);
    }
  }
  
  // Convert formulas object to formula commands
  if (grid.formulas && typeof grid.formulas === 'object') {
    Object.entries(grid.formulas).forEach(([cell, formula]) => {
      commands.push(`grid.formula("${cell}", "${formula}")`);
    });
  }
  
  // Convert charts array to chart commands - Process ALL charts in batch
  if (grid.charts && Array.isArray(grid.charts) && grid.charts.length > 0) {
    // Processing charts in batch mode
    
    // Create a batch chart command that processes all charts at once
    const chartBatch = grid.charts.map((chart: any, index: number) => {
      const chartType = chart.type || 'bar';
      
      // Build chart options object
      const options: any = {
        title: chart.title || `Chart ${index + 1}`,
        data: chart.data || {},
        colors: chart.colors || ["#4e79a7", "#f28e2c", "#e15759", "#76b7b2", "#59a14f"],
        position: chart.position || `A${10 + (index * 10)}`, // Stagger chart positions
        size: chart.size || { rows: 8, cols: 10 }
      };
      
      // Add range if available (for spreadsheet-based charts)
      if (chart.range) {
        options.range = chart.range;
      }
      
      return { type: chartType, options };
    });
    
    // Create a single batch command that creates all charts
    commands.push(`grid.createChartBatch(${JSON.stringify(chartBatch)})`);
  }
  
  return commands;
}

export default function AgentRunner() {
  const [prompt, setPrompt] = useState('');
  const [isRunning, setIsRunning] = useState(false);
  const [lastCommands, setLastCommands] = useState<string[]>([]);
  const [copied, setCopied] = useState(false);
  const [progressMessage, setProgressMessage] = useState<string>('');
  const [executionSteps, setExecutionSteps] = useState<string[]>([]);
  
  // Get grid context for secure command execution
  const { executeCommand, executeBatch } = useGrid();
  
  // State variables
  const [currentCompany, setCurrentCompany] = useState<string | undefined>(undefined);
  const [previousGridState, setPreviousGridState] = useState<any>(null);
  const [sessionId, setSessionId] = useState<string | undefined>(undefined);
  const [feedbackSent, setFeedbackSent] = useState(false);
  const [semanticFeedback, setSemanticFeedback] = useState('');
  const [waitingForFeedback, setWaitingForFeedback] = useState(false);
  const [citations, setCitations] = useState<any[]>([]);
  const [charts, setCharts] = useState<any[]>([]);
  const [showCharts, setShowCharts] = useState(false);
  
  // Placeholder variables for removed RL features
  const useRL = false;
  const rlStats: any = null;
  const rlSystemRef = { current: null };
  const learningApplied = false;
  const learningSummary = '';
  

  const runAgent = async () => {
    if (!prompt.trim()) return;
    
    // TEST MODE: If prompt starts with "test", use mock data
    if (prompt.toLowerCase().startsWith('test')) {
      console.log('[AgentRunner] TEST MODE ACTIVATED - Using mock data');
      setIsRunning(true);
      setProgressMessage('Running test with mock data...');
      
      // Create test commands
      const testCommands = [
        'grid.write("A1", "Company Name")',
        'grid.write("B1", "Revenue")',
        'grid.write("C1", "Growth")',
        'grid.write("D1", "Valuation")',
        'grid.write("A2", "TestCorp")',
        'grid.write("B2", 1000000)',
        'grid.write("C2", 0.25)',
        'grid.write("D2", 5000000)',
        'grid.formula("E1", "=B2*D2")',
        'grid.style("A1", {"fontWeight": "bold", "backgroundColor": "#f0f0f0"})',
        'grid.style("B1", {"fontWeight": "bold", "backgroundColor": "#f0f0f0"})',
        'grid.style("C1", {"fontWeight": "bold", "backgroundColor": "#f0f0f0"})',
        'grid.style("D1", {"fontWeight": "bold", "backgroundColor": "#f0f0f0"})'
      ];
      
      setLastCommands(testCommands);
      
      // Execute test commands
      for (const cmd of testCommands) {
        try {
          await executeCommand(cmd);
          console.log('[AgentRunner TEST] Executed:', cmd);
        } catch (e) {
          console.error('[AgentRunner TEST] Failed:', cmd, e);
        }
      }
      
      setIsRunning(false);
      setProgressMessage('Test complete - check if data appears correctly');
      return;
    }
    
    
    setIsRunning(true);
    setProgressMessage('🤔 Understanding your request...');
    setExecutionSteps([]);
    
    try {
      // Extract company name if mentioned
      const companyMatch = prompt.match(/(?:for|about)\s+(@?\w+)/i) || prompt.match(/@(\w+)/);
      const company = companyMatch?.[1] || currentCompany;
      setCurrentCompany(company);
      
      console.log('[AgentRunner] Extracted company from prompt:', company);
      console.log('[AgentRunner] Full prompt being sent:', prompt);
      
      // Show what we're doing
      setExecutionSteps(prev => [...prev, '📝 Parsing request...']);
      
      // Use unified-brain endpoint with our architecture
      const endpoint = '/api/agent/unified-brain';
      
      // Get current grid state to send as context
      let gridState = {};
      if (typeof window !== 'undefined' && (window as any).grid) {
        gridState = (window as any).grid.getState ? (window as any).grid.getState() : {};
      }
      
      // Update progress
      setProgressMessage('🔍 Researching data...');
      setExecutionSteps(prev => [...prev, '🌐 Fetching real-time data...']);
      
      // Call the streaming API
      const response = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          prompt,
          outputFormat: 'spreadsheet',  // Specify spreadsheet format
          company,
          previousCompany: currentCompany,
          gridState,  // Send current grid state for context
          stream: false,  // Disable streaming - prevents partial data issues
          // Request formulas and citations
          includeFormulas: true,
          includeCitations: true
        })
      });

      if (!response.ok) throw new Error('Failed to get agent response');
      
      // Handle JSON response
      const data = await response.json();
      
      if (data.success) {
        console.log('[AgentRunner] Received response:', data);
        
        // Extract commands from the response
        let commands: string[] = [];
        
        if (data.commands && Array.isArray(data.commands)) {
          commands = data.commands;
        } else if (data.result?.commands && Array.isArray(data.result.commands)) {
          commands = data.result.commands;
        } else if (data.results?.commands && Array.isArray(data.results.commands)) {
          commands = data.results.commands;
        }
        
        console.log('[AgentRunner] Extracted commands:', commands.length);
        
        if (commands.length > 0) {
          setLastCommands(commands);
          setProgressMessage('✅ Commands generated successfully');
          setExecutionSteps(prev => [...prev, `✅ Generated ${commands.length} commands`]);
          
          // Execute commands in the grid
          try {
            await executeBatch(commands);
            setProgressMessage('✅ Commands executed successfully');
            setExecutionSteps(prev => [...prev, '✅ All commands executed']);
          } catch (execError) {
            console.error('[AgentRunner] Command execution error:', execError);
            setProgressMessage('❌ Command execution failed');
            setExecutionSteps(prev => [...prev, `❌ Execution error: ${execError}`]);
          }
        } else {
          setProgressMessage('⚠️ No commands generated');
          setExecutionSteps(prev => [...prev, '⚠️ No commands found in response']);
        }
      } else {
        setProgressMessage('❌ Request failed');
        setExecutionSteps(prev => [...prev, `❌ Error: ${data.error || 'Unknown error'}`]);
      }
    } catch (error) {
      console.error('Agent error:', error);
      setProgressMessage('❌ Error occurred');
      setExecutionSteps(prev => [...prev, `Error: ${error}`]);
    } finally {
      setIsRunning(false);
      // Clear progress after 3 seconds
      setTimeout(() => {
        setProgressMessage('');
        setExecutionSteps([]);
      }, 3000);
    }
  };

  const copyCommands = () => {
    const text = lastCommands.join('\n');
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const clearGrid = () => {
    if (typeof window !== 'undefined' && (window as any).grid && (window as any).grid.clear) {
      (window as any).grid.clear('A1', 'Z100');
    }
  };

  const undoLastAction = () => {
    if (typeof window !== 'undefined' && (window as any).grid) {
      // Clear current state
      if ((window as any).grid.clear) {
        (window as any).grid.clear('A1', 'Z100');
      }
      
      // If we have a previous state, restore it
      if (previousGridState && (window as any).grid.setState) {
        (window as any).grid.setState(previousGridState);
        console.log('Restored previous grid state');
      }
      
      // Clear the last commands to hide feedback panel
      setLastCommands([]);
      setPreviousGridState(null);
    }
  };

  // Submit feedback to API (saves to Supabase)
  const submitFeedback = async (type: string, value?: string) => {
    try {
      console.log('Submitting feedback:', type, value);
      
      const response = await fetch('/api/agent/feedback', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          type,
          value,
          sessionId,
          timestamp: new Date().toISOString(),
        }),
      });

      if (response.ok) {
        if (type === 'semantic') {
          setSemanticFeedback('');
        }
        console.log('Feedback sent successfully');
      }
    } catch (error) {
      console.error('Failed to send feedback:', error);
    }
  };


  return (
    <div className="bg-gray-900 text-gray-100 p-4 rounded-lg space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Bot className="w-5 h-5 text-green-400" />
          <h3 className="font-bold">Agent Runner</h3>
        </div>
        <button
          onClick={clearGrid}
          className="px-3 py-1 bg-red-900 hover:bg-red-800 rounded text-sm flex items-center gap-1"
        >
          <Trash2 className="w-3 h-3" />
          Clear Grid
        </button>
      </div>

      {/* Progress Display */}
      {(progressMessage || executionSteps.length > 0) && (
        <div className="bg-gray-800 border border-gray-700 rounded p-3 space-y-2">
          {progressMessage && (
            <div className="text-sm font-medium text-green-400 flex items-center gap-2">
              {isRunning && <Loader2 className="w-4 h-4 animate-spin" />}
              {progressMessage}
            </div>
          )}
          {executionSteps.length > 0 && (
            <div className="space-y-1">
              {executionSteps.slice(-3).map((step, i) => (
                <div key={i} className="text-xs text-gray-400 pl-6">
                  {step}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Input */}
      <div className="flex gap-2">
        <input
          type="text"
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && !isRunning && runAgent()}
          placeholder="E.g., Create a DCF model with 10% discount rate"
          className="flex-1 px-3 py-2 bg-gray-800 border border-gray-700 rounded text-sm focus:outline-none focus:border-green-400"
          disabled={isRunning}
        />
        <button
          onClick={runAgent}
          disabled={isRunning || !prompt.trim()}
          className={cn(
            "px-4 py-2 rounded font-medium flex items-center gap-2",
            isRunning || !prompt.trim()
              ? "bg-gray-800 text-gray-500 cursor-not-allowed"
              : "bg-green-600 hover:bg-green-500 text-white"
          )}
        >
          {isRunning ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" />
              Running...
            </>
          ) : (
            <>
              <Play className="w-4 h-4" />
              Run Agent
            </>
          )}
        </button>
      </div>


      {/* Last Commands */}
      {lastCommands.length > 0 && (
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <div className="text-xs text-gray-400">Generated Commands:</div>
            <button
              onClick={copyCommands}
              className="px-2 py-1 bg-gray-800 hover:bg-gray-700 rounded text-xs flex items-center gap-1"
            >
              {copied ? (
                <>
                  <Check className="w-3 h-3 text-green-400" />
                  Copied!
                </>
              ) : (
                <>
                  <Copy className="w-3 h-3" />
                  Copy
                </>
              )}
            </button>
          </div>
          <div className="bg-gray-800 p-2 rounded text-xs font-mono max-h-32 overflow-auto">
            {lastCommands.map((cmd, i) => (
              <div key={i} className="text-green-400">
                {cmd}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Learning Applied Indicator */}
      {false /* learningApplied */ && (
        <div className="p-3 bg-green-900/30 border border-green-600/50 rounded animate-pulse">
          <div className="flex items-center gap-2 text-sm text-green-400">
            <Brain className="w-4 h-4" />
            <span className="font-semibold">🧠 LEARNING APPLIED!</span>
          </div>
          <p className="text-xs text-green-300 mt-1">{learningSummary}</p>
        </div>
      )}

      {/* RL Stats Display */}
      {false /* useRL && rlStats */ && (
        <div className="p-2 bg-gray-800 rounded space-y-1">
          <div className="flex items-center gap-2 text-xs text-gray-400">
            <Brain className="w-3 h-3" />
            <span>RL System Active</span>
          </div>
          <div className="grid grid-cols-3 gap-2 text-xs">
            <div>
              <span className="text-gray-500">Avg Reward:</span>
              <span className={cn(
                "ml-1 font-mono",
                rlStats.session?.avgReward > 0 ? "text-green-400" : "text-red-400"
              )}>
                {rlStats.session?.avgReward?.toFixed(2) || '0.00'}
              </span>
            </div>
            <div>
              <span className="text-gray-500">Exploration:</span>
              <span className="ml-1 font-mono text-blue-400">
                {((rlStats.agent?.epsilon || 0.1) * 100).toFixed(0)}%
              </span>
            </div>
            <div>
              <span className="text-gray-500">Buffer:</span>
              <span className="ml-1 font-mono text-yellow-400">
                {rlStats.session?.bufferSize || 0}
              </span>
            </div>
          </div>
          {rlStats.session?.lastReward !== undefined && (
            <div className="flex items-center gap-1 text-xs">
              <TrendingUp className={cn(
                "w-3 h-3",
                rlStats.session.lastReward > 0 ? "text-green-400" : "text-red-400"
              )} />
              <span className="text-gray-500">Last:</span>
              <span className={cn(
                "font-mono",
                rlStats.session.lastReward > 0 ? "text-green-400" : "text-red-400"
              )}>
                {rlStats.session.lastReward.toFixed(2)}
              </span>
            </div>
          )}
        </div>
      )}
      
      {/* RL Feedback Panel - Commented out as RLFeedbackPanel component is missing */}
      {/* {useRL && lastCommands.length > 0 && (
        <RLFeedbackPanel
          sessionId={sessionId}
          company={currentCompany}
          modelType={detectModelType(prompt)}
          commands={lastCommands}
          waitingForFeedback={waitingForFeedback}
          isEnabled={useRL}
          onFeedback={async (reward, specificFeedback) => {
            console.log('Feedback received:', reward, specificFeedback);
            if (rlSystemRef.current) {
              // Provide feedback to RL system
              const gridAPI = (window as any).grid || null;
              if (typeof reward === 'number') {
                await rlSystemRef.current.recordFeedback(reward, gridAPI, specificFeedback);
              } else if (specificFeedback) {
                await rlSystemRef.current.recordFeedback(specificFeedback, gridAPI);
              }
              
              // Update stats
              const stats = await rlSystemRef.current.getStats();
              setRLStats(stats);
              setWaitingForFeedback(false);
            }
          }}
        />
      )} */}
      
      {/* RL Toggle */}
      <div className="flex items-center justify-between p-2 bg-gray-800 rounded">
        <span className="text-xs text-gray-400">Reinforcement Learning</span>
        <button
          onClick={() => {}}
          className={cn(
            "relative inline-flex h-5 w-9 items-center rounded-full transition-colors",
            false ? "bg-green-600" : "bg-gray-600"
          )}
        >
          <span
            className={cn(
              "inline-block h-4 w-4 transform rounded-full bg-white transition-transform",
              false ? "translate-x-5" : "translate-x-1"
            )}
          />
        </button>
      </div>

      {/* Debug info */}
      {lastCommands.length > 0 && (
        <div className="text-xs text-gray-500 mt-2">
          Debug: RL={useRL.toString()}, Commands={lastCommands.length}
        </div>
      )}
      
      {/* Simple Inline Feedback Panel */}
      {lastCommands.length > 0 && (
        <div className="border-t border-gray-700 pt-3 mt-3 space-y-2">
          <div className="bg-green-900/50 border border-green-500 rounded p-2">
            <div className="flex items-center justify-between mb-2">
              <div className="text-xs text-green-400 font-bold">
                🎯 SEMANTIC FEEDBACK - {lastCommands.length} commands generated
              </div>
              {feedbackSent && (
                <div className="text-xs text-green-300 animate-pulse">
                  ✓ Feedback sent!
                </div>
              )}
            </div>
            
            {/* Quick Feedback Buttons */}
            <div className="flex gap-1 mb-2">
              <button 
                onClick={() => submitFeedback('good', 'Model output is correct')}
                className="px-2 py-1 bg-green-700 hover:bg-green-600 rounded text-xs text-white"
              >
                👍 Good
              </button>
              <button 
                onClick={() => submitFeedback('bad', 'Model output is wrong')}
                className="px-2 py-1 bg-red-700 hover:bg-red-600 rounded text-xs text-white"
              >
                👎 Bad
              </button>
              <button 
                onClick={() => submitFeedback('edit', 'Model needs minor edits')}
                className="px-2 py-1 bg-yellow-700 hover:bg-yellow-600 rounded text-xs text-white"
              >
                ✏️ Edit
              </button>
              <button 
                onClick={() => submitFeedback('fix', 'Model needs major fixes')}
                className="px-2 py-1 bg-orange-700 hover:bg-orange-600 rounded text-xs text-white"
              >
                🔧 Fix
              </button>
              <button 
                onClick={undoLastAction}
                className="px-2 py-1 bg-purple-700 hover:bg-purple-600 rounded text-xs text-white ml-auto"
                title="Undo last agent action"
              >
                ↩️ Undo
              </button>
            </div>
            
            {/* Semantic Input */}
            <div className="flex gap-1">
              <input
                type="text"
                value={semanticFeedback}
                onChange={(e) => setSemanticFeedback(e.target.value)}
                placeholder="e.g. Revenue should be 350M, Use 12% WACC"
                className="flex-1 px-2 py-1 bg-gray-800 border border-gray-600 rounded text-xs text-white placeholder-gray-400 focus:outline-none focus:border-green-400"
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && semanticFeedback.trim()) {
                    submitFeedback('semantic', semanticFeedback);
                  }
                }}
              />
              <button 
                onClick={() => semanticFeedback.trim() && submitFeedback('semantic', semanticFeedback)}
                disabled={!semanticFeedback.trim()}
                className="px-3 py-1 bg-green-600 hover:bg-green-500 disabled:bg-gray-600 rounded text-xs text-white font-medium"
              >
                Send
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Citations moved to grid - no longer displayed in sidebar */}

      {/* Charts Section */}
      {charts && charts.length > 0 && (
        <div className="mt-4 p-4 bg-gray-900 rounded-lg">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold text-gray-200 flex items-center">
              <BarChart3 className="w-4 h-4 mr-2" />
              Generated Charts
            </h3>
            <button
              onClick={() => setShowCharts(!showCharts)}
              className="text-xs text-blue-400 hover:text-blue-300"
            >
              {showCharts ? 'Hide' : 'Show'}
            </button>
          </div>
          
          {showCharts && (
            <div className="grid grid-cols-1 gap-4">
              {charts.map((chart, index) => (
                <div key={index} className="bg-gray-800 rounded-lg p-3">
                  <AgentChartGenerator
                    prompt={`Chart ${index + 1}: ${chart.title || chart.type}`}
                    data={chart.data || chart}
                  />
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}