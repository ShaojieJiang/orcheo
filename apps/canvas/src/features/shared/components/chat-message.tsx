import React from "react";
import { Avatar, AvatarFallback, AvatarImage } from "@/design-system/ui/avatar";
import { cn } from "@/lib/utils";
import { CheckIcon, FileIcon, FileTextIcon } from "lucide-react";

// Simple markdown parser function
const parseMarkdown = (text: string): string => {
  // Handle bold text
  let parsedText = text.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>");

  // Handle italic text
  parsedText = parsedText.replace(/\*(.*?)\*/g, "<em>$1</em>");

  // Handle code blocks
  parsedText = parsedText.replace(
    /```(.*?)```/gs,
    "<pre><code>$1</code></pre>",
  );

  // Handle inline code
  parsedText = parsedText.replace(/`(.*?)`/g, "<code>$1</code>");

  // Handle links
  parsedText = parsedText.replace(
    /\[(.*?)\]\((.*?)\)/g,
    '<a href="$2" target="_blank" rel="noopener noreferrer" class="text-primary underline">$1</a>',
  );

  // Handle lists
  parsedText = parsedText.replace(/^\d+\.\s+(.*?)$/gm, "<li>$1</li>");
  parsedText = parsedText.replace(/^-\s+(.*?)$/gm, "<li>$1</li>");

  // Handle paragraphs
  parsedText = parsedText.replace(/\n\n/g, "</p><p>");

  // Handle line breaks
  parsedText = parsedText.replace(/\n/g, "<br/>");

  return `<p>${parsedText}</p>`;
};

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
  attachments?: Array<{
    id: string;
    type: "image" | "video" | "file" | "code";
    name: string;
    url?: string;
    content?: string;
    language?: string;
    size?: string;
  }>;
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
            dangerouslySetInnerHTML={{ __html: parseMarkdown(content) }}
          ></div>
        </div>

        {attachments.length > 0 && (
          <div className="flex flex-col gap-2 mt-1">
            {attachments.map((attachment) => (
              <div
                key={attachment.id}
                className={cn(
                  "rounded-lg overflow-hidden",
                  isUserMessage ? "bg-primary/80" : "bg-muted/80",
                  attachment.type === "image" ? "max-w-xs" : "max-w-sm",
                )}
              >
                {attachment.type === "image" && attachment.url && (
                  <div className="relative">
                    <img
                      src={attachment.url}
                      alt={attachment.name}
                      className="w-full h-auto rounded-lg"
                    />

                    <div className="absolute bottom-0 left-0 right-0 bg-black/50 text-white text-xs p-1 truncate">
                      {attachment.name}
                    </div>
                  </div>
                )}

                {attachment.type === "video" && attachment.url && (
                  <div className="relative">
                    <video
                      src={attachment.url}
                      controls
                      className="w-full h-auto rounded-lg"
                    />

                    <div className="absolute bottom-0 left-0 right-0 bg-black/50 text-white text-xs p-1 truncate">
                      {attachment.name}
                    </div>
                  </div>
                )}

                {attachment.type === "file" && (
                  <div
                    className={cn(
                      "flex items-center gap-2 p-2",
                      isUserMessage
                        ? "text-primary-foreground"
                        : "text-foreground",
                    )}
                  >
                    <div className="p-2 rounded-md bg-background/20">
                      {attachment.name.endsWith(".pdf") ? (
                        <FileTextIcon className="h-6 w-6" />
                      ) : (
                        <FileIcon className="h-6 w-6" />
                      )}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-medium truncate">
                        {attachment.name}
                      </div>
                      {attachment.size && (
                        <div className="text-xs opacity-70">
                          {attachment.size}
                        </div>
                      )}
                    </div>
                    <a
                      href={attachment.url}
                      download={attachment.name}
                      className={cn(
                        "text-xs px-2 py-1 rounded-md",
                        isUserMessage
                          ? "bg-primary-foreground/20 hover:bg-primary-foreground/30 text-primary-foreground"
                          : "bg-background/20 hover:bg-background/30",
                      )}
                    >
                      Download
                    </a>
                  </div>
                )}

                {attachment.type === "code" && attachment.content && (
                  <div className="p-1">
                    <div className="text-xs px-3 py-1 bg-background/20 rounded-t-md flex justify-between">
                      <span>{attachment.language || "Code"}</span>
                      <span className="opacity-70">{attachment.name}</span>
                    </div>
                    <pre className="bg-black text-white p-3 text-sm overflow-x-auto rounded-b-md">
                      <code>{attachment.content}</code>
                    </pre>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}

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
