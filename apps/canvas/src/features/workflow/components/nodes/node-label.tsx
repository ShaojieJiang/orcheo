import React, { useState, useRef, useEffect } from "react";
import { Pencil, Check, X } from "lucide-react";
import { Input } from "@/design-system/ui/input";
import { cn } from "@/lib/utils";

export interface NodeLabelProps {
  id: string;
  label: string;
  onLabelChange?: (id: string, newLabel: string) => void;
  editable?: boolean;
  className?: string;
}

export default function NodeLabel({
  id,
  label,
  onLabelChange,
  editable = true,
  className,
}: NodeLabelProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [editedLabel, setEditedLabel] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (isEditing && inputRef.current) {
      inputRef.current.focus();
    }
  }, [isEditing]);

  const handleEditStart = (e: React.MouseEvent) => {
    if (!editable) return;
    e.stopPropagation();
    setIsEditing(true);
    setEditedLabel(label);
  };

  const handleEditCancel = () => {
    setIsEditing(false);
  };

  const handleEditSave = () => {
    if (onLabelChange && editedLabel.trim() !== "") {
      onLabelChange(id, editedLabel);
    }
    setIsEditing(false);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") {
      handleEditSave();
    } else if (e.key === "Escape") {
      handleEditCancel();
    }
  };

  return (
    <div className={cn("mb-2 w-full text-center", className)}>
      {isEditing ? (
        <div className="flex items-center justify-center">
          <Input
            ref={inputRef}
            value={editedLabel}
            onChange={(e) => setEditedLabel(e.target.value)}
            onKeyDown={handleKeyDown}
            className="h-6 py-0 px-1 text-xs w-[100px] text-center"
            autoFocus
          />

          <div className="absolute right-[-40px] flex space-x-1">
            <button
              onClick={handleEditSave}
              className="p-1 rounded-full bg-green-100 hover:bg-green-200 dark:bg-green-900/30 dark:hover:bg-green-800/50"
            >
              <Check className="h-3 w-3 text-green-600 dark:text-green-400" />
            </button>
            <button
              onClick={handleEditCancel}
              className="p-1 rounded-full bg-red-100 hover:bg-red-200 dark:bg-red-900/30 dark:hover:bg-red-800/50"
            >
              <X className="h-3 w-3 text-red-600 dark:text-red-400" />
            </button>
          </div>
        </div>
      ) : (
        <div
          className="flex items-center justify-center text-xs"
          onDoubleClick={handleEditStart}
        >
          <span className="whitespace-nowrap overflow-hidden text-ellipsis px-1">
            {label}
          </span>
          {editable && (
            <button
              onClick={handleEditStart}
              className="ml-1 opacity-0 group-hover:opacity-100 hover:text-primary transition-opacity"
            >
              <Pencil className="h-3 w-3" />
            </button>
          )}
        </div>
      )}
    </div>
  );
}
