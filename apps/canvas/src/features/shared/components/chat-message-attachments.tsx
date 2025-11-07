import React from "react";
import { FileIcon, FileTextIcon } from "lucide-react";

import { cn } from "@/lib/utils";

export type ChatAttachment = {
  id: string;
  type: "image" | "video" | "file" | "code";
  name: string;
  url?: string;
  content?: string;
  language?: string;
  size?: string;
};

interface ChatAttachmentListProps {
  attachments: ChatAttachment[];
  isUserMessage: boolean;
}

const MediaOverlay: React.FC<{ title: string }> = ({ title }) => (
  <div className="absolute bottom-0 left-0 right-0 bg-black/50 text-white text-xs p-1 truncate">
    {title}
  </div>
);

const ChatAttachmentList: React.FC<ChatAttachmentListProps> = ({
  attachments,
  isUserMessage,
}) => {
  if (!attachments.length) {
    return null;
  }

  return (
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
              <MediaOverlay title={attachment.name} />
            </div>
          )}

          {attachment.type === "video" && attachment.url && (
            <div className="relative">
              <video
                src={attachment.url}
                controls
                className="w-full h-auto rounded-lg"
              />
              <MediaOverlay title={attachment.name} />
            </div>
          )}

          {attachment.type === "file" && (
            <div
              className={cn(
                "flex items-center gap-2 p-2",
                isUserMessage ? "text-primary-foreground" : "text-foreground",
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
                  <div className="text-xs opacity-70">{attachment.size}</div>
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
  );
};

export default ChatAttachmentList;
