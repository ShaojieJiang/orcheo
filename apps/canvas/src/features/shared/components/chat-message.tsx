import React from "react";
import { Avatar, AvatarFallback, AvatarImage } from "@/design-system/ui/avatar";
import { cn } from "@/lib/utils";
import { CheckIcon } from "lucide-react";

import ChatAttachmentList, { ChatAttachment } from "./chat-message-attachments";
import { parseChatMarkdown } from "./chat-message-markdown";

export interface ChatMessageProps {
  id: string;
  content: string;
  sender: {
    id: string;
    name: string;
    avatar?: string;
    isAI?: boolean;
  };
  timestamp: Date | string;
  attachments?: ChatAttachment[];
  status?: "sending" | "sent" | "delivered" | "read" | "error";
  isUserMessage?: boolean;
}

export default function ChatMessage({
  content,
  sender,
  timestamp,
  attachments = [],
  status = "sent",
  isUserMessage = false,
}: ChatMessageProps) {
  const formattedTime =
    typeof timestamp === "string"
      ? new Date(timestamp).toLocaleTimeString([], {
          hour: "2-digit",
          minute: "2-digit",
        })
      : timestamp.toLocaleTimeString([], {
          hour: "2-digit",
          minute: "2-digit",
        });

  return (
    <div
      className={cn(
        "flex w-full gap-3 p-2",
        isUserMessage ? "justify-end" : "justify-start",
      )}
    >
      {!isUserMessage && (
        <Avatar className="h-8 w-8">
          {sender.avatar ? (
            <AvatarImage src={sender.avatar} alt={sender.name} />
          ) : (
            <AvatarFallback
              className={
                sender.isAI ? "bg-primary text-primary-foreground" : ""
              }
            >
              {sender.name.substring(0, 2).toUpperCase()}
            </AvatarFallback>
          )}
        </Avatar>
      )}

      <div
        className={cn(
          "flex flex-col gap-1",
          isUserMessage ? "items-end" : "items-start",
        )}
      >
        <div className="flex items-center gap-2">
          <span className="text-xs text-muted-foreground">
            {isUserMessage ? "You" : sender.name}
          </span>
          <span className="text-xs text-muted-foreground">{formattedTime}</span>
        </div>

        <div
          className={cn(
            "rounded-lg px-4 py-2 max-w-[80%]",
            isUserMessage
              ? "bg-primary text-primary-foreground"
              : "bg-muted text-foreground dark:text-foreground/90",
          )}
        >
          <div
            className="prose prose-sm dark:prose-invert max-w-none"
            dangerouslySetInnerHTML={{ __html: parseChatMarkdown(content) }}
          ></div>
        </div>

        <ChatAttachmentList
          attachments={attachments}
          isUserMessage={isUserMessage}
        />

        {isUserMessage && status && (
          <div className="flex items-center text-xs text-muted-foreground mt-1">
            {status === "sending" && "Sending..."}
            {status === "sent" && "Sent"}
            {status === "delivered" && "Delivered"}
            {status === "read" && (
              <>
                <CheckIcon className="h-3 w-3 mr-1" /> Read
              </>
            )}
            {status === "error" && (
              <span className="text-destructive">Failed to send</span>
            )}
          </div>
        )}
      </div>

      {isUserMessage && (
        <Avatar className="h-8 w-8">
          {sender.avatar ? (
            <AvatarImage src={sender.avatar} alt={sender.name} />
          ) : (
            <AvatarFallback>
              {sender.name.substring(0, 2).toUpperCase()}
            </AvatarFallback>
          )}
        </Avatar>
      )}
    </div>
  );
}
