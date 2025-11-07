export interface Attachment {
  id: string;
  file: File;
  type: "image" | "video" | "file";
  previewUrl?: string;
}

export interface ChatInputProps {
  onSendMessage: (message: string, attachments: Attachment[]) => void;
  disabled?: boolean;
  placeholder?: string;
  className?: string;
}
