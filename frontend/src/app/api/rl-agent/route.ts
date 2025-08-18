import { NextRequest, NextResponse } from 'next/server';
import { exec } from 'child_process';
import { promisify } from 'util';
import path from 'path';
import fs from 'fs/promises';

const execAsync = promisify(exec);

export async function POST(request: NextRequest) {
  try {
    const { action, state, feedback } = await request.json();

    switch (action) {
      case 'predict': {
        // Get next action from trained model
        const scriptPath = path.join(process.cwd(), 'scripts', 'rl_inference.py');
        const stateJson = JSON.stringify(state).replace(/'/g, '"');
        const { stdout } = await execAsync(
          `python3 "${scriptPath}" predict '${stateJson}'`
        );
        
        return NextResponse.json(JSON.parse(stdout));
      }

      case 'train': {
        // Add experience and trigger training
        const scriptPath = path.join(process.cwd(), 'scripts', 'rl_inference.py');
        const experience = {
          state: state.before,
          action: state.action,
          reward: feedback.reward,
          next_state: state.after,
          done: state.done || false,
          user_feedback: feedback.userFeedback
        };
        
        const expJson = JSON.stringify(experience).replace(/'/g, '"');
        const { stdout } = await execAsync(
          `python3 "${scriptPath}" train '${expJson}'`
        );
        
        return NextResponse.json({ success: true, stats: JSON.parse(stdout) });
      }

      case 'status': {
        // Get training status and metrics
        const scriptPath = path.join(process.cwd(), 'scripts', 'rl_inference.py');
        const { stdout } = await execAsync(`python3 "${scriptPath}" status`);
        
        return NextResponse.json(JSON.parse(stdout));
      }

      case 'reset': {
        // Reset agent for new episode
        const scriptPath = path.join(process.cwd(), 'scripts', 'rl_inference.py');
        await execAsync(`python3 "${scriptPath}" reset`);
        
        return NextResponse.json({ success: true });
      }

      default:
        return NextResponse.json(
          { error: 'Invalid action' },
          { status: 400 }
        );
    }
  } catch (error) {
    console.error('RL Agent error:', error);
    return NextResponse.json(
      { error: 'Failed to process RL request' },
      { status: 500 }
    );
  }
}