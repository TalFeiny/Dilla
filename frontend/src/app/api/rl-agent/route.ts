import { NextRequest, NextResponse } from 'next/server';
import { exec } from 'child_process';
import { promisify } from 'util';
import { resolveScriptPath } from '@/lib/scripts-path';

const execAsync = promisify(exec);

export async function POST(request: NextRequest) {
  try {
    const { path: scriptPath, tried } = resolveScriptPath('rl_inference.py');
    if (!scriptPath) {
      return NextResponse.json(
        { error: `RL script not found. Tried: ${tried.join(', ')}. Set SCRIPTS_DIR or run from repo root.` },
        { status: 500 }
      );
    }
    const { action, state, feedback } = await request.json();

    switch (action) {
      case 'predict': {
        // Get next action from trained model
        const stateJson = JSON.stringify(state).replace(/'/g, '"');
        const { stdout } = await execAsync(
          `python3 "${scriptPath}" predict '${stateJson}'`
        );
        
        return NextResponse.json(JSON.parse(stdout));
      }

      case 'train': {
        // Add experience and trigger training
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
        const { stdout } = await execAsync(`python3 "${scriptPath}" status`);
        
        return NextResponse.json(JSON.parse(stdout));
      }

      case 'reset': {
        // Reset agent for new episode
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