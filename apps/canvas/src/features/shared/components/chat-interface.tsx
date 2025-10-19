import React, { useState, useRef, useEffect } from "react";
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
import ChatMessage, {
  ChatMessageProps,
} from "@features/shared/components/chat-message";
import ChatInput, { Attachment } from "@features/shared/components/chat-input";

export interface ChatInterfaceProps {
  title?: string;
  initialMessages?: ChatMessageProps[];
  onSendMessage?: (message: string, attachments: Attachment[]) => void;
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
  user,
  ai,
}: ChatInterfaceProps) {
  const [messages, setMessages] = useState<ChatMessageProps[]>(initialMessages);
  const [isOpen, setIsOpen] = useState(false);
  const [isMinimized, setIsMinimized] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const handleSendMessage = (message: string, attachments: Attachment[]) => {
    if (!message.trim() && attachments.length === 0) return;

    const newMessage: ChatMessageProps = {
      id: `msg-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`,
      content: message,
      sender: user,
      timestamp: new Date(),
      isUserMessage: true,
      status: "sending",
      attachments: attachments.map((att) => ({
        id: att.id,
        type: att.type,
        name: att.file.name,
        url: att.previewUrl || URL.createObjectURL(att.file),
        size: formatFileSize(att.file.size),
      })),
    };

    setMessages((prev) => [...prev, newMessage]);

    // Simulate sending and response
    setTimeout(() => {
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === newMessage.id ? { ...msg, status: "sent" } : msg,
        ),
      );

      if (onSendMessage) {
        onSendMessage(message, attachments);
      }

      // Simulate AI response after a delay
      if (!onSendMessage) {
        setTimeout(() => {
          const aiResponse: ChatMessageProps = {
            id: `msg-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`,
            content: getAIResponse(message),
            sender: {
              ...ai,
              isAI: true,
            },
            timestamp: new Date(),
          };
          setMessages((prev) => [...prev, aiResponse]);
        }, 1000);
      }
    }, 500);
  };

  const getAIResponse = (message: string): string => {
    if (
      message.toLowerCase().includes("hello") ||
      message.toLowerCase().includes("hi")
    ) {
      return "Hello! How can I assist you with your workflow today?";
    } else if (message.toLowerCase().includes("help")) {
      return "I'm here to help! You can ask me about creating workflows, connecting nodes, or troubleshooting issues.";
    } else if (message.toLowerCase().includes("workflow")) {
      return "Workflows in Orcheo Canvas allow you to automate processes by connecting different nodes together. Would you like me to explain how to create one?";
    } else {
      return "I understand. Is there anything specific about the Orcheo Canvas platform you'd like to know more about?";
    }
  };

  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) return bytes + " B";
    else if (bytes < 1048576) return (bytes / 1024).toFixed(1) + " KB";
    else if (bytes < 1073741824) return (bytes / 1048576).toFixed(1) + " MB";
    else return (bytes / 1073741824).toFixed(1) + " GB";
  };

  const handleToggleMinimize = () => {
    setIsMinimized(!isMinimized);
  };

  const handleClose = () => {
    setIsOpen(false);
    setIsMinimized(false);
  };

  // Scroll to bottom when messages change
  useEffect(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages]);

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
          <div className="flex flex-col h-[60vh]">
            <div className="flex-1 overflow-y-auto p-2">
              {messages.length === 0 ? (
                <div className="flex flex-col items-center justify-center h-full text-muted-foreground">
                  <MessageSquare className="h-12 w-12 mb-2 opacity-20" />

                  <p>No messages yet</p>
                  <p className="text-sm">Start a conversation!</p>
                </div>
              ) : (
                messages.map((message) => (
                  <ChatMessage key={message.id} {...message} />
                ))
              )}
              <div ref={messagesEndRef} />
            </div>
            <ChatInput
              onSendMessage={handleSendMessage}
              placeholder="Type your message..."
              className="border-t"
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
              <div className="flex-1 overflow-y-auto p-2">
                {messages.length === 0 ? (
                  <div className="flex flex-col items-center justify-center h-full text-muted-foreground">
                    <MessageSquare className="h-12 w-12 mb-2 opacity-20" />

                    <p>No messages yet</p>
                    <p className="text-sm">Start a conversation!</p>
                  </div>
                ) : (
                  messages.map((message) => (
                    <ChatMessage key={message.id} {...message} />
                  ))
                )}
                <div ref={messagesEndRef} />
              </div>
              <ChatInput
                onSendMessage={handleSendMessage}
                placeholder="Type your message..."
                className="border-t"
              />
            </>
          )}
        </div>
      )}
    </>
  );
}
