import React, { useState } from "react";
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

import { ChatKitSurface } from "@features/chatkit/components/chatkit-surface";
import { useChatInterfaceOptions } from "./chat-interface-options";
import type { ChatInterfaceProps } from "./chat-interface.types";

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
  workflowId,
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

  const chatKitOptions = useChatInterfaceOptions({
    chatkitOptions,
    getClientSecret,
    backendBaseUrl,
    workflowId,
    sessionPayload,
    title,
    user,
    ai,
    initialMessages,
    onResponseStart,
    onResponseEnd,
    onThreadChange,
    onLog,
  });

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
            <ChatKitSurface options={chatKitOptions} />
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
                <ChatKitSurface options={chatKitOptions} />
              </div>
            </>
          )}
        </div>
      )}
    </>
  );
}
