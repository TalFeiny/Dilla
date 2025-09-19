/**
 * Secure Command Executor for Production
 * Parses and executes grid commands without eval() or Function constructor
 */

export interface GridCommand {
  method: string;
  args: any[];
}

export class SecureCommandExecutor {
  /**
   * Parse a grid command string into a safe command object
   * Example: 'grid.write("A1", "Hello")' -> { method: 'write', args: ['A1', 'Hello'] }
   */
  static parseCommand(command: string): GridCommand | null {
    try {
      // Remove 'grid.' prefix if present
      const cleanCommand = command.replace(/^grid\./, '');
      
      // Match method name and arguments
      const match = cleanCommand.match(/^(\w+)\((.*)\)$/);
      if (!match) return null;
      
      const [, method, argsString] = match;
      
      // Parse arguments safely (without eval)
      const args = this.parseArguments(argsString);
      
      return { method, args };
    } catch (error) {
      console.error('Failed to parse command:', command, error);
      return null;
    }
  }
  
  /**
   * Parse function arguments safely without eval
   */
  private static parseArguments(argsString: string): any[] {
    if (!argsString.trim()) return [];
    
    const args: any[] = [];
    let current = '';
    let inString = false;
    let stringChar = '';
    let depth = 0;
    
    for (let i = 0; i < argsString.length; i++) {
      const char = argsString[i];
      
      if (!inString) {
        if (char === '"' || char === "'") {
          inString = true;
          stringChar = char;
          current += char;
        } else if (char === '{' || char === '[') {
          depth++;
          current += char;
        } else if (char === '}' || char === ']') {
          depth--;
          current += char;
        } else if (char === ',' && depth === 0) {
          args.push(this.parseValue(current.trim()));
          current = '';
        } else {
          current += char;
        }
      } else {
        current += char;
        if (char === stringChar && argsString[i - 1] !== '\\') {
          inString = false;
        }
      }
    }
    
    if (current.trim()) {
      args.push(this.parseValue(current.trim()));
    }
    
    return args;
  }
  
  /**
   * Parse a single value (string, number, boolean, object, array)
   */
  private static parseValue(value: string): any {
    // Remove surrounding quotes for strings
    if ((value.startsWith('"') && value.endsWith('"')) || 
        (value.startsWith("'") && value.endsWith("'"))) {
      return value.slice(1, -1).replace(/\\"/g, '"').replace(/\\'/g, "'");
    }
    
    // Parse numbers
    if (/^-?\d+(\.\d+)?$/.test(value)) {
      return parseFloat(value);
    }
    
    // Parse booleans
    if (value === 'true') return true;
    if (value === 'false') return false;
    if (value === 'null') return null;
    if (value === 'undefined') return undefined;
    
    // Parse objects and arrays (safely with JSON.parse)
    if (value.startsWith('{') || value.startsWith('[')) {
      try {
        return JSON.parse(value);
      } catch {
        // If JSON parse fails, return as string
        return value;
      }
    }
    
    // Default to string
    return value;
  }
  
  /**
   * Execute a parsed command on a grid API object
   */
  static executeCommand(api: any, command: GridCommand): any {
    const { method, args } = command;
    
    // Validate method exists and is a function
    if (!api || typeof api[method] !== 'function') {
      throw new Error(`Invalid method: ${method}`);
    }
    
    // Execute the method with parsed arguments
    return api[method](...args);
  }
  
  /**
   * Parse and execute a batch of commands
   */
  static executeBatch(api: any, commands: string[]): { success: boolean; results: any[] } {
    const results: any[] = [];
    let success = true;
    
    for (const commandStr of commands) {
      try {
        const command = this.parseCommand(commandStr);
        if (command) {
          const result = this.executeCommand(api, command);
          results.push(result);
        }
      } catch (error) {
        console.error('Command execution failed:', commandStr, error);
        success = false;
        results.push({ error: error.message });
      }
    }
    
    return { success, results };
  }
  
  /**
   * Special handler for createChartBatch command
   */
  static handleChartBatch(api: any, commandStr: string): any {
    if (!commandStr.includes('createChartBatch')) {
      return null;
    }
    
    // Extract the JSON array from the command
    const match = commandStr.match(/createChartBatch\((.*)\)/);
    if (!match) return null;
    
    try {
      const chartBatch = JSON.parse(match[1]);
      if (api.createChartBatch) {
        return api.createChartBatch(chartBatch);
      }
    } catch (error) {
      console.error('Failed to parse chart batch:', error);
    }
    
    return null;
  }
}

// Command validator for additional security
export class CommandValidator {
  private static readonly ALLOWED_METHODS = new Set([
    'write', 'formula', 'style', 'format', 'clear',
    'createChart', 'createChartBatch', 'createFinancialChart',
    'setColumns', 'addRow', 'link', 'selectCell',
    'applyStyle', 'conditionalFormat'
  ]);
  
  /**
   * Validate a command is safe to execute
   */
  static isValidCommand(command: GridCommand): boolean {
    // Check if method is in allowed list
    if (!this.ALLOWED_METHODS.has(command.method)) {
      console.warn(`Method not allowed: ${command.method}`);
      return false;
    }
    
    // Additional validation rules
    if (command.method === 'write' && command.args.length < 2) {
      console.warn('Write command requires at least 2 arguments');
      return false;
    }
    
    return true;
  }
  
  /**
   * Sanitize command arguments
   */
  static sanitizeArgs(args: any[]): any[] {
    return args.map(arg => {
      // Remove any potential script tags or dangerous content
      if (typeof arg === 'string') {
        return arg
          .replace(/<script[^>]*>.*?<\/script>/gi, '')
          .replace(/javascript:/gi, '')
          .replace(/on\w+\s*=/gi, '');
      }
      return arg;
    });
  }
}