import type { ChatMessageProps } from "@features/shared/components/chat-message";
import type { ExecutionStatus } from "@features/workflow/hooks/use-workflow-execution";

export type ChatEnvironment = "draft" | "production";

export interface ChatKitParticipant {
  id: string;
  name: string;
  avatar?: string;
  role?: "user" | "ai" | "observer" | "reviewer";
  status?: "online" | "offline" | "away";
}

export interface ChatKitChecklistItem {
  id: string;
  label: string;
  completed: boolean;
  owner?: string;
  dueDate?: string;
}

export interface ChatKitRunSummary {
  id: string;
  status: ExecutionStatus;
  environment: ChatEnvironment;
  startedAt: string;
  durationMs?: number;
  triggeredBy?: string;
  tokens?: {
    prompt: number;
    completion: number;
    total: number;
  };
  notes?: string;
}

export interface ChatKitSession {
  id: string;
  nodeId?: string;
  title: string;
  subtitle?: string;
  description?: string;
  environment: ChatEnvironment;
  status?: ExecutionStatus | "handoff" | "handoff-ready" | "qa";
  pinned?: boolean;
  updatedAt: string;
  messages: ChatMessageProps[];
  participants: ChatKitParticipant[];
  quickPrompts?: string[];
  handoffChecklist?: ChatKitChecklistItem[];
  runSummaries?: ChatKitRunSummary[];
  tags?: string[];
  unreadCount?: number;
  tokenEstimate?: {
    prompt: number;
    completion: number;
    total: number;
  };
}

export interface ChatKitMetrics {
  tokens?: {
    total: number;
    prompt: number;
    completion: number;
  };
  averageLatencyMs?: number;
  runsToday?: number;
  lastExecutionStatus?: ExecutionStatus;
  lastExecutionStartedAt?: string | null;
}
