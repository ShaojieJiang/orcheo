import { Badge } from "@/design-system/ui/badge";
import { Button } from "@/design-system/ui/button";
import { Clock, Maximize2, Minimize2 } from "lucide-react";

import { ExecutionState } from "./time-travel-types";

interface TimeTravelHeaderProps {
  currentState?: ExecutionState;
  isExpanded: boolean;
  onToggleExpand: () => void;
}

export function TimeTravelHeader({
  currentState,
  isExpanded,
  onToggleExpand,
}: TimeTravelHeaderProps) {
  return (
    <div className="flex items-center justify-between p-4 border-b border-border">
      <div className="flex items-center gap-2">
        <Clock className="h-5 w-5" />
        <h3 className="font-medium">Time Travel Debugger</h3>
        {currentState && (
          <Badge variant="outline" className="ml-2">
            {formatTime(currentState.timestamp)}
          </Badge>
        )}
      </div>

      <div className="flex items-center gap-2">
        <Button variant="ghost" size="icon" onClick={onToggleExpand}>
          {isExpanded ? (
            <Minimize2 className="h-4 w-4" />
          ) : (
            <Maximize2 className="h-4 w-4" />
          )}
        </Button>
      </div>
    </div>
  );
}

function formatTime(timestamp: string) {
  return new Date(timestamp).toLocaleTimeString();
}
