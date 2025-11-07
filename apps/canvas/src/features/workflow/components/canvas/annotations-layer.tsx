import React, { useState } from "react";

import { cn } from "@/lib/utils";

import { AnnotationComposer } from "./annotations-layer/annotation-composer";
import { AnnotationList } from "./annotations-layer/annotation-list";
import type { Annotation } from "./annotations-layer/types";

interface AnnotationsLayerProps {
  annotations?: Annotation[];
  onAddAnnotation?: (annotation: Omit<Annotation, "id" | "createdAt">) => void;
  onUpdateAnnotation?: (id: string, content: string) => void;
  onDeleteAnnotation?: (id: string) => void;
  readOnly?: boolean;
  className?: string;
}

export default function AnnotationsLayer({
  annotations = [],
  onAddAnnotation,
  onUpdateAnnotation,
  onDeleteAnnotation,
  readOnly = false,
  className,
}: AnnotationsLayerProps) {
  const [isAddingAnnotation, setIsAddingAnnotation] = useState(false);
  const [newAnnotationPosition, setNewAnnotationPosition] = useState({
    x: 0,
    y: 0,
  });
  const [newAnnotationContent, setNewAnnotationContent] = useState("");

  const handleCanvasClick = (event: React.MouseEvent) => {
    if (!isAddingAnnotation) {
      return;
    }

    const rect = event.currentTarget.getBoundingClientRect();
    const x = event.clientX - rect.left;
    const y = event.clientY - rect.top;
    setNewAnnotationPosition({ x, y });
  };

  const exitAnnotationMode = () => {
    setIsAddingAnnotation(false);
    setNewAnnotationContent("");
  };

  const toggleAddMode = () => {
    setIsAddingAnnotation((prev) => {
      if (prev) {
        setNewAnnotationContent("");
      }
      return !prev;
    });
  };

  const handleAddAnnotation = () => {
    if (!newAnnotationContent.trim() || !onAddAnnotation) {
      return;
    }

    onAddAnnotation({
      content: newAnnotationContent,
      position: newAnnotationPosition,
      author: {
        name: "Current User",
        avatar: "https://avatar.vercel.sh/avery",
      },
    });
    exitAnnotationMode();
  };

  return (
    <div
      className={cn("absolute inset-0 pointer-events-none", className)}
      onClick={isAddingAnnotation ? handleCanvasClick : undefined}
    >
      {!readOnly && (
        <AnnotationComposer
          isAdding={isAddingAnnotation}
          position={newAnnotationPosition}
          content={newAnnotationContent}
          onToggle={toggleAddMode}
          onContentChange={setNewAnnotationContent}
          onSubmit={handleAddAnnotation}
          onCancel={exitAnnotationMode}
        />
      )}

      <AnnotationList
        annotations={annotations}
        readOnly={readOnly}
        onUpdateAnnotation={onUpdateAnnotation}
        onDeleteAnnotation={onDeleteAnnotation}
      />
    </div>
  );
}
