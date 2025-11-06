import {
  determineNodeType,
  isRecord,
} from "@features/workflow/pages/workflow-canvas/helpers/validation";
import {
  DEFAULT_NODE_LABEL,
  createIdentityAllocator,
} from "@features/workflow/pages/workflow-canvas/helpers/node-identity";
import {
  DEFAULT_STICKY_NOTE_COLOR,
  DEFAULT_STICKY_NOTE_CONTENT,
  DEFAULT_STICKY_NOTE_HEIGHT,
  DEFAULT_STICKY_NOTE_WIDTH,
  STICKY_NOTE_MIN_HEIGHT,
  STICKY_NOTE_MIN_WIDTH,
  isStickyNoteColor,
  sanitizeStickyNoteContent,
  sanitizeStickyNoteDimension,
} from "@features/workflow/pages/workflow-canvas/helpers/sticky-notes";
import {
  getNodeIcon,
  inferNodeIconKey,
} from "@features/workflow/lib/node-icons";
import { defaultNodeStyle } from "@features/workflow/pages/workflow-canvas/helpers/transformers";

import type {
  CanvasNode,
  NodeData,
  NodeStatus,
  SidebarNodeDefinition,
} from "@features/workflow/pages/workflow-canvas/helpers/types";
import type { MutableRefObject } from "react";
import type { StickyNoteColor } from "@features/workflow/components/nodes/sticky-note-node";

export interface NodeBaseData {
  nodeType: string;
  baseDataRest: Partial<NodeData>;
  semanticType: string;
  nodeId: string;
  label: string;
  description: string;
}

export function buildNodeBaseData(
  node: SidebarNodeDefinition,
  nodesRef: MutableRefObject<CanvasNode[]>,
): NodeBaseData {
  const nodeType = determineNodeType(node.id);
  const baseDataRest: Partial<NodeData> = isRecord(node.data)
    ? { ...(node.data as Partial<NodeData>) }
    : {};
  delete baseDataRest.icon;
  delete baseDataRest.onOpenChat;

  const semanticType =
    nodeType === "startEnd"
      ? node.id === "start-node"
        ? "start"
        : "end"
      : typeof node.type === "string" && node.type.length > 0
        ? node.type
        : typeof baseDataRest.type === "string" && baseDataRest.type.length > 0
          ? baseDataRest.type
          : "default";
  const baseLabel =
    typeof node.name === "string" && node.name.length > 0
      ? node.name
      : typeof baseDataRest.label === "string" && baseDataRest.label.length > 0
        ? baseDataRest.label
        : DEFAULT_NODE_LABEL;
  const allocateIdentity = createIdentityAllocator(nodesRef.current);
  const { id: nodeId, label } = allocateIdentity(baseLabel);
  const description =
    typeof node.description === "string" && node.description.length > 0
      ? node.description
      : typeof baseDataRest.description === "string"
        ? baseDataRest.description
        : "";

  return {
    nodeType,
    baseDataRest,
    semanticType,
    nodeId,
    label,
    description,
  };
}

export function createStickyNode(
  base: NodeBaseData,
  position: { x: number; y: number },
  handleUpdateStickyNoteNode: (nodeId: string, data: Partial<NodeData>) => void,
): CanvasNode {
  return {
    id: base.nodeId,
    type: "stickyNote",
    position,
    style: defaultNodeStyle,
    data: {
      ...base.baseDataRest,
      label: base.label,
      description: base.description,
      type: base.semanticType,
      status: "idle" as NodeStatus,
      color: isStickyNoteColor(base.baseDataRest.color)
        ? (base.baseDataRest.color as StickyNoteColor)
        : DEFAULT_STICKY_NOTE_COLOR,
      content: sanitizeStickyNoteContent(
        base.baseDataRest.content ?? DEFAULT_STICKY_NOTE_CONTENT,
      ),
      width: sanitizeStickyNoteDimension(
        base.baseDataRest.width,
        DEFAULT_STICKY_NOTE_WIDTH,
        STICKY_NOTE_MIN_WIDTH,
      ),
      height: sanitizeStickyNoteDimension(
        base.baseDataRest.height,
        DEFAULT_STICKY_NOTE_HEIGHT,
        STICKY_NOTE_MIN_HEIGHT,
      ),
      onUpdateStickyNote: handleUpdateStickyNoteNode,
    },
    draggable: true,
    connectable: false,
  };
}

export function createStandardNode(
  base: NodeBaseData,
  position: { x: number; y: number },
  handleOpenChat: (nodeId: string) => void,
): CanvasNode {
  const rawIconKey =
    typeof base.baseDataRest.iconKey === "string"
      ? base.baseDataRest.iconKey
      : undefined;
  const finalIconKey =
    inferNodeIconKey({
      iconKey: rawIconKey,
      label: base.label,
      type: base.semanticType,
    }) ?? rawIconKey;
  const iconNode = getNodeIcon(finalIconKey) ?? base.baseDataRest.icon;

  return {
    id: base.nodeId,
    type: base.nodeType,
    position,
    style: defaultNodeStyle,
    data: {
      ...base.baseDataRest,
      label: base.label,
      description: base.description,
      type: base.semanticType,
      status: "idle" as NodeStatus,
      iconKey: finalIconKey,
      icon: iconNode,
      onOpenChat:
        base.nodeType === "chatTrigger"
          ? () => handleOpenChat(base.nodeId)
          : undefined,
    },
    draggable: true,
  };
}
