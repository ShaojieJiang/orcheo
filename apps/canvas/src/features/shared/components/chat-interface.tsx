import React, { useCallback, useEffect, useMemo, useState } from "react";
import { ChatKit, useChatKit } from "@openai/chatkit-react";
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
import { MessageSquare, MinimizeIcon, XIcon } from "lucide-react";
import type { ChatMessageProps } from "@features/shared/components/chat-message";
import type { Attachment } from "@features/shared/components/chat-input";

type Position =
  | "bottom-right"
  | "bottom-left"
  | "top-right"
  | "top-left"
  | "center";

export interface ChatInterfaceProps {
  title?: string;
  initialMessages?: ChatMessageProps[];
  onSendMessage?: (message: string, attachments: Attachment[]) => void;
  className?: string;
  isMinimizable?: boolean;
  isClosable?: boolean;
  position?: Position;
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
}

const POSITION_CLASSES: Record<Position, string> = {
  "bottom-right": "bottom-4 right-4",
  "bottom-left": "bottom-4 left-4",
  "top-right": "top-4 right-4",
  "top-left": "top-4 left-4",
  center: "bottom-1/2 right-1/2 translate-x-1/2 translate-y-1/2",
};

const FALLBACK_GREETING = "How can I help you test this workflow?";

const getDefaultApiUrl = () => {
  if (typeof window === "undefined") {
    return "/api/chatkit";
  }
  return `${window.location.origin}/api/chatkit`;
};

const getDefaultDomainKey = () => {
  if (typeof window === "undefined") {
    return "localhost";
  }
  return window.location.hostname || "localhost";
};

function extractUserMessage(payload: unknown): string | null {
  if (!payload || typeof payload !== "object") {
    return null;
  }

  if (
    !("type" in payload) ||
    (payload as { type: unknown }).type !== "threads.addUserMessage"
  ) {
    return null;
  }

  const params = (payload as { params?: unknown }).params;
  if (!params || typeof params !== "object") {
    return null;
  }

  const input = (params as { input?: unknown }).input;
  if (!input || typeof input !== "object") {
    return null;
  }

  const content = (input as { content?: unknown }).content;
  if (!Array.isArray(content)) {
    return null;
  }

  const parts = content
    .map((part) => {
      if (!part || typeof part !== "object") {
        return null;
      }
      if ((part as { type?: unknown }).type === "input_text") {
        const text = (part as { text?: unknown }).text;
        return typeof text === "string" ? text : null;
      }
      return null;
    })
    .filter((value): value is string => Boolean(value));

  if (parts.length === 0) {
    return null;
  }

  return parts.join(" ").trim();
}

function useChatKitScriptStatus() {
  const [status, setStatus] = useState<"pending" | "ready" | "error">(() => {
    if (typeof window === "undefined") {
      return "pending";
    }
    return window.customElements?.get("openai-chatkit") ? "ready" : "pending";
  });
  const [errorDetail, setErrorDetail] = useState<string | null>(null);

  useEffect(() => {
    const handleLoaded = () => {
      setStatus("ready");
      setErrorDetail(null);
    };

    const handleError = (event: Event) => {
      setStatus("error");
      const detail = (event as CustomEvent<unknown>).detail;
      if (typeof detail === "string") {
        setErrorDetail(detail);
      } else if (detail && typeof detail === "object" && "message" in detail) {
        const message = (detail as { message?: unknown }).message;
        setErrorDetail(typeof message === "string" ? message : null);
      } else {
        setErrorDetail("Unable to load ChatKit script.");
      }
    };

    window.addEventListener("chatkit-script-loaded", handleLoaded);
    window.addEventListener(
      "chatkit-script-error",
      handleError as EventListener,
    );

    if (window.customElements?.get("openai-chatkit")) {
      handleLoaded();
    }

    return () => {
      window.removeEventListener("chatkit-script-loaded", handleLoaded);
      window.removeEventListener(
        "chatkit-script-error",
        handleError as EventListener,
      );
    };
  }, []);

  return { status, errorDetail } as const;
}

