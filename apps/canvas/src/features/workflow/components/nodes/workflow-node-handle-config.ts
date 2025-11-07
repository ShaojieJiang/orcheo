import type { NodeHandleConfig, WorkflowNodeData } from "./workflow-node.types";

export const deriveInputHandles = (
  data: WorkflowNodeData,
): NodeHandleConfig[] => {
  if (data.hideInputHandle) {
    return [];
  }
  if (data.inputs && data.inputs.length > 0) {
    return data.inputs;
  }
  return [{ id: undefined }];
};

export const deriveOutputHandles = (
  data: WorkflowNodeData,
): NodeHandleConfig[] => {
  if (data.outputs && data.outputs.length > 0) {
    return data.outputs;
  }
  return [{ id: undefined }];
};
