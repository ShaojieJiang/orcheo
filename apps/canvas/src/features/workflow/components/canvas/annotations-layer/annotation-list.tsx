import { AnnotationItem } from "./annotation-item";
import type { Annotation } from "./types";

interface AnnotationListProps {
  annotations: Annotation[];
  readOnly: boolean;
  onUpdateAnnotation?: (id: string, content: string) => void;
  onDeleteAnnotation?: (id: string) => void;
}

export function AnnotationList({
  annotations,
  readOnly,
  onUpdateAnnotation,
  onDeleteAnnotation,
}: AnnotationListProps) {
  return (
    <>
      {annotations.map((annotation) => (
        <AnnotationItem
          key={annotation.id}
          annotation={annotation}
          readOnly={readOnly}
          onUpdate={onUpdateAnnotation}
          onDelete={onDeleteAnnotation}
        />
      ))}
    </>
  );
}