export default function ChatInterface({
  title = "Chat",
  initialMessages = [],
  onSendMessage,
  className,
  isMinimizable = true,
  isClosable = true,
  position = "bottom-right",
  triggerButton,
}: ChatInterfaceProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [isMinimized, setIsMinimized] = useState(false);
  const { status: scriptStatus, errorDetail } = useChatKitScriptStatus();

  const defaultApiUrl = useMemo(getDefaultApiUrl, []);
  const defaultDomainKey = useMemo(getDefaultDomainKey, []);

  const backendBase = useMemo(() => {
    const raw = import.meta.env.VITE_ORCHEO_BACKEND_URL;
    if (!raw) {
      return undefined;
    }
    return raw.endsWith("/") ? raw.slice(0, -1) : raw;
  }, []);

  const resolvedDefaultApiUrl = backendBase
    ? `${backendBase}/api/chatkit`
    : defaultApiUrl;

  const apiUrl = import.meta.env.VITE_CHATKIT_API_URL ?? resolvedDefaultApiUrl;
  const domainKey = import.meta.env.VITE_CHATKIT_DOMAIN_KEY ?? defaultDomainKey;

  const greeting = useMemo(() => {
    const first = initialMessages.at(0)?.content;
    if (typeof first === "string" && first.trim().length > 0) {
      return first.trim();
    }
    return FALLBACK_GREETING;
  }, [initialMessages]);

  const starterPrompts = useMemo(() => {
    if (initialMessages.length <= 1) {
      return undefined;
    }
    return initialMessages.slice(1).map((message) => ({
      id: message.id,
      title: message.sender?.name ?? "Suggestion",
      prompt: message.content,
    }));
  }, [initialMessages]);

  const chatkitFetch = useCallback(
    async (input: RequestInfo | URL, init?: RequestInit) => {
      if (onSendMessage && init?.body && typeof init.body === "string") {
        try {
          const parsed = JSON.parse(init.body) as unknown;
          const userMessage = extractUserMessage(parsed);
          if (userMessage) {
            onSendMessage(userMessage, []);
          }
        } catch (error) {
          console.warn("Failed to parse ChatKit request payload", error);
        }
      }
      return fetch(input, init);
    },
    [onSendMessage],
  );

  const chatkit = useChatKit(
    useMemo(
      () => ({
        api: {
          url: apiUrl,
          domainKey,
          fetch: chatkitFetch,
        },
        header: {
          enabled: true,
          title: { text: title },
        },
        startScreen: {
          greeting,
          prompts: starterPrompts,
        },
        composer: {
          placeholder: "Type your message...",
          attachments: { enabled: false },
        },
        threadItemActions: {
          feedback: false,
        },
      }),
      [apiUrl, chatkitFetch, domainKey, greeting, starterPrompts, title],
    ),
  );

  useEffect(() => {
    if (!isOpen) {
      setIsMinimized(false);
    }
  }, [isOpen]);

  const chatContent = (
    <div className="flex h-full flex-col">
      {scriptStatus === "ready" ? (
        <ChatKit control={chatkit.control} className="h-full w-full" />
      ) : (
        <div className="flex h-full flex-col items-center justify-center gap-2 p-4 text-center text-sm text-muted-foreground">
          <MessageSquare className="h-10 w-10 opacity-20" />
          <p>
            {scriptStatus === "pending"
              ? "Loading chat interface..."
              : (errorDetail ?? "Chat interface unavailable.")}
          </p>
        </div>
      )}
    </div>
  );

  if (triggerButton) {
    return (
      <Dialog open={isOpen} onOpenChange={setIsOpen}>
        <DialogTrigger asChild>{triggerButton}</DialogTrigger>
        <DialogContent className={cn("sm:max-w-xl", className)}>
          <DialogHeader>
            <DialogTitle>{title}</DialogTitle>
          </DialogHeader>
          <div className="h-[60vh]">{chatContent}</div>
        </DialogContent>
      </Dialog>
    );
  }

  return (
    <>
      {!isOpen && (
        <TooltipProvider>
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                onClick={() => setIsOpen(true)}
                className="fixed bottom-4 right-4 z-50 h-14 w-14 rounded-full shadow-lg"
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
            "fixed z-50 flex flex-col rounded-lg border bg-background shadow-lg",
            POSITION_CLASSES[position],
            isMinimized ? "h-12 w-72" : "h-[500px] w-80 sm:w-96",
            className,
          )}
        >
          <div className="flex items-center justify-between gap-2 border-b p-3">
            <h3 className="truncate font-medium">{title}</h3>
            <div className="flex items-center gap-1">
              {isMinimizable && (
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-6 w-6"
                  onClick={() => setIsMinimized((prev) => !prev)}
                >
                  <MinimizeIcon className="h-4 w-4" />
                </Button>
              )}
              {isClosable && (
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-6 w-6"
                  onClick={() => setIsOpen(false)}
                >
                  <XIcon className="h-4 w-4" />
                </Button>
              )}
            </div>
          </div>
          {!isMinimized && <div className="flex-1">{chatContent}</div>}
        </div>
      )}
    </>
  );
}
