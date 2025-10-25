import React from "react";
import {
  BaseEdge,
  EdgeLabelRenderer,
  EdgeProps,
  getBezierPath,
  useReactFlow,
} from "@xyflow/react";
import { Trash2 } from "lucide-react";
import { useEdgeHoverContext } from "@features/workflow/components/canvas/edge-hover-context";

export default function CustomEdge({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  style = {},
  markerEnd,
}: EdgeProps) {
  const edgeHoverContext = useEdgeHoverContext();
  const [localHovered, setLocalHovered] = React.useState(false);
  const { setEdges } = useReactFlow();

  const [edgePath, labelX, labelY] = getBezierPath({
    sourceX,
    sourceY,
    sourcePosition,
    targetX,
    targetY,
    targetPosition,
  });

  const hoveredEdgeId = edgeHoverContext?.hoveredEdgeId ?? null;
  const setHoveredEdgeId = edgeHoverContext?.setHoveredEdgeId;

  const showHover = React.useCallback(
    (hovered: boolean) => {
      if (setHoveredEdgeId) {
        const nextId = hovered ? id : null;
        if (hoveredEdgeId === nextId) {
          return;
        }
        setHoveredEdgeId(nextId);
      } else {
        setLocalHovered(hovered);
      }
    },
    [hoveredEdgeId, id, setHoveredEdgeId],
  );

  const isHovered =
    setHoveredEdgeId !== undefined ? hoveredEdgeId === id : localHovered;

  const handleDelete = (event: React.MouseEvent) => {
    event.stopPropagation();
    setEdges((edges) => edges.filter((edge) => edge.id !== id));
    showHover(false);
  };

  return (
    <>
      {/* Invisible wider path for easier hovering */}
      <path
        d={edgePath}
        fill="none"
        stroke="currentColor"
        strokeOpacity={0}
        strokeWidth={20}
        style={{ pointerEvents: "stroke" }}
        onMouseEnter={() => {
          if (!setHoveredEdgeId) {
            setLocalHovered(true);
          }
        }}
        onMouseLeave={() => {
          if (!setHoveredEdgeId) {
            setLocalHovered(false);
          }
        }}
        className="react-flow__edge-interaction"
      />
      {/* Visible edge */}
      <BaseEdge
        path={edgePath}
        markerEnd={markerEnd}
        interactionWidth={20}
        style={{
          ...style,
          strokeWidth: isHovered ? 3 : 2,
        }}
      />
      <EdgeLabelRenderer>
        {isHovered && (
          <div
            data-edge-id={id}
            style={{
              position: "absolute",
              transform: `translate(-50%, -50%) translate(${labelX}px,${labelY}px)`,
              pointerEvents: "all",
            }}
            className="nodrag nopan"
            onMouseEnter={() => showHover(true)}
            onMouseLeave={() => showHover(false)}
          >
            <Trash2
              className="h-3 w-3 text-red-500 cursor-pointer"
              onClick={handleDelete}
              aria-label="Delete edge"
            />
          </div>
        )}
      </EdgeLabelRenderer>
    </>
  );
}
