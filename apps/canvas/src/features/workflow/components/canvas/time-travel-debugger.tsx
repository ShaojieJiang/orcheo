import { useEffect, useRef, useState } from "react";

import { cn } from "@/lib/utils";

import { TimeTravelHeader } from "./time-travel-header";
import { TimeTravelPlaybackControls } from "./time-travel-playback-controls";
import { TimeTravelStateDetails } from "./time-travel-state-details";
import { TimeTravelTimeline } from "./time-travel-timeline";
import { TimeTravelDebuggerProps } from "./time-travel-types";

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

  const totalStates = states.length;
  const currentState = totalStates > 0 ? states[currentStateIndex] : undefined;

  useEffect(() => {
    if (!isPlaying || totalStates === 0) {
      return;
    }

    if (currentStateIndex < totalStates - 1) {
      playbackRef.current = setTimeout(() => {
        setCurrentStateIndex((index) => index + 1);
      }, 1000 / playbackSpeed);
      return;
    }

    setIsPlaying(false);
    onReplayComplete?.();
  }, [
    isPlaying,
    currentStateIndex,
    totalStates,
    playbackSpeed,
    onReplayComplete,
  ]);

  useEffect(() => {
    return () => {
      if (playbackRef.current) {
        clearTimeout(playbackRef.current);
      }
    };
  }, []);

  useEffect(() => {
    if (currentState) {
      onStateChange?.(currentState);
    }
  }, [currentState, onStateChange]);

  useEffect(() => {
    if (totalStates === 0) {
      setCurrentStateIndex(0);
      setIsPlaying(false);
      return;
    }

    setCurrentStateIndex((index) => Math.min(index, totalStates - 1));
  }, [totalStates]);

  const stopPlayback = () => {
    setIsPlaying(false);
  };

  const goToIndex = (index: number) => {
    stopPlayback();

    if (totalStates === 0) {
      setCurrentStateIndex(0);
      return;
    }

    const clampedIndex = Math.max(0, Math.min(index, totalStates - 1));
    setCurrentStateIndex(clampedIndex);
  };

  const handlePlay = () => setIsPlaying(true);
  const handlePause = () => stopPlayback();
  const handleRestart = () => goToIndex(0);

  const handleSkipForward = () => {
    if (currentStateIndex < totalStates - 1) {
      goToIndex(currentStateIndex + 1);
    }
  };

  const handleSkipBackward = () => {
    if (currentStateIndex > 0) {
      goToIndex(currentStateIndex - 1);
    }
  };

  const handleJumpToEnd = () => {
    if (totalStates > 0) {
      goToIndex(totalStates - 1);
    }
  };

  const handleSliderChange = (value: number) => {
    goToIndex(value);
  };

  const handleTimelineSelect = (index: number) => {
    goToIndex(index);
  };

  const handleSpeedChange = (speed: number) => {
    setPlaybackSpeed(speed);
  };

  return (
    <div
      className={cn(
        "border border-border rounded-lg bg-background shadow-md",
        isExpanded ? "fixed inset-4 z-50 flex flex-col" : "w-full",
        className,
      )}
    >
      <TimeTravelHeader
        currentState={currentState}
        isExpanded={isExpanded}
        onToggleExpand={() => setIsExpanded((value) => !value)}
      />

      <div className="flex-1 overflow-hidden flex flex-col">
        <TimeTravelPlaybackControls
          currentStateIndex={currentStateIndex}
          totalStates={totalStates}
          playbackSpeed={playbackSpeed}
          isPlaying={isPlaying}
          onPlay={handlePlay}
          onPause={handlePause}
          onRestart={handleRestart}
          onSkipForward={handleSkipForward}
          onSkipBackward={handleSkipBackward}
          onJumpToEnd={handleJumpToEnd}
          onSliderChange={handleSliderChange}
          onSpeedChange={handleSpeedChange}
        />

        <div className="flex flex-1 overflow-hidden">
          <TimeTravelTimeline
            states={states}
            currentIndex={currentStateIndex}
            onSelect={handleTimelineSelect}
          />

          <TimeTravelStateDetails state={currentState} />
        </div>
      </div>
    </div>
  );
}
