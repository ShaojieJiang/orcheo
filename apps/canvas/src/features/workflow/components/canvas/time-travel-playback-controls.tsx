import { Button } from "@/design-system/ui/button";
import { Slider } from "@/design-system/ui/slider";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/design-system/ui/tooltip";
import {
  FastForward,
  Pause,
  Play,
  Rewind,
  SkipBack,
  SkipForward,
} from "lucide-react";

interface TimeTravelPlaybackControlsProps {
  currentStateIndex: number;
  totalStates: number;
  playbackSpeed: number;
  isPlaying: boolean;
  onPlay: () => void;
  onPause: () => void;
  onRestart: () => void;
  onSkipForward: () => void;
  onSkipBackward: () => void;
  onJumpToEnd: () => void;
  onSliderChange: (index: number) => void;
  onSpeedChange: (speed: number) => void;
}

export function TimeTravelPlaybackControls({
  currentStateIndex,
  totalStates,
  playbackSpeed,
  isPlaying,
  onPlay,
  onPause,
  onRestart,
  onSkipForward,
  onSkipBackward,
  onJumpToEnd,
  onSliderChange,
  onSpeedChange,
}: TimeTravelPlaybackControlsProps) {
  const atBeginning = currentStateIndex === 0;
  const atEnd = currentStateIndex >= totalStates - 1;

  return (
    <div className="p-4 border-b border-border">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="outline"
                  size="icon"
                  onClick={onRestart}
                  disabled={atBeginning}
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
                  onClick={onSkipBackward}
                  disabled={atBeginning}
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
              onClick={onPause}
            >
              <Pause className="h-4 w-4" />
            </Button>
          ) : (
            <Button
              variant="outline"
              size="icon"
              className="h-8 w-8"
              onClick={onPlay}
              disabled={atEnd}
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
                  onClick={onSkipForward}
                  disabled={atEnd}
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
                  onClick={onJumpToEnd}
                  disabled={atEnd}
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
          {([0.5, 1, 2, 4] as const).map((speed) => (
            <Button
              key={speed}
              variant={playbackSpeed === speed ? "secondary" : "ghost"}
              size="sm"
              className="h-7 px-2"
              onClick={() => onSpeedChange(speed)}
            >
              {speed}x
            </Button>
          ))}
        </div>
      </div>

      <div className="px-2">
        <Slider
          value={[currentStateIndex]}
          min={0}
          max={Math.max(totalStates - 1, 0)}
          step={1}
          onValueChange={(value) => onSliderChange(value[0] ?? 0)}
        />
        <div className="flex justify-between mt-1 text-xs text-muted-foreground">
          <span>Start</span>
          <span>
            Step {Math.min(currentStateIndex + 1, totalStates)} of {totalStates}
          </span>
          <span>End</span>
        </div>
      </div>
    </div>
  );
}
