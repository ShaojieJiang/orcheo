import { Sparkles } from "lucide-react";
import { useVibe } from "@features/vibe/context/vibe-context";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/design-system/ui/tooltip";

export function VibeSidebarCollapsed() {
  const { toggleOpen, readyProviders } = useVibe();
  const hasAgents = readyProviders.length > 0;

  return (
    <div className="flex h-full flex-col items-center justify-start pt-3">
      <TooltipProvider>
        <Tooltip>
          <TooltipTrigger asChild>
            <button
              onClick={toggleOpen}
              className="flex h-9 w-9 items-center justify-center rounded-md transition-colors hover:bg-accent"
              title="Open Orcheo Vibe"
            >
              <Sparkles
                className={`h-5 w-5 ${hasAgents ? "text-primary" : "text-muted-foreground"}`}
              />
              <span className="sr-only">Open Orcheo Vibe</span>
            </button>
          </TooltipTrigger>
          <TooltipContent side="right">
            <p>Orcheo Vibe</p>
          </TooltipContent>
        </Tooltip>
      </TooltipProvider>
    </div>
  );
}
