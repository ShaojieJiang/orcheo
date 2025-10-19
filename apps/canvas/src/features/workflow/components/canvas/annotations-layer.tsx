import React, { useState } from "react";
import { Button } from "@/design-system/ui/button";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/design-system/ui/popover";
import { Textarea } from "@/design-system/ui/textarea";
import { cn } from "@/lib/utils";
import {
  MessageSquare,
  X,
  Edit,
  Trash,
  Plus,
  User,
  MoreHorizontal,
} from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/design-system/ui/dropdown-menu";
import { Avatar, AvatarFallback, AvatarImage } from "@/design-system/ui/avatar";

interface Annotation {
  id: string;
  content: string;
  position: { x: number; y: number };
  author: {
    name: string;
    avatar: string;
  };
  createdAt: string;
}

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
  const [editingAnnotationId, setEditingAnnotationId] = useState<string | null>(
    null,
  );
  const [editingContent, setEditingContent] = useState("");

  const handleCanvasClick = (e: React.MouseEvent) => {
    if (isAddingAnnotation) {
      // Get position relative to the canvas
      const rect = e.currentTarget.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;

      setNewAnnotationPosition({ x, y });
    }
  };

  const handleAddAnnotation = () => {
    if (newAnnotationContent.trim() && onAddAnnotation) {
      onAddAnnotation({
        content: newAnnotationContent,
        position: newAnnotationPosition,
        author: {
          name: "Current User",
          avatar: "https://avatar.vercel.sh/avery",
        },
      });
      setNewAnnotationContent("");
      setIsAddingAnnotation(false);
    }
  };

  const handleUpdateAnnotation = (id: string) => {
    if (editingContent.trim() && onUpdateAnnotation) {
      onUpdateAnnotation(id, editingContent);
      setEditingAnnotationId(null);
      setEditingContent("");
    }
  };

  const startEditing = (annotation: Annotation) => {
    setEditingAnnotationId(annotation.id);
    setEditingContent(annotation.content);
  };

  const cancelEditing = () => {
    setEditingAnnotationId(null);
    setEditingContent("");
  };

  return (
    <div
      className={cn("absolute inset-0 pointer-events-none", className)}
      onClick={isAddingAnnotation ? handleCanvasClick : undefined}
    >
      {/* Annotation toggle button */}
      {!readOnly && (
        <div className="absolute top-4 right-4 pointer-events-auto z-10">
          <Button
            variant={isAddingAnnotation ? "default" : "outline"}
            size="sm"
            onClick={() => setIsAddingAnnotation(!isAddingAnnotation)}
            className="gap-2"
          >
            {isAddingAnnotation ? (
              <>
                <X className="h-4 w-4" />
                Cancel
              </>
            ) : (
              <>
                <Plus className="h-4 w-4" />
                Add Comment
              </>
            )}
          </Button>
        </div>
      )}

      {/* Instructions when adding annotation */}
      {isAddingAnnotation && (
        <div className="absolute top-16 right-4 bg-background border border-border rounded-md p-2 shadow-md pointer-events-auto">
          <p className="text-xs text-muted-foreground">
            Click anywhere on the canvas to add a comment
          </p>
        </div>
      )}

      {/* New annotation popover */}
      {isAddingAnnotation && (
        <Popover open={true}>
          <PopoverTrigger asChild>
            <div
              className="absolute w-6 h-6 bg-primary rounded-full flex items-center justify-center cursor-pointer pointer-events-auto"
              style={{
                left: `${newAnnotationPosition.x}px`,
                top: `${newAnnotationPosition.y}px`,
                transform: "translate(-50%, -50%)",
              }}
            >
              <Plus className="h-4 w-4 text-primary-foreground" />
            </div>
          </PopoverTrigger>
          <PopoverContent
            className="w-80 pointer-events-auto"
            side="right"
            align="start"
          >
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <Avatar className="h-6 w-6">
                  <AvatarImage src="https://avatar.vercel.sh/avery" />

                  <AvatarFallback>CU</AvatarFallback>
                </Avatar>
                <span className="text-sm font-medium">Current User</span>
              </div>
              <Textarea
                placeholder="Add your comment..."
                className="min-h-[100px]"
                value={newAnnotationContent}
                onChange={(e) => setNewAnnotationContent(e.target.value)}
                autoFocus
              />

              <div className="flex justify-end gap-2">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setIsAddingAnnotation(false)}
                >
                  Cancel
                </Button>
                <Button size="sm" onClick={handleAddAnnotation}>
                  Add Comment
                </Button>
              </div>
            </div>
          </PopoverContent>
        </Popover>
      )}

      {/* Existing annotations */}
      {annotations.map((annotation) => (
        <div
          key={annotation.id}
          className="absolute pointer-events-auto"
          style={{
            left: `${annotation.position.x}px`,
            top: `${annotation.position.y}px`,
          }}
        >
          <Popover>
            <PopoverTrigger asChild>
              <Button
                variant="outline"
                size="icon"
                className="h-6 w-6 rounded-full bg-background border-primary"
              >
                <MessageSquare className="h-3 w-3 text-primary" />
              </Button>
            </PopoverTrigger>
            <PopoverContent className="w-80" side="right" align="start">
              {editingAnnotationId === annotation.id ? (
                <div className="space-y-2">
                  <Textarea
                    value={editingContent}
                    onChange={(e) => setEditingContent(e.target.value)}
                    className="min-h-[100px]"
                    autoFocus
                  />

                  <div className="flex justify-end gap-2">
                    <Button variant="ghost" size="sm" onClick={cancelEditing}>
                      Cancel
                    </Button>
                    <Button
                      size="sm"
                      onClick={() => handleUpdateAnnotation(annotation.id)}
                    >
                      Save
                    </Button>
                  </div>
                </div>
              ) : (
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <Avatar className="h-6 w-6">
                        <AvatarImage src={annotation.author.avatar} />

                        <AvatarFallback>
                          {annotation.author.name.charAt(0)}
                        </AvatarFallback>
                      </Avatar>
                      <span className="text-sm font-medium">
                        {annotation.author.name}
                      </span>
                    </div>
                    {!readOnly && (
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-8 w-8"
                          >
                            <MoreHorizontal className="h-4 w-4" />
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                          <DropdownMenuItem
                            onClick={() => startEditing(annotation)}
                          >
                            <Edit className="mr-2 h-4 w-4" />
                            Edit
                          </DropdownMenuItem>
                          <DropdownMenuItem
                            onClick={() => onDeleteAnnotation?.(annotation.id)}
                            className="text-destructive focus:text-destructive"
                          >
                            <Trash className="mr-2 h-4 w-4" />
                            Delete
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    )}
                  </div>
                  <p className="text-sm">{annotation.content}</p>
                  <p className="text-xs text-muted-foreground">
                    {new Date(annotation.createdAt).toLocaleString()}
                  </p>
                </div>
              )}
            </PopoverContent>
          </Popover>
        </div>
      ))}
    </div>
  );
}
