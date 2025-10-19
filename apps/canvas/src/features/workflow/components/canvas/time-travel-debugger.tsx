import React, { useState, useEffect, useRef } from "react";
import { Button } from "@/design-system/ui/button";
import { Slider } from "@/design-system/ui/slider";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/design-system/ui/tooltip";
import { Badge } from "@/design-system/ui/badge";
import { ScrollArea } from "@/design-system/ui/scroll-area";
import {
  Play,
  Pause,
  SkipBack,
  SkipForward,
  FastForward,
  Rewind,
  Clock,
  CheckCircle,
  AlertCircle,
  Loader2,
  Maximize2,
  Minimize2,
} from "lucide-react";
import { cn } from "@/lib/utils";

interface ExecutionState {
  timestamp: string;
  nodeId: string;
  nodeName: string;
  state: "running" | "success" | "error" | "idle";
  inputData?: Record<string, unknown>;
  outputData?: Record<string, unknown>;
  error?: string;
}

interface TimeTravelDebuggerProps {
  states: ExecutionState[];
  onStateChange?: (state: ExecutionState) => void;
  onReplayComplete?: () => void;
  className?: string;
}

export default function TimeTravelDebugger({
  states = [],
  onStateChange,
  onReplayComplete,
  className,
}: TimeTravelDebuggerProps) {
  const [currentStateIndex, setCurrentStateIndex] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [playbackSpeed, setPlaybackSpeed] = useState(1);
  const [isExpanded, setIsExpanded] = useState(false);
  const playbackRef = useRef<NodeJS.Timeout | null>(null);

  const currentState = states[currentStateIndex];

  // Handle playback
  useEffect(() => {
    if (isPlaying && currentStateIndex < states.length - 1) {
      playbackRef.current = setTimeout(() => {
        const nextIndex = currentStateIndex + 1;
        setCurrentStateIndex(nextIndex);

        if (nextIndex >= states.length - 1) {
          setIsPlaying(false);
          onReplayComplete?.();
        }
      }, 1000 / playbackSpeed);
    } else if (currentStateIndex >= states.length - 1 && isPlaying) {
      setIsPlaying(false);
      onReplayComplete?.();
    }

    return () => {
      if (playbackRef.current) {
        clearTimeout(playbackRef.current);
      }
    };
  }, [
    isPlaying,
    currentStateIndex,
    states.length,
    playbackSpeed,
    onReplayComplete,
  ]);

  // Notify parent component about state changes
  useEffect(() => {
    if (currentState) {
      onStateChange?.(currentState);
    }
  }, [currentState, onStateChange]);

  const handlePlay = () => {
    setIsPlaying(true);
  };

  const handlePause = () => {
    setIsPlaying(false);
  };

  const handleRestart = () => {
    setIsPlaying(false);
    setCurrentStateIndex(0);
  };

  const handleSkipForward = () => {
    setIsPlaying(false);
    if (currentStateIndex < states.length - 1) {
      setCurrentStateIndex(currentStateIndex + 1);
    }
  };

  const handleSkipBackward = () => {
    setIsPlaying(false);
    if (currentStateIndex > 0) {
      setCurrentStateIndex(currentStateIndex - 1);
    }
  };

  const handleSliderChange = (value: number[]) => {
    setIsPlaying(false);
    setCurrentStateIndex(value[0]);
  };

  const getStateIcon = (state: string) => {
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
  };

  const formatTime = (timestamp: string) => {
    return new Date(timestamp).toLocaleTimeString();
  };

  return (
    <div
      className={cn(
        "border border-border rounded-lg bg-background shadow-md",
        isExpanded ? "fixed inset-4 z-50 flex flex-col" : "w-full",
        className,
      )}
    >
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
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setIsExpanded(!isExpanded)}
          >
            {isExpanded ? (
              <Minimize2 className="h-4 w-4" />
            ) : (
              <Maximize2 className="h-4 w-4" />
            )}
          </Button>
        </div>
      </div>

      <div className="flex-1 overflow-hidden flex flex-col">
        {/* Playback controls */}
        <div className="p-4 border-b border-border">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <TooltipProvider>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button
                      variant="outline"
                      size="icon"
                      onClick={handleRestart}
                      disabled={currentStateIndex === 0}
                    >
                      <SkipBack className="h-4 w-4" />
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent>Restart</TooltipContent>
                </Tooltip>
              </TooltipProvider>

              <TooltipProvider>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button
                      variant="outline"
                      size="icon"
                      onClick={handleSkipBackward}
                      disabled={currentStateIndex === 0}
                    >
                      <Rewind className="h-4 w-4" />
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent>Previous Step</TooltipContent>
                </Tooltip>
              </TooltipProvider>

              {isPlaying ? (
                <Button
                  variant="outline"
                  size="icon"
                  className="h-8 w-8"
                  onClick={handlePause}
                >
                  <Pause className="h-4 w-4" />
                </Button>
              ) : (
                <Button
                  variant="outline"
                  size="icon"
                  className="h-8 w-8"
                  onClick={handlePlay}
                  disabled={currentStateIndex >= states.length - 1}
                >
                  <Play className="h-4 w-4" />
                </Button>
              )}

              <TooltipProvider>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button
                      variant="outline"
                      size="icon"
                      onClick={handleSkipForward}
                      disabled={currentStateIndex >= states.length - 1}
                    >
                      <FastForward className="h-4 w-4" />
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent>Next Step</TooltipContent>
                </Tooltip>
              </TooltipProvider>

              <TooltipProvider>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button
                      variant="outline"
                      size="icon"
                      onClick={() => setCurrentStateIndex(states.length - 1)}
                      disabled={currentStateIndex >= states.length - 1}
                    >
                      <SkipForward className="h-4 w-4" />
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent>Jump to End</TooltipContent>
                </Tooltip>
              </TooltipProvider>
            </div>

            <div className="flex items-center gap-2">
              <span className="text-sm text-muted-foreground">Speed:</span>
              <Button
                variant={playbackSpeed === 0.5 ? "secondary" : "ghost"}
                size="sm"
                className="h-7 px-2"
                onClick={() => setPlaybackSpeed(0.5)}
              >
                0.5x
              </Button>
              <Button
                variant={playbackSpeed === 1 ? "secondary" : "ghost"}
                size="sm"
                className="h-7 px-2"
                onClick={() => setPlaybackSpeed(1)}
              >
                1x
              </Button>
              <Button
                variant={playbackSpeed === 2 ? "secondary" : "ghost"}
                size="sm"
                className="h-7 px-2"
                onClick={() => setPlaybackSpeed(2)}
              >
                2x
              </Button>
              <Button
                variant={playbackSpeed === 4 ? "secondary" : "ghost"}
                size="sm"
                className="h-7 px-2"
                onClick={() => setPlaybackSpeed(4)}
              >
                4x
              </Button>
            </div>
          </div>

          <div className="px-2">
            <Slider
              value={[currentStateIndex]}
              min={0}
              max={states.length - 1}
              step={1}
              onValueChange={handleSliderChange}
            />

            <div className="flex justify-between mt-1 text-xs text-muted-foreground">
              <span>Start</span>
              <span>
                Step {currentStateIndex + 1} of {states.length}
              </span>
              <span>End</span>
            </div>
          </div>
        </div>

        {/* State timeline */}
        <div className="flex flex-1 overflow-hidden">
          <div className="w-1/3 border-r border-border">
            <div className="p-2 bg-muted/30 border-b border-border">
              <h4 className="text-sm font-medium">Execution Timeline</h4>
            </div>
            <ScrollArea className="h-[calc(100%-33px)]">
              <div className="p-2">
                {states.map((state, index) => (
                  <div
                    key={index}
                    className={cn(
                      "flex items-center gap-2 p-2 rounded-md cursor-pointer",
                      index === currentStateIndex
                        ? "bg-accent text-accent-foreground"
                        : "hover:bg-muted",
                    )}
                    onClick={() => {
                      setIsPlaying(false);
                      setCurrentStateIndex(index);
                    }}
                  >
                    {getStateIcon(state.state)}
                    <div className="flex-1">
                      <div className="text-sm font-medium">
                        {state.nodeName}
                      </div>
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
                  </div>
                ))}
              </div>
            </ScrollArea>
          </div>

          {/* State details */}
          <div className="flex-1 overflow-hidden flex flex-col">
            {currentState ? (
              <>
                <div className="p-2 bg-muted/30 border-b border-border">
                  <h4 className="text-sm font-medium">
                    Node: {currentState.nodeName}
                  </h4>
                </div>
                <div className="flex-1 overflow-auto p-4">
                  <div className="space-y-4">
                    <div>
                      <h5 className="text-sm font-medium mb-2">Input Data</h5>
                      <div className="bg-muted p-3 rounded-md overflow-auto max-h-[200px]">
                        <pre className="text-xs">
                          {currentState.inputData
                            ? JSON.stringify(currentState.inputData, null, 2)
                            : "No input data"}
                        </pre>
                      </div>
                    </div>

                    {currentState.state !== "running" && (
                      <div>
                        <h5 className="text-sm font-medium mb-2">
                          Output Data
                        </h5>
                        <div className="bg-muted p-3 rounded-md overflow-auto max-h-[200px]">
                          <pre className="text-xs">
                            {currentState.outputData
                              ? JSON.stringify(currentState.outputData, null, 2)
                              : currentState.error
                                ? "Error: " + currentState.error
                                : "No output data"}
                          </pre>
                        </div>
                      </div>
                    )}

                    {currentState.error && (
                      <div>
                        <h5 className="text-sm font-medium mb-2 text-red-500">
                          Error
                        </h5>
                        <div className="bg-red-50 dark:bg-red-900/20 p-3 rounded-md overflow-auto max-h-[200px] border border-red-200 dark:border-red-800">
                          <pre className="text-xs text-red-700 dark:text-red-300">
                            {currentState.error}
                          </pre>
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              </>
            ) : (
              <div className="flex-1 flex items-center justify-center">
                <p className="text-muted-foreground">
                  Select a state to view details
                </p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
