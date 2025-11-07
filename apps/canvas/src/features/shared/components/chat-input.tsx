import React, { useState, useRef, ChangeEvent, KeyboardEvent } from "react";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/design-system/ui/tooltip";
import { Button } from "@/design-system/ui/button";
import { Textarea } from "@/design-system/ui/textarea";
import { MicIcon, PaperclipIcon, SendIcon } from "lucide-react";
import { cn } from "@/lib/utils";
import AttachmentPreview from "@/features/shared/components/chat-input/attachment-preview";
import EmojiPicker from "@/features/shared/components/chat-input/emoji-picker";
import type {
  Attachment,
  ChatInputProps,
} from "@/features/shared/components/chat-input/chat-input-types";

type SpeechRecognitionConstructor = new () => SpeechRecognition;

interface SpeechRecognitionWindow extends Window {
  SpeechRecognition?: SpeechRecognitionConstructor;
  webkitSpeechRecognition?: SpeechRecognitionConstructor;
}

export default function ChatInput({
  onSendMessage,
  disabled = false,
  placeholder = "Type a message...",
  className,
}: ChatInputProps) {
  const [message, setMessage] = useState("");
  const [attachments, setAttachments] = useState<Attachment[]>([]);
  const [isEmojiPickerOpen, setIsEmojiPickerOpen] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleSendMessage = () => {
    if (message.trim() || attachments.length > 0) {
      onSendMessage(message, attachments);
      setMessage("");
      setAttachments([]);
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  const handleFileChange = (e: ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;

    const newAttachments: Attachment[] = [];

    Array.from(files).forEach((file) => {
      const id = `attachment-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`;
      const type = file.type.startsWith("image/")
        ? "image"
        : file.type.startsWith("video/")
          ? "video"
          : "file";

      const attachment: Attachment = {
        id,
        file,
        type,
      };

      if (type === "image" || type === "video") {
        attachment.previewUrl = URL.createObjectURL(file);
      }

      newAttachments.push(attachment);
    });

    setAttachments([...attachments, ...newAttachments]);

    // Reset the file input
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  const handleRemoveAttachment = (id: string) => {
    setAttachments(attachments.filter((attachment) => attachment.id !== id));
  };

  const handleEmojiSelect = (emoji: string) => {
    setMessage((prev) => prev + emoji);
    setIsEmojiPickerOpen(false);
  };

  const handleVoiceInput = () => {
    if (typeof window === "undefined") {
      return;
    }

    const recognitionCtor =
      (window as SpeechRecognitionWindow).SpeechRecognition ??
      (window as SpeechRecognitionWindow).webkitSpeechRecognition;

    if (!recognitionCtor) {
      alert(
        "Speech recognition is not supported in your browser. Try using Chrome.",
      );
      return;
    }

    const recognition = new recognitionCtor();
    recognition.lang = "en-US";
    recognition.continuous = false;
    recognition.interimResults = false;

    recognition.onstart = () => {
      setIsRecording(true);
    };

    recognition.onresult = (event: SpeechRecognitionEvent) => {
      const transcript = event.results[0][0].transcript;
      setMessage((prev) => `${prev} ${transcript}`.trim());
    };

    recognition.onerror = (event: SpeechRecognitionErrorEvent) => {
      console.error("Speech recognition error", event.error);
      setIsRecording(false);
    };

    recognition.onend = () => {
      setIsRecording(false);
    };

    if (!isRecording) {
      recognition.start();
    } else {
      recognition.stop();
    }
  };

  return (
    <div className={cn("flex flex-col gap-2 p-2", className)}>
      <AttachmentPreview
        attachments={attachments}
        onRemoveAttachment={handleRemoveAttachment}
      />

      <div className="flex items-end gap-2">
        <div className="flex-1 relative">
          <Textarea
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={placeholder}
            disabled={disabled}
            className="min-h-[60px] max-h-[200px] resize-none pr-10"
          />

          <div className="absolute bottom-2 right-2">
            <EmojiPicker
              isOpen={isEmojiPickerOpen}
              onOpenChange={setIsEmojiPickerOpen}
              onSelect={handleEmojiSelect}
            />
          </div>
        </div>

        <div className="flex items-center gap-1">
          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon"
                  className={cn(
                    "rounded-full",
                    isRecording &&
                      "bg-red-100 text-red-500 dark:bg-red-900/30 dark:text-red-400",
                  )}
                  onClick={handleVoiceInput}
                  disabled={disabled}
                >
                  <MicIcon className="h-5 w-5" />
                </Button>
              </TooltipTrigger>
              <TooltipContent>
                {isRecording ? "Stop recording" : "Voice input"}
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>

          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon"
                  className="rounded-full"
                  onClick={() => fileInputRef.current?.click()}
                  disabled={disabled}
                >
                  <PaperclipIcon className="h-5 w-5" />
                </Button>
              </TooltipTrigger>
              <TooltipContent>Attach file</TooltipContent>
            </Tooltip>
          </TooltipProvider>

          <input
            type="file"
            ref={fileInputRef}
            onChange={handleFileChange}
            className="hidden"
            multiple
            accept="image/*,video/*,application/*"
            disabled={disabled}
          />

          <Button
            onClick={handleSendMessage}
            disabled={
              disabled || (message.trim() === "" && attachments.length === 0)
            }
            className="rounded-full"
          >
            <SendIcon className="h-5 w-5" />
          </Button>
        </div>
      </div>
    </div>
  );
}
