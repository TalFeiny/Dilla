import { NextRequest, NextResponse } from 'next/server';
import { exec } from 'child_process';
import { promisify } from 'util';

const execAsync = promisify(exec);

// Whitelist of allowed commands for security
const ALLOWED_COMMANDS = {
  'restart-dev': async () => {
    // Kill existing process on port 3001
    try {
      await execAsync("lsof -ti:3001 | xargs kill -9");
    } catch (e) {
      // Port might not be in use, that's OK
    }
    
    // Start dev server in background
    exec('cd vc-platform-new && npm run dev', (error, stdout, stderr) => {
      if (error) {
        console.error('Dev server error:', error);
      }
    });
    
    return { success: true, message: 'Dev server restarting on port 3001' };
  },
  
  'stop-dev': async () => {
    try {
      const { stdout } = await execAsync("lsof -ti:3001 | xargs kill -9");
      return { success: true, message: 'Dev server stopped' };
    } catch (error) {
      return { success: false, message: 'No dev server running on port 3001' };
    }
  },
  
  'status': async () => {
    try {
      const { stdout } = await execAsync("lsof -i:3001 | grep LISTEN");
      return { success: true, message: 'Dev server is running', details: stdout };
    } catch (error) {
      return { success: false, message: 'Dev server is not running' };
    }
  }
};

export async function POST(request: NextRequest) {
  try {
    const { command } = await request.json();
    
    if (!command || !ALLOWED_COMMANDS[command]) {
      return NextResponse.json(
        { error: `Invalid command. Allowed: ${Object.keys(ALLOWED_COMMANDS).join(', ')}` },
        { status: 400 }
      );
    }
    
    const result = await ALLOWED_COMMANDS[command]();
    return NextResponse.json(result);
    
  } catch (error) {
    console.error('System command error:', error);
    return NextResponse.json(
      { error: 'Failed to execute system command' },
      { status: 500 }
    );
  }
}