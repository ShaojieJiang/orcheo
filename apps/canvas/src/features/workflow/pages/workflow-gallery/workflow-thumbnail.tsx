import { type Workflow } from "@features/workflow/data/workflow-data";

const NODE_COLORS: Record<string, string> = {
  trigger: "#f59e0b",
  api: "#3b82f6",
  function: "#8b5cf6",
  data: "#10b981",
  ai: "#6366f1",
  python: "#f97316",
};

interface WorkflowThumbnailProps {
  workflow: Workflow;
}

export const WorkflowThumbnail = ({ workflow }: WorkflowThumbnailProps) => {
  return (
    <div className="relative h-24 w-full overflow-hidden rounded-md bg-muted/30">
      <svg
        width="100%"
        height="100%"
        viewBox="0 0 200 100"
        className="absolute inset-0"
      >
        {workflow.nodes.slice(0, 5).map((node, index) => {
          const x = 30 + (index % 3) * 70;
          const y = 30 + Math.floor(index / 3) * 40;
          const color = NODE_COLORS[node.type] ?? "#99a1b3";

          return (
            <g key={node.id}>
              <rect
                x={x - 15}
                y={y - 10}
                width={30}
                height={20}
                rx={4}
                fill={color}
                fillOpacity={0.3}
                stroke={color}
                strokeWidth={1}
              />
            </g>
          );
        })}

        {workflow.edges.slice(0, 4).map((edge) => {
          const sourceIndex = workflow.nodes.findIndex(
            (node) => node.id === edge.source,
          );
          const targetIndex = workflow.nodes.findIndex(
            (node) => node.id === edge.target,
          );

          if (
            sourceIndex < 0 ||
            targetIndex < 0 ||
            sourceIndex >= 5 ||
            targetIndex >= 5
          ) {
            return null;
          }

          const sourceX = 30 + (sourceIndex % 3) * 70 + 15;
          const sourceY = 30 + Math.floor(sourceIndex / 3) * 40;
          const targetX = 30 + (targetIndex % 3) * 70 - 15;
          const targetY = 30 + Math.floor(targetIndex / 3) * 40;

          return (
            <path
              key={edge.id}
              d={`M${sourceX},${sourceY} C${sourceX + 20},${sourceY} ${targetX - 20},${targetY} ${targetX},${targetY}`}
              stroke="#99a1b3"
              strokeWidth={1}
              fill="none"
            />
          );
        })}
      </svg>
    </div>
  );
};
