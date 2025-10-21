import React, { useCallback, useMemo, useState } from "react";
import { Button } from "@/design-system/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/design-system/ui/dialog";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/design-system/ui/tooltip";
import { cn } from "@/lib/utils";
import { buildBackendHttpUrl } from "@/lib/config";
import {
  ChatKit,
  useChatKit,
  type UseChatKitOptions,
} from "@openai/chatkit-react";
import { MessageSquare, MinimizeIcon, XIcon } from "lucide-react";
import type { ChatMessageProps } from "@features/shared/components/chat-message";

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
  user: {
    id: string;
    name: string;
    avatar?: string;
  };
  ai: {
    id: string;
    name: string;
    avatar?: string;
  };
  backendBaseUrl?: string;
  sessionPayload?: Record<string, unknown>;
  getClientSecret?: (currentSecret: string | null) => Promise<string>;
  chatkitOptions?: Partial<UseChatKitOptions>;
  onResponseStart?: () => void;
  onResponseEnd?: () => void;
  onThreadChange?: (threadId: string | null) => void;
  onLog?: (payload: Record<string, unknown>) => void;
}

export default function ChatInterface({
  title = "Chat",
  initialMessages = [],
  className,
  isMinimizable = true,
  isClosable = true,
  position = "bottom-right",
  triggerButton,
  user,
  ai,
  backendBaseUrl,
  sessionPayload,
  getClientSecret,
  chatkitOptions,
  onResponseStart,
  onResponseEnd,
  onThreadChange,
  onLog,
}: ChatInterfaceProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [isMinimized, setIsMinimized] = useState(false);

  const initialGreeting = initialMessages.find(
    (message) =>
      typeof message.content === "string" && message.sender?.id === ai.id,
  )?.content as string | undefined;

  const resolveSessionSecret = useCallback(
    async (currentSecret: string | null) => {
      if (getClientSecret) {
        return getClientSecret(currentSecret);
      }

      const url = buildBackendHttpUrl("/api/chatkit/session", backendBaseUrl);
      const response = await fetch(url, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          current_client_secret: currentSecret,
          currentClientSecret: currentSecret,
          user,
          assistant: ai,
          metadata: {
            title,
            ...sessionPayload,
          },
        }),
      });

      if (!response.ok) {
        throw new Error("Failed to fetch ChatKit client secret");
      }

      const data = (await response.json()) as {
        client_secret?: string;
        clientSecret?: string;
      };

      const secret = data.client_secret ?? data.clientSecret;
      if (!secret) {
        throw new Error("ChatKit session response missing client secret");
      }
      return secret;
    },
    [ai, backendBaseUrl, getClientSecret, sessionPayload, title, user],
  );

  const composeHandlers = useCallback(
    <T extends unknown[]>(
      ...handlers: Array<((...args: T) => void) | undefined>
    ) => {
      const valid = handlers.filter(Boolean) as Array<(...args: T) => void>;
      if (valid.length === 0) {
        return undefined;
      }
      return (...args: T) => {
        valid.forEach((handler) => handler(...args));
      };
    },
    [],
  );

  const options = useMemo<UseChatKitOptions>(() => {
    const merged = {
      ...(chatkitOptions as UseChatKitOptions),
    } as UseChatKitOptions;

    merged.api = {
      ...(chatkitOptions?.api ?? {}),
      getClientSecret:
        chatkitOptions?.api?.getClientSecret ?? resolveSessionSecret,
    };

    if (!merged.header) {
      merged.header = {
        enabled: true,
        title: {
          enabled: true,
          text: title,
        },
      };
    }

    if (!merged.startScreen && initialGreeting) {
      merged.startScreen = {
        greeting: initialGreeting,
      };
    }

    merged.onResponseStart = composeHandlers(
      chatkitOptions?.onResponseStart,
      onResponseStart,
    );
    merged.onResponseEnd = composeHandlers(
      chatkitOptions?.onResponseEnd,
      onResponseEnd,
    );
    merged.onThreadChange = composeHandlers(
      chatkitOptions?.onThreadChange,
      onThreadChange,
    );
    merged.onThreadLoadStart = chatkitOptions?.onThreadLoadStart;
    merged.onThreadLoadEnd = chatkitOptions?.onThreadLoadEnd;
    merged.onLog = composeHandlers(chatkitOptions?.onLog, onLog);
    merged.onError = chatkitOptions?.onError;

    return merged;
  }, [
    chatkitOptions,
    composeHandlers,
    initialGreeting,
    onLog,
    onResponseEnd,
    onResponseStart,
    onThreadChange,
    resolveSessionSecret,
    title,
  ]);

  const { control } = useChatKit(options);

  const handleToggleMinimize = () => {
    setIsMinimized(!isMinimized);
  };

  const handleClose = () => {
    setIsOpen(false);
    setIsMinimized(false);
  };

  // Position classes
  const positionClasses = {
    "bottom-right": "bottom-4 right-4",
    "bottom-left": "bottom-4 left-4",
    "top-right": "top-4 right-4",
    "top-left": "top-4 left-4",
    center: "bottom-1/2 right-1/2 transform translate-x-1/2 translate-y-1/2",
  };

  // If using Dialog mode (with trigger button)
  if (triggerButton) {
    return (
      <Dialog open={isOpen} onOpenChange={setIsOpen}>
        <DialogTrigger asChild>{triggerButton}</DialogTrigger>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>{title}</DialogTitle>
          </DialogHeader>
          <div className="flex h-[60vh] flex-col">
            <ChatKit
              control={control}
              className="flex h-full w-full flex-col"
            />
          </div>
        </DialogContent>
      </Dialog>
    );
  }

  // Floating chat interface
  return (
    <>
      {!isOpen && (
        <TooltipProvider>
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                onClick={() => setIsOpen(true)}
                className="rounded-full h-14 w-14 shadow-lg fixed z-50 bottom-4 right-4"
              >
                <MessageSquare className="h-6 w-6" />
              </Button>
            </TooltipTrigger>
            <TooltipContent>Open chat</TooltipContent>
          </Tooltip>
        </TooltipProvider>
      )}

      {isOpen && (
        <div
          className={cn(
            "fixed z-50 flex flex-col rounded-lg shadow-lg bg-background border",
            positionClasses[position],
            isMinimized ? "w-72 h-12" : "w-80 sm:w-96 h-[500px]",
            className,
          )}
        >
          <div className="flex items-center justify-between p-3 border-b">
            <h3 className="font-medium truncate">{title}</h3>
            <div className="flex items-center gap-1">
              {isMinimizable && (
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-6 w-6"
                  onClick={handleToggleMinimize}
                >
                  <MinimizeIcon className="h-4 w-4" />
                </Button>
              )}
              {isClosable && (
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-6 w-6"
                  onClick={handleClose}
                >
                  <XIcon className="h-4 w-4" />
                </Button>
              )}
            </div>
          </div>

          {!isMinimized && (
            <>
              <div className="flex-1 overflow-hidden">
                <ChatKit
                  control={control}
                  className="flex h-full w-full flex-col"
                />
              </div>
            </>
          )}
        </div>
      )}
    </>
  );
}
