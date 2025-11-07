import React from "react";
import { Button } from "@/design-system/ui/button";
import { FileIcon, VideoIcon, XIcon } from "lucide-react";
import type { Attachment } from "@/features/shared/components/chat-input/chat-input-types";

interface AttachmentPreviewProps {
  attachments: Attachment[];
  onRemoveAttachment: (id: string) => void;
}

export default function AttachmentPreview({
  attachments,
  onRemoveAttachment,
}: AttachmentPreviewProps) {
  if (attachments.length === 0) {
    return null;
  }

  return (
    <div className="flex flex-wrap gap-2 rounded-md bg-muted/50 p-2">
      {attachments.map((attachment) => (
        <div
          key={attachment.id}
          className="group relative overflow-hidden rounded-md border border-border"
        >
          {attachment.type === "image" && attachment.previewUrl ? (
            <div className="relative h-16 w-16">
              <img
                src={attachment.previewUrl}
                alt={attachment.file.name}
                className="h-full w-full object-cover"
              />
              <OverlayRemoveButton
                onRemove={() => onRemoveAttachment(attachment.id)}
              />
            </div>
          ) : attachment.type === "video" && attachment.previewUrl ? (
            <div className="relative flex h-16 w-16 items-center justify-center bg-black">
              <VideoIcon className="h-6 w-6 text-white" />
              <OverlayRemoveButton
                onRemove={() => onRemoveAttachment(attachment.id)}
              />
            </div>
          ) : (
            <div className="relative flex h-16 w-16 flex-col items-center justify-center bg-muted p-1">
              <FileIcon className="h-6 w-6" />
              <div className="w-full truncate text-center text-xs">
                {attachment.file.name.split(".").pop()}
              </div>
              <OverlayRemoveButton
                onRemove={() => onRemoveAttachment(attachment.id)}
              />
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

interface OverlayRemoveButtonProps {
  onRemove: () => void;
}

function OverlayRemoveButton({ onRemove }: OverlayRemoveButtonProps) {
  return (
    <div className="absolute inset-0 flex items-center justify-center bg-black/40 opacity-0 transition-opacity group-hover:opacity-100">
      <Button
        variant="ghost"
        size="icon"
        className="h-6 w-6 text-white"
        onClick={onRemove}
      >
        <XIcon className="h-4 w-4" />
      </Button>
    </div>
  );
}
