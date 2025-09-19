'use client';

import { useState, useEffect, useRef } from 'react';
import { Bot, Play, Loader2, Trash2, Copy, Check, Brain, TrendingUp } from 'lucide-react';
import { cn } from '@/lib/utils';
// import RLFeedbackPanel from './RLFeedbackPanel';
import { SpreadsheetRLSystem } from '@/lib/rl-system';

export default function AgentRunner() {
  const [prompt, setPrompt] = useState('');
  const [isRunning, setIsRunning] = useState(false);
  const [lastCommands, setLastCommands] = useState<string[]>([]);
  const [copied, setCopied] = useState(false);
  const [sessionId, setSessionId] = useState<string | undefined>();
  const [currentCompany, setCurrentCompany] = useState<string | undefined>();
  const [useRL, setUseRL] = useState(true);
  const [semanticFeedback, setSemanticFeedback] = useState('');
  const [feedbackSent, setFeedbackSent] = useState(false);
  const [previousGridState, setPreviousGridState] = useState<any>(null);
  const [rlStats, setRLStats] = useState<any>(null);
  const [waitingForFeedback, setWaitingForFeedback] = useState(false);
  const [learningApplied, setLearningApplied] = useState(false);
  const [learningSummary, setLearningSummary] = useState<string>('');
  const [progressMessage, setProgressMessage] = useState<string>('');
  const [executionSteps, setExecutionSteps] = useState<string[]>([]);
  
  // Initialize RL system
  const rlSystemRef = useRef<SpreadsheetRLSystem | null>(null);
  
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

  // Initialize RL system when enabled
  useEffect(() => {
    if (useRL && !rlSystemRef.current) {
      const modelType = prompt ? detectModelType(prompt) : 'General';
      rlSystemRef.current = new SpreadsheetRLSystem({
        modelType,
        company: currentCompany,
        epsilon: 0.1,  // 10% exploration
        temperature: 1.0,
        autoLearn: true
      });
      
      // Initialize and load stats
      rlSystemRef.current.initialize().then(() => {
        rlSystemRef.current?.getStats().then(stats => {
          setRLStats(stats);
        });
      }).catch(error => {
        console.error('Failed to initialize RL system:', error);
        setUseRL(false); // Disable RL if initialization fails
      });
    }
  }, [useRL, currentCompany]);
  
  // Debug state changes
  useEffect(() => {
    console.log('lastCommands updated:', lastCommands);
    console.log('lastCommands.length:', lastCommands.length);
  }, [lastCommands]);

  const runAgent = async () => {
    if (!prompt.trim()) return;
    
    console.log('=== Starting runAgent ===');
    console.log('Prompt:', prompt);
    console.log('UseRL:', useRL);
    
    setIsRunning(true);
    setProgressMessage('🤔 Understanding your request...');
    setExecutionSteps([]);
    
    try {
      // Extract company name if mentioned
      const companyMatch = prompt.match(/(?:for|about)\s+(\w+)/i);
      const company = companyMatch?.[1] || currentCompany;
      setCurrentCompany(company);
      
      // Show what we're doing
      setExecutionSteps(prev => [...prev, '📝 Parsing request...']);
      
      // Initialize RL system for this prompt if enabled
      if (useRL) {
        if (!rlSystemRef.current) {
          const modelType = detectModelType(prompt);
          rlSystemRef.current = new SpreadsheetRLSystem({
            modelType,
            company,
            epsilon: 0.1,
            temperature: 1.0,
            autoLearn: true
          });
          try {
            await rlSystemRef.current.initialize();
          } catch (error) {
            console.error('Failed to initialize RL in runAgent:', error);
            // Continue without RL
          }
        }
        
        // Get RL suggestion for the prompt
        try {
          if (typeof window !== 'undefined' && (window as any).grid) {
            const currentGrid = (window as any).grid.getState ? (window as any).grid.getState() : {};
            const suggestion = await rlSystemRef.current.getSuggestion(currentGrid, prompt);
            console.log('RL Suggestion:', suggestion);
          }
        } catch (error) {
          console.error('Failed to get RL suggestion:', error);
          // Continue without RL suggestion
        }
        
        if (!sessionId) {
          const newSessionId = crypto.randomUUID();
          setSessionId(newSessionId);
        }
      }
      
      // Use unified brain endpoint with spreadsheet format
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
          trackLearning: useRL,
          gridState,  // Send current grid state for context
          stream: true,  // Enable streaming
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
                  // Also log to console
                  console.log('📋 [Skill Chain] Decomposed into', parsed.total_count, 'skills:');
                  parsed.skills?.forEach((skill: any, i: number) => {
                    console.log(`  ${i+1}. ${skill.name}: ${skill.purpose} (Group ${skill.group})`);
                  });
                } else if (parsed.type === 'skill_start') {
                  // Show skill start in the stream
                  setExecutionSteps(prev => [...prev, `⏳ [${parsed.phase}] Starting: ${parsed.skill}`]);
                  console.log(`⏳ [${parsed.phase}] Starting: ${parsed.skill} - ${parsed.purpose}`);
                } else if (parsed.type === 'skill_complete') {
                  // Show skill completion in the stream
                  const timing = parsed.timing ? ` (${parsed.timing.toFixed(2)}s)` : '';
                  setExecutionSteps(prev => [...prev, `✅ ${parsed.skill} complete${timing}`]);
                  console.log(`✅ [Skill Complete] ${parsed.skill}${timing}`);
                } else if (parsed.type === 'skill_error') {
                  // Show skill error in the stream
                  setExecutionSteps(prev => [...prev, `❌ ${parsed.skill} failed: ${parsed.error}`]);
                  console.error(`❌ [Skill Error] ${parsed.skill}: ${parsed.error}`);
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
                  // Also log the skills that were used from metadata
                  if (parsed.metadata?.skills_used) {
                    console.log('📊 Skills used:', parsed.metadata.skills_used);
                  }
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
      console.log('All commands received:', allCommands);
      
      if (data.commands && Array.isArray(data.commands)) {
        console.log('Processing', data.commands.length, 'commands');
        console.log('window.grid available?', !!(window as any).grid);
        console.log('RL enabled:', useRL);
        console.log('Setting lastCommands to:', data.commands);
        
        // Save current grid state before executing new commands
        if (typeof window !== 'undefined' && (window as any).grid) {
          const currentState = (window as any).grid.getState ? (window as any).grid.getState() : null;
          setPreviousGridState(currentState);
          console.log('Saved grid state for undo');
        }
        
        setLastCommands(data.commands);
        console.log('lastCommands state will update to:', data.commands);
        
        // Record each action for RL if enabled (disabled for now)
        // if (useRL && sessionId) {
        //   for (const command of data.commands) {
        //     const writeMatch = command.match(/grid\.write\("([^"]+)",\s*(.+?)\)/);
        //     if (writeMatch) {
        //       await rlSystem.recordAction({
        //         command,
        //         cell: writeMatch[1],
        //         value: writeMatch[2]
        //       });
        //     }
        //   }
        // }
        
        // Update progress for execution
        setProgressMessage('⚡ Executing commands...');
        let commandCount = 0;
        
        // PARALLEL PROCESSING: Group commands by type for batch execution
        const writeCommands = data.commands.filter(cmd => cmd.includes('write('));
        const formulaCommands = data.commands.filter(cmd => cmd.includes('formula('));
        const styleCommands = data.commands.filter(cmd => cmd.includes('style('));
        const chartCommands = data.commands.filter(cmd => cmd.includes('createChart('));
        
        setExecutionSteps(prev => [...prev, `📊 Processing ${data.commands.length} commands in parallel...`]);
        
        // Helper function to execute a single command
        const executeCommand = async (command: string) => {
          try {
            if (typeof window !== 'undefined' && (window as any).grid) {
              const grid = (window as any).grid;
              
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
        
        // Update RL stats after execution
        if (useRL && rlSystemRef.current) {
          const stats = await rlSystemRef.current.getStats();
          setRLStats(stats);
        }
        
        // Show completion
        setProgressMessage('✅ Complete!');
        setExecutionSteps(prev => [...prev, '🎉 Spreadsheet ready!']);
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
    if (typeof window !== 'undefined' && (window as any).grid) {
      (window as any).grid.clear('A1', 'Z100');
    }
  };

  const undoLastAction = () => {
    if (typeof window !== 'undefined' && (window as any).grid) {
      // Clear current state
      (window as any).grid.clear('A1', 'Z100');
      
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

  // Handle feedback from RL panel
  const handleRLFeedback = async (reward: number, specificFeedback?: string) => {
    console.log('RL Feedback received:', reward, specificFeedback);
    
    if (useRL && rlSystemRef.current && typeof window !== 'undefined' && (window as any).grid) {
      // Record feedback in RL system
      await rlSystemRef.current.recordFeedback(
        reward,
        (window as any).grid,
        specificFeedback
      );
      
      // Update stats
      const stats = await rlSystemRef.current.getStats();
      setRLStats(stats);
      
      // Decay exploration rate after positive feedback
      if (reward > 0.5) {
        rlSystemRef.current.decayEpsilon();
      }
      
      setWaitingForFeedback(false);
    }
  };

  // Submit feedback to API
  const submitFeedback = async (type: string, value?: string) => {
    try {
      console.log('Submitting feedback:', type, value);
      
      const response = await fetch('/api/agent/corrections', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          sessionId: sessionId || crypto.randomUUID(),
          company: currentCompany,
          modelType: detectModelType(prompt),
          correction: value || type,
          feedbackType: type,
          timestamp: new Date(),
          commands: lastCommands
        })
      });

      if (response.ok) {
        setFeedbackSent(true);
        setTimeout(() => setFeedbackSent(false), 2000);
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

      {/* Test Button */}
      <div className="flex gap-2 mb-2">
        <button
          onClick={() => {
            console.log('=== TESTING GRID API ===');
            console.log('window.grid exists?', !!(window as any).grid);
            console.log('window.grid methods:', Object.keys((window as any).grid || {}));
            
            if (typeof window !== 'undefined' && (window as any).grid) {
              try {
                console.log('Writing to A1...');
                (window as any).grid.write("A1", "Test Value", { href: "https://example.com", source: "Test Source" });
                console.log('Writing to B1...');
                (window as any).grid.write("B1", 123);
                console.log('Setting formula in C1...');
                (window as any).grid.formula("C1", "=A1+B1");
                console.log('✅ Test commands executed successfully!');
                
                // Check if data was actually written
                setTimeout(() => {
                  const state = (window as any).grid.getState();
                  console.log('Grid state after test:', state);
                }, 500);
              } catch (error) {
                console.error('❌ Test failed:', error);
              }
            } else {
              console.error('❌ Grid API not found!');
              console.log('window object:', window);
            }
          }}
          className="px-3 py-1 bg-blue-600 hover:bg-blue-700 rounded text-xs"
        >
          Test Grid API
        </button>
        <button
          onClick={() => {
            const testCommands = [
              'window.grid.write("A1", "Company", {style: {fontWeight: "bold"}})',
              'window.grid.write("B1", "Revenue", {style: {fontWeight: "bold"}})',
              'window.grid.write("A2", "Stripe")',
              'window.grid.write("B2", 14000000000)',
              'window.grid.formula("B3", "=B2*1.5")'
            ];
            testCommands.forEach((cmd, i) => {
              setTimeout(() => {
                console.log('Executing:', cmd);
                try {
                  eval(cmd);
                } catch (e) {
                  console.error('Failed:', e);
                }
              }, i * 100);
            });
          }}
          className="px-3 py-1 bg-green-600 hover:bg-green-700 rounded text-xs"
        >
          Test Commands
        </button>
      </div>

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
      {learningApplied && (
        <div className="p-3 bg-green-900/30 border border-green-600/50 rounded animate-pulse">
          <div className="flex items-center gap-2 text-sm text-green-400">
            <Brain className="w-4 h-4" />
            <span className="font-semibold">🧠 LEARNING APPLIED!</span>
          </div>
          <p className="text-xs text-green-300 mt-1">{learningSummary}</p>
        </div>
      )}

      {/* RL Stats Display */}
      {useRL && rlStats && (
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
              const gridAPI = typeof window !== 'undefined' ? (window as any).grid : null;
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
          onClick={() => setUseRL(!useRL)}
          className={cn(
            "relative inline-flex h-5 w-9 items-center rounded-full transition-colors",
            useRL ? "bg-green-600" : "bg-gray-600"
          )}
        >
          <span
            className={cn(
              "inline-block h-4 w-4 transform rounded-full bg-white transition-transform",
              useRL ? "translate-x-5" : "translate-x-1"
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
    </div>
  );
}