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
  
  
  // Debug state changes - REMOVED to prevent potential re-render issues
  // useEffect(() => {
  //   console.log('lastCommands updated:', lastCommands);
  //   console.log('lastCommands.length:', lastCommands.length);
  // }, [lastCommands]);

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
      
      // Initialize RL system for this prompt if enabled
      // COMMENTED OUT: Missing imports for detectModelType and SpreadsheetRLSystem
      // if (useRL) {
      //   if (!rlSystemRef.current) {
      //     const modelType = detectModelType(prompt);
      //     rlSystemRef.current = new SpreadsheetRLSystem({
      //       modelType,
      //       company,
      //       epsilon: 0.1,
      //       temperature: 1.0,
      //       autoLearn: true
      //     });
      //     try {
      //       await rlSystemRef.current.initialize();
      //     } catch (error) {
      //       console.error('Failed to initialize RL in runAgent:', error);
      //       // Continue without RL
      //     }
      //   }
      //   
      //   // Get RL suggestion for the prompt
      //   try {
      //     if (gridApi && gridApi.getState) {
      //       const currentGrid = gridApi.getState();
      //       const suggestion = await rlSystemRef.current.getSuggestion(currentGrid, prompt);
      //       console.log('RL Suggestion:', suggestion);
      //     }
      //   } catch (error) {
      //     console.error('Failed to get RL suggestion:', error);
      //     // Continue without RL suggestion
      //   }
      //   
      //   if (!sessionId) {
      //     const newSessionId = crypto.randomUUID();
      //     setSessionId(newSessionId);
      //   }
      // }
      
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
          stream: true,  // Enable streaming
          // Request formulas and citations
          includeFormulas: true,
          includeCitations: true
        })
      });

      if (!response.ok) throw new Error('Failed to get agent response');
      
      // Handle streaming response with proper UTF-8 decoding
      const reader = response.body?.getReader();
      const decoder = new TextDecoder('utf-8', { fatal: false }); // Don't throw on invalid UTF-8
      let allCommands: string[] = [];
      let streamComplete = false;
      
      if (reader) {
        let buffer = '';  // Buffer for incomplete chunks
        
        while (true) {
          const { done, value } = await reader.read();
          if (done) {
            console.log('[AgentRunner] Stream reading complete');
            streamComplete = true;
            break;
          }
          
          const chunk = decoder.decode(value, { stream: true });
          console.log('[AgentRunner] Raw chunk received:', chunk.substring(0, 500));
          
          // DEBUG: Check for corrupted data
          if (chunk.includes('tacxn') || chunk.includes('\\u')) {
            console.error('[AgentRunner] WARNING: Corrupted data detected in chunk!');
            console.log('[AgentRunner] Full corrupted chunk:', chunk);
          }
          
          // Add chunk to buffer
          buffer += chunk;
          
          // Process complete lines
          const lines = buffer.split('\n');
          // Keep the last incomplete line in the buffer
          buffer = lines.pop() || '';
          
          for (const line of lines) {
            if (line.startsWith('data: ')) {
              const data = line.slice(6).trim();
              if (data === '[DONE]') {
                console.log('[AgentRunner] Stream complete signal received');
                continue;
              }
              
              try {
                console.log('[AgentRunner] Parsing SSE data:', data.substring(0, 200));
                const parsed = JSON.parse(data);
                console.log('[AgentRunner] Parsed type:', parsed.type);
                
                // LOG: Check if Traxn.com is in the data
                if (JSON.stringify(parsed).includes('Traxn') || JSON.stringify(parsed).includes('traxn')) {
                  console.error('[AgentRunner] WARNING: Traxn.com detected in response - backend is using wrong data source!');
                  console.log('[AgentRunner] Full parsed data with Traxn:', JSON.stringify(parsed, null, 2));
                }
                
                if (parsed.type === 'skill_chain') {
                  // Show skill chain decomposition in the stream - batch updates to prevent re-renders
                  const newSteps = [`📋 Decomposed into ${parsed.total_count} skills:`];
                  parsed.skills?.forEach((skill: any, i: number) => {
                    newSteps.push(`  ${i+1}. ${skill.name}: ${skill.purpose}`);
                  });
                  setExecutionSteps(prev => [...prev, ...newSteps]);
                  // Also log to console
                  // Skill chain decomposed
                } else if (parsed.type === 'skill_start') {
                  // Show skill start in the stream
                  setExecutionSteps(prev => [...prev, `⏳ [${parsed.phase}] Starting: ${parsed.skill}`]);
                  // Skill starting
                } else if (parsed.type === 'skill_complete') {
                  // Show skill completion in the stream
                  const timing = parsed.timing ? ` (${parsed.timing.toFixed(2)}s)` : '';
                  setExecutionSteps(prev => [...prev, `✅ ${parsed.skill} complete${timing}`]);
                  // Skill complete
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
                  console.log('[AgentRunner] COMPLETE MESSAGE:', parsed);
                  setProgressMessage(parsed.message);
                  // Also log the skills that were used from metadata
                  if (parsed.metadata?.skills_used) {
                    console.log('[AgentRunner] Skills used:', parsed.metadata.skills_used);
                  }
                  
                  // Check if the complete message includes formatted result
                  if (parsed.result) {
                    console.log('[AgentRunner] Complete message received with result:', JSON.stringify(parsed.result, null, 2));
                    console.log('[AgentRunner] Result type:', typeof parsed.result);
                    console.log('[AgentRunner] Result keys:', Object.keys(parsed.result));
                    
                    // DEBUG: Log what we're actually getting
                    console.log('[AgentRunner] Checking for commands in result...');
                    console.log('  - parsed.result.commands exists?', !!parsed.result.commands);
                    console.log('  - parsed.result.commands is array?', Array.isArray(parsed.result.commands));
                    console.log('  - parsed.result.grid exists?', !!parsed.result.grid);
                    console.log('  - parsed.result.grid.data exists?', !!parsed.result.grid?.data);
                    
                    // Extract citations and integrate them with the data
                    if (parsed.result.citations && parsed.result.citations.length > 0) {
                      setCitations(parsed.result.citations);
                      
                      // Look for citation references in the data and add them as inline references
                      // This assumes the backend has marked cells with [1], [2] etc
                      // We'll add the citation info as metadata/tooltips to those cells
                      
                      if (parsed.result.data && Array.isArray(parsed.result.data)) {
                        parsed.result.data.forEach((row, rowIndex) => {
                          row.forEach((cell, colIndex) => {
                            if (typeof cell === 'string') {
                              // Check if this cell contains citation references like [1], [2]
                              const citationPattern = /\[(\d+)\]/g;
                              const matches = cell.match(citationPattern);
                              
                              if (matches) {
                                // This cell has citations - add them as source metadata
                                const cellAddress = String.fromCharCode(65 + colIndex) + (rowIndex + 1);
                                const citationNumbers = matches.map(m => parseInt(m.replace(/[\[\]]/g, '')));
                                
                                // Find the corresponding citations
                                const relevantCitations = parsed.result.citations.filter(c => 
                                  citationNumbers.includes(c.number)
                                );
                                
                                if (relevantCitations.length > 0) {
                                  // Create a source string with all relevant citations
                                  const sourceText = relevantCitations.map(c => 
                                    `[${c.number}] ${c.source} - ${c.title}`
                                  ).join('; ');
                                  
                                  // Add the citation URL if there's a primary citation
                                  const primaryCitation = relevantCitations[0];
                                  if (primaryCitation.url) {
                                    // Add as a linked cell with source metadata
                                    const writeCommand = allCommands.find(cmd => 
                                      cmd.includes(`grid.write("${cellAddress}"`)
                                    );
                                    if (writeCommand) {
                                      // Update the write command to include source metadata
                                      const updatedCommand = writeCommand.replace(
                                        /\)$/,
                                        `, { source: "${sourceText.replace(/"/g, '\\"')}", sourceUrl: "${primaryCitation.url.replace(/"/g, '\\"')}" })`
                                      );
                                      const cmdIndex = allCommands.indexOf(writeCommand);
                                      if (cmdIndex !== -1) {
                                        allCommands[cmdIndex] = updatedCommand;
                                      }
                                    }
                                  }
                                }
                              }
                            }
                          });
                        });
                      }
                    }
                    
                    // Extract charts if available
                    if (parsed.result.charts) {
                      setCharts(parsed.result.charts);
                    }
                    
                    // IMPORTANT: Backend sends commands directly for spreadsheet format
                    // Check for commands first (spreadsheet format)
                    if (parsed.result.commands && Array.isArray(parsed.result.commands)) {
                      console.log('[AgentRunner] Found commands in result:', parsed.result.commands.length);
                      console.log('[AgentRunner] Commands sample:', parsed.result.commands.slice(0, 3));
                      allCommands.push(...parsed.result.commands);
                      console.log('[AgentRunner] allCommands now has:', allCommands.length);
                    }
                    // Fallback: If result has grid data, convert to commands
                    else if (parsed.result.grid && parsed.result.grid.data) {
                      console.log('[AgentRunner] Converting grid data to commands');
                      const gridCommands = convertGridDataToCommands(parsed.result.grid);
                      allCommands.push(...gridCommands);
                    }
                    // Also check if commands are at the root level of parsed (some streaming variations)
                    else if (parsed.commands && Array.isArray(parsed.commands)) {
                      console.log('[AgentRunner] Found commands at root level:', parsed.commands.length);
                      allCommands.push(...parsed.commands);
                    }
                    // FALLBACK: If result is a string, it might be JSON that needs parsing
                    else if (typeof parsed.result === 'string') {
                      console.log('[AgentRunner] Result is a string, attempting to parse as JSON...');
                      try {
                        const resultData = JSON.parse(parsed.result);
                        if (resultData.commands && Array.isArray(resultData.commands)) {
                          console.log('[AgentRunner] Found commands after parsing string:', resultData.commands.length);
                          allCommands.push(...resultData.commands);
                        } else if (resultData.grid?.data) {
                          console.log('[AgentRunner] Found grid data after parsing string');
                          const gridCommands = convertGridDataToCommands(resultData.grid);
                          allCommands.push(...gridCommands);
                        }
                      } catch (parseError) {
                        console.error('[AgentRunner] Failed to parse result string as JSON:', parseError);
                        console.log('[AgentRunner] Raw result string:', parsed.result.substring(0, 200));
                      }
                    }
                    // FINAL FALLBACK: Check if there's data array directly
                    else if (parsed.result.data && Array.isArray(parsed.result.data)) {
                      console.log('[AgentRunner] Found data array directly, converting to grid commands');
                      const gridCommands = convertGridDataToCommands({ data: parsed.result.data });
                      allCommands.push(...gridCommands);
                    }
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
        
        // Process any remaining buffer
        if (buffer.trim()) {
          console.log('[AgentRunner] Processing remaining buffer:', buffer);
        }
      }
      
      // Process the accumulated commands
      const data = { commands: allCommands };
      console.log('[AgentRunner] Total commands to process:', allCommands.length);
      console.log('[AgentRunner] First 5 commands:', allCommands.slice(0, 5));
      
      // If no commands were found, create a default message
      if (!allCommands || allCommands.length === 0) {
        console.error('[AgentRunner] WARNING: No commands were extracted from the response!');
        console.log('[AgentRunner] This likely means the backend response format is unexpected.');
        
        // Add a default command to show something is working
        allCommands.push('grid.write("A1", "No data received - check backend response format")');
        allCommands.push('grid.write("A2", "The backend may not be returning data in the expected format")');
        allCommands.push('grid.write("A3", "Check the browser console for detailed logs")');
        data.commands = allCommands;
      } else {
        // Validate commands to check for corruption
        console.log('[AgentRunner] Validating commands for corruption...');
        const corruptedCommands = allCommands.filter(cmd => 
          cmd.includes('tacxn') || 
          cmd.includes('\\u0000') || 
          !cmd.includes('grid.') ||
          cmd.includes('undefined') ||
          cmd.includes('null')
        );
        
        if (corruptedCommands.length > 0) {
          console.error('[AgentRunner] CORRUPTED COMMANDS DETECTED:', corruptedCommands);
          console.log('[AgentRunner] This indicates the backend is sending malformed data');
          
          // Replace corrupted commands with error message
          allCommands = [
            'grid.write("A1", "ERROR: Backend sent corrupted data")',
            'grid.write("A2", "Corrupted commands detected - check console")',
            `grid.write("A3", "Example corruption: ${corruptedCommands[0]?.substring(0, 50)}")`
          ];
          data.commands = allCommands;
        }
      }
      
      if (data.commands && Array.isArray(data.commands) && data.commands.length > 0) {
        console.log('[AgentRunner] Processing commands:', data.commands.length);
        console.log('[AgentRunner] Sample command:', data.commands[0]);
        
        // Wait for Grid API to be available - Improved logic
        let gridReady = false;
        let attemptCount = 0;
        const maxAttempts = 40; // Increased attempts for slower initialization
        
        setProgressMessage('🔄 Waiting for spreadsheet to initialize...');
        
        while (!gridReady && attemptCount < maxAttempts) {
          attemptCount++;
          
          // First check if executeCommand is available (from context)
          if (executeCommand) {
            // Try a test command to verify grid is actually ready
            try {
              const testResult = await executeCommand('grid.selectCell("A1")');
              console.log(`[AgentRunner] Test command result (attempt ${attemptCount}):`, testResult);
              
              // Check if grid is ready
              if (!testResult || (typeof testResult === 'string')) {
                // If result is a string or null, grid is ready
                gridReady = true;
                console.log(`[AgentRunner] Grid API verified ready after ${attemptCount} attempts`);
                break;
              } else if (typeof testResult === 'object' && 'error' in testResult) {
                // Check for error in object result
                if (testResult.error === 'Grid API not available' || testResult.error === 'Grid context not available') {
                  console.log(`[AgentRunner] Grid not ready yet (attempt ${attemptCount}/${maxAttempts})`);
                } else {
                  // Some other error - grid might be ready but command failed
                  console.log(`[AgentRunner] Grid might be ready, test failed with:`, testResult.error);
                  gridReady = true; // Try to proceed anyway
                  break;
                }
              }
            } catch (e) {
              console.log(`[AgentRunner] Test command exception (attempt ${attemptCount}):`, e);
            }
          }
          
          // Also check direct APIs as fallback
          if (!gridReady && (typeof window !== 'undefined' && (window as any).grid)) {
            console.log('[AgentRunner] Direct grid API found as fallback');
            gridReady = true;
            break;
          }
          
          // Longer wait initially to allow grid to render
          const waitTime = attemptCount <= 5 ? 1000 : 500;
          console.log(`[AgentRunner] Waiting ${waitTime}ms before next attempt...`);
          await new Promise(resolve => setTimeout(resolve, waitTime));
        }
        
        // Proceed even if grid not fully ready - executeCommand will handle retries
        if (!gridReady) {
          console.warn('[AgentRunner] Grid initialization timed out, but proceeding with command execution');
          setProgressMessage('⚠️ Grid initialization slow - commands will execute with retry logic...');
        } else {
          setProgressMessage('✅ Spreadsheet ready - executing commands...');
        }
        
        // Save current grid state before executing new commands
        if (typeof window !== 'undefined' && (window as any).grid) {
          const currentState = (window as any).grid.getState ? (window as any).grid.getState() : null;
          setPreviousGridState(currentState);
          console.log('[AgentRunner] Saved grid state for undo');
        }
        
        setLastCommands(data.commands);
        console.log('[AgentRunner] Commands state updated')
        
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
        
        // PARALLEL PROCESSING: Group commands by type for batch execution
        const writeCommands = data.commands.filter(cmd => cmd.includes('write('));
        const formulaCommands = data.commands.filter(cmd => cmd.includes('formula('));
        const styleCommands = data.commands.filter(cmd => cmd.includes('style('));
        const chartCommands = data.commands.filter(cmd => 
          cmd.includes('createChart(') || cmd.includes('createChartBatch(')
        );
        
        setExecutionSteps(prev => [...prev, `📊 Processing ${data.commands.length} commands in parallel...`]);
        
        // Helper function to execute a single command securely with retry logic
        const executeCommandSecure = async (command: string, retries = 3) => {
          for (let attempt = 1; attempt <= retries; attempt++) {
            try {
              console.log(`[ExecuteCommand] Attempt ${attempt} for: ${command.substring(0, 50)}...`);
              
              // Try to execute the command even if gridApi is not directly available
              // The executeCommand function from context should handle this
              const result = await executeCommand(command);
              
              // Log the result for debugging
              if (result && typeof result === 'object' && 'error' in result) {
                console.log(`[ExecuteCommand] Command returned error:`, result.error);
              } else {
                console.log(`[ExecuteCommand] Command executed successfully`);
              }
              
              // Check if result indicates grid not available
              if (result && typeof result === 'object' && result.error) {
                if (result.error === 'Grid context not available' || result.error === 'Grid API not available') {
                  console.warn(`[ExecuteCommand] Grid not ready (attempt ${attempt}/${retries}): ${result.error}`);
                  if (attempt < retries) {
                    await new Promise(resolve => setTimeout(resolve, 500 * attempt));
                    continue;
                  }
                  return { success: false, error: result.error };
                }
                // Other errors - don't retry
                console.error('[ExecuteCommand] Command failed:', result.error);
                return { success: false, error: result.error };
              }
              
              console.log(`[ExecuteCommand] Success on attempt ${attempt}`);
              return { success: true, result };
            } catch (error) {
              console.error(`[ExecuteCommand] Error on attempt ${attempt}:`, error);
              if (attempt === retries) {
                return { success: false, error: error.message };
              }
              await new Promise(resolve => setTimeout(resolve, 500 * attempt));
            }
          }
          return { success: false, error: 'Max retries exceeded' };
        };
        
        // PARALLEL EXECUTION BY COMMAND TYPE
        const executionPromises = [];
        
        // Execute write commands in parallel (they don't depend on each other)
        if (writeCommands.length > 0) {
          setExecutionSteps(prev => [...prev, `✏️ Writing ${writeCommands.length} data cells in parallel...`]);
          const writePromises = writeCommands.map(cmd => executeCommandSecure(cmd));
          executionPromises.push(Promise.all(writePromises));
        }
        
        // Execute formulas after writes complete (they may depend on written data)
        if (formulaCommands.length > 0) {
          executionPromises.push(
            Promise.all(writeCommands.map(cmd => executeCommandSecure(cmd))).then(() => {
              setExecutionSteps(prev => [...prev, `📈 Adding ${formulaCommands.length} formulas...`]);
              return Promise.all(formulaCommands.map(cmd => executeCommandSecure(cmd)));
            })
          );
        }
        
        // Execute styles in parallel (independent)
        if (styleCommands.length > 0) {
          setExecutionSteps(prev => [...prev, `🎨 Applying ${styleCommands.length} styles...`]);
          const stylePromises = styleCommands.map(cmd => executeCommandSecure(cmd));
          executionPromises.push(Promise.all(stylePromises));
        }
        
        // Execute charts last (they depend on data)
        if (chartCommands.length > 0) {
          // Special handling for batch charts
          const batchCommand = chartCommands.find(cmd => cmd.includes('createChartBatch'));
          if (batchCommand) {
            setExecutionSteps(prev => [...prev, `📊 Creating chart batch...`]);
            executionPromises.push(executeCommandSecure(batchCommand));
          } else {
            executionPromises.push(
              Promise.all([...writeCommands, ...formulaCommands].map(cmd => executeCommandSecure(cmd))).then(() => {
                setExecutionSteps(prev => [...prev, `📊 Creating ${chartCommands.length} charts...`]);
                return Promise.all(chartCommands.map(cmd => executeCommandSecure(cmd)));
              })
            );
          }
        }
        
        // Wait for all parallel executions to complete
        const results = await Promise.allSettled(executionPromises);
        
        // Log results for debugging
        console.log(`[AgentRunner] Execution complete. ${results.filter(r => r.status === 'fulfilled').length} successful, ${results.filter(r => r.status === 'rejected').length} failed`);
        // Parallel execution complete
        
        // Removed RL stats update
        
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
          sessionId: sessionId || crypto.randomUUID(),
          company: currentCompany,
          modelType: 'unified-brain',  // Fixed model type
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

      {/* Test Button - Using GridContext */}
      <div className="flex gap-2 mb-2">
        <button
          onClick={() => {
            console.log('=== TESTING GRID API (via Context) ===');
            console.log('grid exists?', !!(window as any).grid);
            console.log('grid methods:', (window as any).grid ? Object.keys((window as any).grid) : []);
            
            if ((window as any).grid) {
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
                  const state = (window as any).grid.getState ? (window as any).grid.getState() : {};
                  console.log('Grid state after test:', state);
                }, 500);
              } catch (error) {
                console.error('❌ Test failed:', error);
              }
            } else {
              console.error('❌ Grid API not available in context!');
            }
          }}
          className="px-3 py-1 bg-blue-600 hover:bg-blue-700 rounded text-xs"
        >
          Test Grid API
        </button>
        <button
          onClick={() => {
            const testCommands = [
              'grid.write("A1", "Company", {style: {fontWeight: "bold"}})',
              'grid.write("B1", "Revenue", {style: {fontWeight: "bold"}})',
              'grid.write("A2", "Stripe")',
              'grid.write("B2", 14000000000)',
              'grid.formula("B3", "=B2*1.5")'
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