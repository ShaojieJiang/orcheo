import { useEffect, useMemo, useState } from "react";
import type { StartScreenPrompt } from "@openai/chatkit";
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
import { buildBackendHttpUrl } from "@/lib/config";
import { cn } from "@/lib/utils";
import { MessageSquare, MinimizeIcon, XIcon } from "lucide-react";

const DEFAULT_DOMAIN_KEY = "domain_pk_orcheo_dev";
const DEFAULT_PLACEHOLDER = "Describe what you want the workflow to do";

export interface ChatInterfaceProps {
  title?: string;
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
  workflowId?: string | null;
  chatNodeId?: string | null;
  chatNodeLabel?: string | null;
  domainKey?: string;
  greeting?: string;
  starterPrompts?: StartScreenPrompt[];
  composerPlaceholder?: string;
  onResponseStart?: () => void;
  onResponseEnd?: () => void;
}

export default function ChatInterface({
  title = "Chat",
  className,
  isMinimizable = true,
  isClosable = true,
  position = "bottom-right",
  triggerButton,
  workflowId,
  chatNodeId,
  chatNodeLabel,
  domainKey,
  greeting,
  starterPrompts,
  composerPlaceholder = DEFAULT_PLACEHOLDER,
  onResponseStart,
  onResponseEnd,
}: ChatInterfaceProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [isMinimized, setIsMinimized] = useState(false);

  const backendUrl = useMemo(() => buildBackendHttpUrl("/api/chatkit"), []);

  const startScreen = useMemo(() => {
    if (!greeting && (!starterPrompts || starterPrompts.length === 0)) {
      return undefined;
    }
    return {
      greeting: greeting ?? undefined,
      prompts: starterPrompts,
    };
  }, [greeting, starterPrompts]);

  const chatkit = useChatKit({
    api: {
      url: backendUrl,
      domainKey: domainKey ?? DEFAULT_DOMAIN_KEY,
      fetch: (url: string, init?: RequestInit) => {
        const headers = new Headers(init?.headers ?? {});
        if (workflowId) {
          headers.set("x-orcheo-chat-workflow-id", workflowId);
        }
        if (chatNodeId) {
          headers.set("x-orcheo-chat-node-id", chatNodeId);
        }
        if (chatNodeLabel) {
          headers.set("x-orcheo-chat-node-name", chatNodeLabel);
        }
        return fetch(url, { ...init, headers });
      },
    },
    header: {
      title: {
        enabled: true,
        text: title,
      },
    },
    startScreen,
    history: { enabled: true },
    composer: {
      placeholder: composerPlaceholder,
    },
    onResponseStart: () => {
      onResponseStart?.();
    },
    onResponseEnd: () => {
      onResponseEnd?.();
    },
    onError: ({ error }) => {
      console.error("ChatKit error", error);
    },
  });

  const { control, focusComposer } = chatkit;

  useEffect(() => {
    if (isOpen && !isMinimized) {
      void focusComposer().catch(() => undefined);
    }
  }, [isOpen, isMinimized, focusComposer]);

  const positionClasses = {
    "bottom-right": "bottom-4 right-4",
    "bottom-left": "bottom-4 left-4",
    "top-right": "top-4 right-4",
    "top-left": "top-4 left-4",
    center: "bottom-1/2 right-1/2 translate-x-1/2 translate-y-1/2",
  } as const;

  const handleToggleMinimize = () => {
    setIsMinimized((prev) => !prev);
  };

  const handleClose = () => {
    setIsOpen(false);
    setIsMinimized(false);
  };

  if (triggerButton) {
    return (
      <Dialog open={isOpen} onOpenChange={setIsOpen}>
        <DialogTrigger asChild>{triggerButton}</DialogTrigger>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>{title}</DialogTitle>
          </DialogHeader>
          <div className="h-[60vh]">
            <ChatKit control={control} className="h-full w-full" />
          </div>
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
            positionClasses[position],
            isMinimized ? "h-12 w-72" : "h-[500px] w-80 sm:w-96",
            className,
          )}
        >
          <div className="flex items-center justify-between border-b p-3">
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
            <div className="flex-1 min-h-0">
              <ChatKit control={control} className="h-full w-full" />
            </div>
          )}
        </div>
      )}
    </>
  );
}
