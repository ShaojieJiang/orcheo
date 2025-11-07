import { Badge } from "@/design-system/ui/badge";
import { ScrollArea } from "@/design-system/ui/scroll-area";
import { cn } from "@/lib/utils";
import { AlertCircle, CheckCircle, Clock, Loader2 } from "lucide-react";

import { ExecutionState } from "./time-travel-types";

interface ExecutionTimelineProps {
  states: ExecutionState[];
  currentIndex: number;
  onSelect: (index: number) => void;
}

export function TimeTravelTimeline({
  states,
  currentIndex,
  onSelect,
}: ExecutionTimelineProps) {
  return (
    <div className="w-1/3 border-r border-border">
      <div className="p-2 bg-muted/30 border-b border-border">
        <h4 className="text-sm font-medium">Execution Timeline</h4>
      </div>
      <ScrollArea className="h-[calc(100%-33px)]">
        <div className="p-2">
          {states.map((state, index) => (
            <button
              type="button"
              key={`${state.nodeId}-${index}`}
              className={cn(
                "flex w-full items-center gap-2 p-2 rounded-md text-left",
                index === currentIndex
                  ? "bg-accent text-accent-foreground"
                  : "hover:bg-muted",
              )}
              onClick={() => onSelect(index)}
            >
              {getStateIcon(state.state)}
              <div className="flex-1">
                <div className="text-sm font-medium">{state.nodeName}</div>
                <div className="text-xs text-muted-foreground">
                  {formatTime(state.timestamp)}
                </div>
              </div>
              <Badge
                variant={
                  state.state === "error"
                    ? "destructive"
                    : state.state === "success"
                      ? "default"
                      : "outline"
                }
                className="capitalize"
              >
                {state.state}
              </Badge>
            </button>
          ))}
        </div>
      </ScrollArea>
    </div>
  );
}

function getStateIcon(state: ExecutionState["state"]) {
  switch (state) {
    case "running":
      return <Loader2 className="h-4 w-4 animate-spin text-blue-500" />;
    case "success":
      return <CheckCircle className="h-4 w-4 text-green-500" />;
    case "error":
      return <AlertCircle className="h-4 w-4 text-red-500" />;
    default:
      return <Clock className="h-4 w-4 text-muted-foreground" />;
  }
}

function formatTime(timestamp: string) {
  return new Date(timestamp).toLocaleTimeString();
}
