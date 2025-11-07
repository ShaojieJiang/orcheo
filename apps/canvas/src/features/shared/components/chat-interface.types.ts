import type React from "react";
import type { UseChatKitOptions } from "@openai/chatkit-react";

import type { ChatMessageProps } from "@features/shared/components/chat-message";

export interface ChatParticipant {
  id: string;
  name: string;
  avatar?: string;
}

export interface ChatInterfaceProps {
  title?: string;
  initialMessages?: ChatMessageProps[];
  className?: string;
  isMinimizable?: boolean;
  isClosable?: boolean;
  position?:
    | "bottom-right"
    | "bottom-left"
    | "top-right"
    | "top-left"
    | "center";
  triggerButton?: React.ReactNode;
  user: ChatParticipant;
  ai: ChatParticipant;
  backendBaseUrl?: string;
  sessionPayload?: Record<string, unknown>;
  getClientSecret?: (currentSecret: string | null) => Promise<string>;
  chatkitOptions?: Partial<UseChatKitOptions>;
  onResponseStart?: () => void;
  onResponseEnd?: () => void;
  onThreadChange?: (threadId: string | null) => void;
  onLog?: (payload: Record<string, unknown>) => void;
}
