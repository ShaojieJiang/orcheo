import { useEffect, useState } from "react";

import { Avatar, AvatarFallback, AvatarImage } from "@/design-system/ui/avatar";
import { Button } from "@/design-system/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/design-system/ui/dropdown-menu";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/design-system/ui/popover";
import { Textarea } from "@/design-system/ui/textarea";
import { Edit, MessageSquare, MoreHorizontal, Trash } from "lucide-react";

import type { Annotation } from "./types";

interface AnnotationItemProps {
  annotation: Annotation;
  readOnly: boolean;
  onUpdate?: (id: string, content: string) => void;
  onDelete?: (id: string) => void;
}

export function AnnotationItem({
  annotation,
  readOnly,
  onUpdate,
  onDelete,
}: AnnotationItemProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [content, setContent] = useState(annotation.content);

  useEffect(() => {
    setContent(annotation.content);
  }, [annotation.content]);

  const handleSave = () => {
    if (!content.trim() || !onUpdate) {
      return;
    }

    onUpdate(annotation.id, content);
    setIsEditing(false);
  };

  const handleDelete = () => {
    onDelete?.(annotation.id);
  };

  return (
    <div
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
          {isEditing ? (
            <div className="space-y-2">
              <Textarea
                value={content}
                onChange={(event) => setContent(event.target.value)}
                className="min-h-[100px]"
                autoFocus
              />
              <div className="flex justify-end gap-2">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setIsEditing(false)}
                >
                  Cancel
                </Button>
                <Button size="sm" onClick={handleSave}>
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
                      <Button variant="ghost" size="icon" className="h-8 w-8">
                        <MoreHorizontal className="h-4 w-4" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem onClick={() => setIsEditing(true)}>
                        <Edit className="mr-2 h-4 w-4" />
                        Edit
                      </DropdownMenuItem>
                      <DropdownMenuItem
                        onClick={handleDelete}
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
  );
}
