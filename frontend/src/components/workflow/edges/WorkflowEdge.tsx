'use client';

import { memo } from 'react';
import {
  BaseEdge,
  getBezierPath,
  type EdgeProps,
  EdgeLabelRenderer,
} from '@xyflow/react';

function WorkflowEdgeComponent({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  selected,
  sourceHandleId,
}: EdgeProps) {
  const [edgePath, labelX, labelY] = getBezierPath({
    sourceX,
    sourceY,
    sourcePosition,
    targetX,
    targetY,
    targetPosition,
  });

  const isFalseBranch = sourceHandleId === 'false_out';

  return (
    <>
      <BaseEdge
        id={id}
        path={edgePath}
        style={{
          stroke: isFalseBranch ? '#ef4444' : selected ? '#fff' : '#4b5563',
          strokeWidth: selected ? 2.5 : 1.5,
          strokeDasharray: isFalseBranch ? '5 3' : undefined,
        }}
      />
      {isFalseBranch && (
        <EdgeLabelRenderer>
          <div
            style={{
              position: 'absolute',
              transform: `translate(-50%, -50%) translate(${labelX}px,${labelY}px)`,
              pointerEvents: 'none',
            }}
            className="text-[9px] font-medium text-red-400 bg-gray-900 px-1 rounded"
          >
            false
          </div>
        </EdgeLabelRenderer>
      )}
    </>
  );
}

export const WorkflowEdge = memo(WorkflowEdgeComponent);
