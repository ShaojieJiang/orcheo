import React, { useState, useRef, ChangeEvent, KeyboardEvent } from "react";
import { Button } from "@/design-system/ui/button";
import { Textarea } from "@/design-system/ui/textarea";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/design-system/ui/tooltip";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/design-system/ui/popover";
import {
  FileIcon,
  ImageIcon,
  LinkIcon,
  MicIcon,
  PaperclipIcon,
  SendIcon,
  SmileIcon,
  VideoIcon,
  XIcon,
} from "lucide-react";
import { cn } from "@/lib/utils";

// Simple emoji array to replace emoji-mart
const COMMON_EMOJIS = [
  "😀",
  "😃",
  "😄",
  "😁",
  "😆",
  "😅",
  "😂",
  "🤣",
  "😊",
  "😇",
  "🙂",
  "🙃",
  "😉",
  "😌",
  "😍",
  "🥰",
  "😘",
  "😗",
  "😙",
  "😚",
  "😋",
  "😛",
  "😝",
  "😜",
  "🤪",
  "🤨",
  "🧐",
  "🤓",
  "😎",
  "🤩",
  "🥳",
  "😏",
  "😒",
  "😞",
  "😔",
  "😟",
  "😕",
  "🙁",
  "☹️",
  "😣",
  "👍",
  "👎",
  "👌",
  "✌️",
  "🤞",
  "🤟",
  "🤘",
  "👏",
  "🙌",
  "👐",
  "❤️",
  "🧡",
  "💛",
  "💚",
  "💙",
  "💜",
  "🖤",
  "❣️",
  "💕",
  "💞",
];

export interface Attachment {
  id: string;
  file: File;
  type: "image" | "video" | "file";
  previewUrl?: string;
}

interface ChatInputProps {
  onSendMessage: (message: string, attachments: Attachment[]) => void;
  disabled?: boolean;
  placeholder?: string;
  className?: string;
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
    if (!("webkitSpeechRecognition" in window)) {
      alert(
        "Speech recognition is not supported in your browser. Try using Chrome.",
      );
      return;
    }

    setIsRecording(!isRecording);

    // @ts-ignore - SpeechRecognition is not in the TypeScript types
    const SpeechRecognition =
      window.SpeechRecognition || window.webkitSpeechRecognition;
    const recognition = new SpeechRecognition();

    recognition.lang = "en-US";
    recognition.continuous = false;
    recognition.interimResults = false;

    recognition.onstart = () => {
      setIsRecording(true);
    };

    recognition.onresult = (event: any) => {
      const transcript = event.results[0][0].transcript;
      setMessage((prev) => prev + " " + transcript);
    };

    recognition.onerror = (event: any) => {
      console.error("Speech recognition error", event.error);
      setIsRecording(false);
    };

    recognition.onend = () => {
      setIsRecording(false);
    };

    if (!isRecording) {
      recognition.start();
    }
  };

  return (
    <div className={cn("flex flex-col gap-2 p-2", className)}>
      {attachments.length > 0 && (
        <div className="flex flex-wrap gap-2 p-2 bg-muted/50 rounded-md">
          {attachments.map((attachment) => (
            <div
              key={attachment.id}
              className="relative group rounded-md overflow-hidden border border-border"
            >
              {attachment.type === "image" && attachment.previewUrl ? (
                <div className="w-16 h-16 relative">
                  <img
                    src={attachment.previewUrl}
                    alt={attachment.file.name}
                    className="w-full h-full object-cover"
                  />

                  <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-6 w-6 text-white"
                      onClick={() => handleRemoveAttachment(attachment.id)}
                    >
                      <XIcon className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              ) : attachment.type === "video" && attachment.previewUrl ? (
                <div className="w-16 h-16 relative bg-black flex items-center justify-center">
                  <VideoIcon className="h-6 w-6 text-white" />

                  <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-6 w-6 text-white"
                      onClick={() => handleRemoveAttachment(attachment.id)}
                    >
                      <XIcon className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              ) : (
                <div className="w-16 h-16 bg-muted flex flex-col items-center justify-center p-1 relative">
                  <FileIcon className="h-6 w-6" />

                  <div className="text-xs truncate w-full text-center">
                    {attachment.file.name.split(".").pop()}
                  </div>
                  <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-6 w-6 text-white"
                      onClick={() => handleRemoveAttachment(attachment.id)}
                    >
                      <XIcon className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}

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
            <Popover
              open={isEmojiPickerOpen}
              onOpenChange={setIsEmojiPickerOpen}
            >
              <PopoverTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-8 w-8 rounded-full"
                >
                  <SmileIcon className="h-5 w-5 text-muted-foreground" />
                </Button>
              </PopoverTrigger>
              <PopoverContent className="w-auto p-2" align="end">
                <div className="grid grid-cols-10 gap-1">
                  {COMMON_EMOJIS.map((emoji, index) => (
                    <button
                      key={index}
                      className="w-8 h-8 flex items-center justify-center hover:bg-muted rounded-md text-lg"
                      onClick={() => handleEmojiSelect(emoji)}
                    >
                      {emoji}
                    </button>
                  ))}
                </div>
              </PopoverContent>
            </Popover>
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
