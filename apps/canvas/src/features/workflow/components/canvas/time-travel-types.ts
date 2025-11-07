export type ExecutionStatus = "running" | "success" | "error" | "idle";

export interface ExecutionState {
  timestamp: string;
  nodeId: string;
  nodeName: string;
  state: ExecutionStatus;
  inputData?: Record<string, unknown>;
  outputData?: Record<string, unknown>;
  error?: string;
}

export interface TimeTravelDebuggerProps {
  states: ExecutionState[];
  onStateChange?: (state: ExecutionState) => void;
  onReplayComplete?: () => void;
  className?: string;
}
