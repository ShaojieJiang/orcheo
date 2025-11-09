import { ChatKit, useChatKit } from "@openai/chatkit-react";
import type { UseChatKitOptions } from "@openai/chatkit-react";
import { cn } from "@/lib/utils";

interface ChatKitSurfaceProps {
  options: UseChatKitOptions;
  className?: string;
}

export function ChatKitSurface({ options, className }: ChatKitSurfaceProps) {
  const { control } = useChatKit(options);

  return (
    <div className={cn("flex h-full w-full flex-col", className)}>
      <ChatKit control={control} className="flex h-full w-full flex-col" />
    </div>
  );
}
