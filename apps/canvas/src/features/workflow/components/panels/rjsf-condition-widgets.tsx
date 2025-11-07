/* eslint-disable react-refresh/only-export-components */
/**
 * Condition-specific widgets that provide operator pickers and typed operands.
 */

import React from "react";
import { RegistryWidgetsType, WidgetProps, getUiOptions } from "@rjsf/utils";
import { Input } from "@/design-system/ui/input";
import { Button } from "@/design-system/ui/button";
import { Check } from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
  DropdownMenuTrigger,
} from "@/design-system/ui/dropdown-menu";
import {
  conditionOperatorGroups,
  type ConditionOperatorGroup,
  type ConditionOperatorOption,
} from "@features/workflow/lib/node-schemas";
import {
  hasSchemaFieldData,
  insertSchemaFieldReference,
  readSchemaFieldDragData,
} from "./schema-dnd";

const formatOperandValue = (value: unknown): string => {
  if (value === undefined) {
    return "";
  }
  if (value === null) {
    return "null";
  }
  if (typeof value === "object") {
    try {
      return JSON.stringify(value);
    } catch (error) {
      console.error("Failed to stringify operand", error);
      return "";
    }
  }
  return String(value);
};

const parseOperandValue = (rawValue: string): unknown => {
  const trimmed = rawValue.trim();
  if (trimmed.length === 0) {
    return undefined;
  }
  if (trimmed === "null") {
    return null;
  }
  if (trimmed === "true") {
    return true;
  }
  if (trimmed === "false") {
    return false;
  }
  const numberPattern = /^-?\d+(\.\d+)?$/;
  if (numberPattern.test(trimmed)) {
    return Number(trimmed);
  }
  return rawValue;
};

function ConditionOperandWidget(props: WidgetProps) {
  const {
    id,
    value,
    onChange,
    disabled,
    readonly,
    placeholder,
    onBlur,
    onFocus,
  } = props;
  const displayValue = formatOperandValue(value);

  const handleDragOver = React.useCallback(
    (event: React.DragEvent<HTMLInputElement>) => {
      if (disabled || readonly) {
        return;
      }
      if (hasSchemaFieldData(event.dataTransfer)) {
        event.preventDefault();
        event.dataTransfer.dropEffect = "copy";
      }
    },
    [disabled, readonly],
  );

  const handleDrop = React.useCallback(
    (event: React.DragEvent<HTMLInputElement>) => {
      if (disabled || readonly) {
        return;
      }

      const payload = readSchemaFieldDragData(event.dataTransfer);
      if (!payload?.path) {
        return;
      }

      event.preventDefault();
      event.stopPropagation();

      const target = event.target as HTMLInputElement;
      const { value: nextValue, selectionStart } = insertSchemaFieldReference(
        target,
        payload.path,
      );

      target.value = nextValue;
      target.focus();
      const restoreSelection = () =>
        target.setSelectionRange(selectionStart, selectionStart);
      if (typeof window !== "undefined" && window.requestAnimationFrame) {
        window.requestAnimationFrame(restoreSelection);
      } else {
        restoreSelection();
      }

      const parsedValue = parseOperandValue(nextValue);
      onChange(parsedValue);
    },
    [disabled, onChange, readonly],
  );

  return (
    <Input
      id={id}
      value={displayValue}
      onChange={(event) => onChange(parseOperandValue(event.target.value))}
      onBlur={(event) => onBlur?.(id, parseOperandValue(event.target.value))}
      onFocus={(event) => onFocus?.(id, parseOperandValue(event.target.value))}
      disabled={disabled || readonly}
      placeholder={placeholder}
      onDragOver={handleDragOver}
      onDrop={handleDrop}
    />
  );
}

type OperatorSelection = {
  group: ConditionOperatorGroup;
  option: ConditionOperatorOption;
};

const findOperatorSelection = (value: unknown): OperatorSelection | null => {
  if (typeof value !== "string") {
    return null;
  }
  for (const group of conditionOperatorGroups) {
    const option = group.options.find((candidate) => candidate.value === value);
    if (option) {
      return { group, option };
    }
  }
  return null;
};

function ConditionOperatorWidget(props: WidgetProps) {
  const { id, value, onChange, disabled, readonly, options, uiSchema } = props;
  const uiOptions = getUiOptions(uiSchema);
  const groups =
    (uiOptions.operatorGroups as ConditionOperatorGroup[]) ??
    conditionOperatorGroups;
  const selection = findOperatorSelection(value);
  const buttonLabel = selection
    ? `${selection.group.label} · ${selection.option.label}`
    : "Select operator";
  const allowedValues = new Set(
    ((options.enumOptions as Array<{ value: string }> | undefined) ?? []).map(
      (entry) => String(entry.value),
    ),
  );

  const handleSelect = (nextValue: string) => {
    if (!allowedValues.size || allowedValues.has(nextValue)) {
      onChange(nextValue);
    }
  };

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          id={id}
          variant="outline"
          className="w-full justify-between"
          disabled={disabled || readonly}
        >
          <span className="truncate text-left">{buttonLabel}</span>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent className="w-64">
        {groups.map((group) => (
          <DropdownMenuSub key={group.key}>
            <DropdownMenuSubTrigger>{group.label}</DropdownMenuSubTrigger>
            <DropdownMenuSubContent className="w-64">
              {group.options.map((option) => (
                <DropdownMenuItem
                  key={option.value}
                  onSelect={() => handleSelect(option.value)}
                  className="justify-between"
                >
                  <div className="flex flex-col text-left">
                    <span>{option.label}</span>
                    {option.description && (
                      <span className="text-xs text-muted-foreground">
                        {option.description}
                      </span>
                    )}
                  </div>
                  {selection?.option.value === option.value && (
                    <Check className="h-4 w-4" />
                  )}
                </DropdownMenuItem>
              ))}
            </DropdownMenuSubContent>
          </DropdownMenuSub>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

type ConditionWidgetMap = Pick<
  RegistryWidgetsType,
  "conditionOperand" | "conditionOperator"
>;

export const conditionWidgets: ConditionWidgetMap = {
  conditionOperand: ConditionOperandWidget,
  conditionOperator: ConditionOperatorWidget,
};

export { ConditionOperandWidget, ConditionOperatorWidget };
