'use client';

import { useState, useEffect } from 'react';
import { Bot, Play, Loader2, Trash2, Copy, Check } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useGrid } from '@/contexts/GridContext';
import UnifiedFeedback from '@/components/UnifiedFeedback';

export default function AgentRunner() {
  const [prompt, setPrompt] = useState('');
  const [isRunning, setIsRunning] = useState(false);
  const [lastCommands, setLastCommands] = useState<string[]>([]);
  const [copied, setCopied] = useState(false);
  const [sessionId, setSessionId] = useState<string | undefined>();
  const [currentCompany, setCurrentCompany] = useState<string | undefined>();
  const [showFeedback, setShowFeedback] = useState(false);
  const [previousGridState, setPreviousGridState] = useState<any>(null);
  const [progressMessage, setProgressMessage] = useState<string>('');
  const [executionSteps, setExecutionSteps] = useState<string[]>([]);
  
  // Get grid context
  const { executeCommand, executeBatch } = useGrid();
  
  // Helper function to detect model type from prompt
  const detectModelType = (prompt: string): string => {
    const lower = prompt.toLowerCase();
    if (lower.includes('dcf') || lower.includes('discounted cash')) return 'DCF';
    if (lower.includes('revenue') || lower.includes('sales')) return 'Revenue';
    if (lower.includes('saas') || lower.includes('mrr') || lower.includes('arr')) return 'SaaS';
    if (lower.includes('valuation')) return 'Valuation';
    if (lower.includes('pwerm')) return 'PWERM';
    if (lower.includes('p&l') || lower.includes('profit')) return 'P&L';
    if (lower.includes('balance sheet')) return 'BalanceSheet';
    if (lower.includes('burn') || lower.includes('runway')) return 'BurnAnalysis';
    if (lower.includes('unit economics')) return 'UnitEconomics';
    return 'General';
  };
  
  // Debug state changes
  useEffect(() => {
    console.log('lastCommands updated:', lastCommands);
    console.log('lastCommands.length:', lastCommands.length);
  }, [lastCommands]);

  const runAgent = async () => {
    if (!prompt.trim()) return;
    
    console.log('=== Starting runAgent ===');
    console.log('Prompt:', prompt);
    
    setIsRunning(true);
    setProgressMessage('🤔 Understanding your request...');
    setExecutionSteps([]);
    setShowFeedback(false); // Hide any existing feedback
    
    try {
      // Extract company name if mentioned
      const companyMatch = prompt.match(/(?:for|about)\s+(\w+)/i);
      const company = companyMatch?.[1] || currentCompany;
      setCurrentCompany(company);
      
      // Show what we're doing
      setExecutionSteps(prev => [...prev, '📝 Parsing request...']);
      
      // Generate session ID if needed
      if (!sessionId) {
        const newSessionId = crypto.randomUUID();
        setSessionId(newSessionId);
      }
      
      // Use unified brain endpoint with spreadsheet format
      const endpoint = '/api/agent/unified-brain';
      
      // Get current grid state to send as context
      let gridState = {};
      if (gridApi && gridApi.getState) {
        gridState = gridApi.getState();
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
      
      // Handle streaming response
      const reader = response.body?.getReader();
      const decoder = new TextDecoder();
      let allCommands: string[] = [];
      
      if (reader) {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          
          const chunk = decoder.decode(value);
          const lines = chunk.split('\n');
          
          for (const line of lines) {
            if (line.startsWith('data: ')) {
              const data = line.slice(6);
              if (data === '[DONE]') continue;
              
              try {
                const parsed = JSON.parse(data);
                
                if (parsed.type === 'skill_chain') {
                  // Show skill chain decomposition in the stream
                  setExecutionSteps(prev => [...prev, `📋 Decomposed into ${parsed.total_count} skills:`]);
                  parsed.skills?.forEach((skill: any, i: number) => {
                    setExecutionSteps(prev => [...prev, `  ${i+1}. ${skill.name}: ${skill.purpose}`]);
                  });
                } else if (parsed.type === 'skill_start') {
                  // Show skill start in the stream
                  setExecutionSteps(prev => [...prev, `⏳ [${parsed.phase}] Starting: ${parsed.skill}`]);
                } else if (parsed.type === 'skill_complete') {
                  // Show skill completion in the stream
                  const timing = parsed.timing ? ` (${parsed.timing.toFixed(2)}s)` : '';
                  setExecutionSteps(prev => [...prev, `✅ ${parsed.skill} complete${timing}`]);
                } else if (parsed.type === 'skill_error') {
                  // Show skill error in the stream
                  setExecutionSteps(prev => [...prev, `❌ ${parsed.skill} failed: ${parsed.error}`]);
                } else if (parsed.type === 'progress') {
                  setProgressMessage(parsed.message);
                } else if (parsed.type === 'commands') {
                  // Accumulate commands
                  allCommands.push(...parsed.commands);
                  
                  // Update progress
                  if (parsed.progress) {
                    setExecutionSteps(prev => [
                      ...prev.slice(0, -1),
                      `⚡ Processing... ${parsed.progress}%`
                    ]);
                  }
                } else if (parsed.type === 'complete') {
                  setProgressMessage(parsed.message);
                } else if (parsed.type === 'error') {
                  throw new Error(parsed.message);
                }
              } catch (e) {
                console.error('Error parsing SSE data:', e);
              }
            }
          }
        }
      }
      
      // Process the accumulated commands
      const data = { commands: allCommands };
      console.log('=== AGENT COMMAND PROCESSING ===');
      console.log('Streaming complete, total commands:', allCommands.length);
      
      if (data.commands && Array.isArray(data.commands)) {
        console.log('Processing', data.commands.length, 'commands');
        
        // Save current grid state before executing new commands
        if (gridApi && gridApi.getState) {
          const currentState = gridApi.getState();
          setPreviousGridState(currentState);
          console.log('Saved grid state for undo');
        }
        
        setLastCommands(data.commands);
        
        // Update progress for execution
        setProgressMessage('⚡ Executing commands...');
        
        // PARALLEL PROCESSING: Group commands by type for batch execution
        const writeCommands = data.commands.filter(cmd => cmd.includes('write('));
        const formulaCommands = data.commands.filter(cmd => cmd.includes('formula('));
        const styleCommands = data.commands.filter(cmd => cmd.includes('style('));
        const chartCommands = data.commands.filter(cmd => cmd.includes('createChart('));
        
        setExecutionSteps(prev => [...prev, `📊 Processing ${data.commands.length} commands in parallel...`]);
        
        // Helper function to execute a single command
        const executeCommand = async (command: string) => {
          try {
            if (gridApi) {
              const grid = gridApi;
              
              // Use Function constructor for safer execution
              const executeFunc = new Function('grid', `
                try {
                  ${command};
                  return { success: true };
                } catch (e) {
                  console.error('Command error:', e);
                  return { success: false, error: e.toString() };
                }
              `);
              
              const result = executeFunc(grid);
              if (!result.success) {
                console.error(`Failed to execute: ${command}`, result.error);
              }
              return result;
            }
            return { success: false, error: 'Grid not available' };
          } catch (error) {
            console.error('Execution error:', error);
            return { success: false, error: error };
          }
        };
        
        // PARALLEL EXECUTION BY COMMAND TYPE
        const executionPromises = [];
        
        // Execute write commands in parallel (they don't depend on each other)
        if (writeCommands.length > 0) {
          setExecutionSteps(prev => [...prev, `✏️ Writing ${writeCommands.length} data cells in parallel...`]);
          const writePromises = writeCommands.map(cmd => executeCommand(cmd));
          executionPromises.push(Promise.all(writePromises));
        }
        
        // Execute formulas after writes complete (they may depend on written data)
        if (formulaCommands.length > 0) {
          executionPromises.push(
            Promise.all(writeCommands.map(cmd => executeCommand(cmd))).then(() => {
              setExecutionSteps(prev => [...prev, `📈 Adding ${formulaCommands.length} formulas...`]);
              return Promise.all(formulaCommands.map(cmd => executeCommand(cmd)));
            })
          );
        }
        
        // Execute styles in parallel (independent)
        if (styleCommands.length > 0) {
          setExecutionSteps(prev => [...prev, `🎨 Applying ${styleCommands.length} styles...`]);
          const stylePromises = styleCommands.map(cmd => executeCommand(cmd));
          executionPromises.push(Promise.all(stylePromises));
        }
        
        // Execute charts last (they depend on data)
        if (chartCommands.length > 0) {
          executionPromises.push(
            Promise.all([...writeCommands, ...formulaCommands].map(cmd => executeCommand(cmd))).then(() => {
              setExecutionSteps(prev => [...prev, `📊 Creating ${chartCommands.length} charts...`]);
              return Promise.all(chartCommands.map(cmd => executeCommand(cmd)));
            })
          );
        }
        
        // Wait for all parallel executions to complete
        const results = await Promise.allSettled(executionPromises);
        
        // Count successes
        const successCount = results.filter(r => r.status === 'fulfilled').length;
        console.log(`Parallel execution complete: ${successCount}/${executionPromises.length} batches succeeded`);
        
        // Show completion
        setProgressMessage('✅ Complete!');
        setExecutionSteps(prev => [...prev, '🎉 Spreadsheet ready!']);
        
        // Show feedback component after successful generation
        setShowFeedback(true);
      } else {
        setProgressMessage('⚠️ No commands received');
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
    if (gridApi && gridApi.clear) {
      gridApi.clear('A1', 'Z100');
      setLastCommands([]);
      setShowFeedback(false);
    }
  };

  const undoLastAction = () => {
    if (gridApi) {
      // Clear current state
      if (gridApi.clear) {
        gridApi.clear('A1', 'Z100');
      }
      
      // If we have a previous state, restore it
      if (previousGridState && gridApi.setState) {
        gridApi.setState(previousGridState);
        console.log('Restored previous grid state');
      }
      
      // Clear the last commands to hide feedback panel
      setLastCommands([]);
      setPreviousGridState(null);
      setShowFeedback(false);
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
        <div className="flex gap-2">
          {lastCommands.length > 0 && (
            <button
              onClick={undoLastAction}
              className="px-3 py-1 bg-purple-900 hover:bg-purple-800 rounded text-sm flex items-center gap-1"
              title="Undo last agent action"
            >
              ↩️ Undo
            </button>
          )}
          <button
            onClick={clearGrid}
            className="px-3 py-1 bg-red-900 hover:bg-red-800 rounded text-sm flex items-center gap-1"
          >
            <Trash2 className="w-3 h-3" />
            Clear Grid
          </button>
        </div>
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
      
      {/* Unified Feedback Component */}
      {showFeedback && lastCommands.length > 0 && (
        <UnifiedFeedback
          sessionId={sessionId}
          prompt={prompt}
          response={{ commands: lastCommands, gridState: previousGridState }}
          outputFormat="spreadsheet"
          onClose={() => setShowFeedback(false)}
          metadata={{
            company: currentCompany,
            modelType: detectModelType(prompt),
            commandCount: lastCommands.length
          }}
        />
      )}
    </div>
  );
}