/* eslint-disable react-refresh/only-export-components */
/**
 * Custom RJSF theme using shadcn/ui components
 * This ensures the JSON Schema forms match the existing design system
 */

import React from "react";
import {
  RegistryWidgetsType,
  WidgetProps,
  FieldTemplateProps,
  ObjectFieldTemplateProps,
  ArrayFieldTemplateProps,
  getUiOptions,
} from "@rjsf/utils";
import validator from "@rjsf/validator-ajv8";
import { Input } from "@/design-system/ui/input";
import { Textarea } from "@/design-system/ui/textarea";
import { Label } from "@/design-system/ui/label";
import { Switch } from "@/design-system/ui/switch";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/design-system/ui/select";
import { Button } from "@/design-system/ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/design-system/ui/tooltip";
import { Plus, X, HelpCircle, Check } from "lucide-react";
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

/**
 * Custom Text Input Widget
 */
function TextWidget(props: WidgetProps) {
  const { id, value, onChange, required, disabled, readonly, placeholder } =
    props;

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

      onChange(nextValue);
    },
    [disabled, onChange, readonly],
  );

  return (
    <Input
      id={id}
      type="text"
      value={value || ""}
      onChange={(e) => onChange(e.target.value)}
      required={required}
      disabled={disabled}
      readOnly={readonly}
      placeholder={placeholder}
      onDragOver={handleDragOver}
      onDrop={handleDrop}
    />
  );
}

/**
 * Custom Textarea Widget
 */
function TextareaWidget(props: WidgetProps) {
  const { id, value, onChange, required, disabled, readonly, placeholder } =
    props;
  const uiOptions = getUiOptions(props.uiSchema || {});
  const rows = (uiOptions.rows as number) || 3;

  const handleDragOver = React.useCallback(
    (event: React.DragEvent<HTMLTextAreaElement>) => {
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
    (event: React.DragEvent<HTMLTextAreaElement>) => {
      if (disabled || readonly) {
        return;
      }

      const payload = readSchemaFieldDragData(event.dataTransfer);
      if (!payload?.path) {
        return;
      }

      event.preventDefault();
      event.stopPropagation();

      const target = event.target as HTMLTextAreaElement;
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

      onChange(nextValue);
    },
    [disabled, onChange, readonly],
  );

  return (
    <Textarea
      id={id}
      value={value || ""}
      onChange={(e) => onChange(e.target.value)}
      required={required}
      disabled={disabled}
      readOnly={readonly}
      placeholder={placeholder}
      rows={rows}
      onDragOver={handleDragOver}
      onDrop={handleDrop}
    />
  );
}

/**
 * Custom Number Input Widget
 */
function NumberWidget(props: WidgetProps) {
  const {
    id,
    value,
    onChange,
    required,
    disabled,
    readonly,
    placeholder,
    schema,
  } = props;

  return (
    <Input
      id={id}
      type="number"
      value={value ?? ""}
      onChange={(e) => {
        const val = e.target.value;
        onChange(val === "" ? undefined : Number(val));
      }}
      required={required}
      disabled={disabled}
      readOnly={readonly}
      placeholder={placeholder}
      min={schema.minimum}
      max={schema.maximum}
      step={schema.multipleOf || (schema.type === "integer" ? 1 : "any")}
    />
  );
}

/**
 * Custom Checkbox/Switch Widget
 */
function CheckboxWidget(props: WidgetProps) {
  const { id, value, onChange, label, disabled, readonly } = props;

  return (
    <div className="flex items-center space-x-2">
      <Switch
        id={id}
        checked={Boolean(value)}
        onCheckedChange={onChange}
        disabled={disabled || readonly}
      />
      <Label htmlFor={id}>{label}</Label>
    </div>
  );
}

/**
 * Custom Select Widget
 */
function SelectWidget(props: WidgetProps) {
  const { id, value, onChange, options, disabled, readonly, placeholder } =
    props;
  const { enumOptions } = options;

  return (
    <Select
      value={value ? String(value) : undefined}
      onValueChange={onChange}
      disabled={disabled || readonly}
    >
      <SelectTrigger id={id}>
        <SelectValue placeholder={placeholder || "Select an option"} />
      </SelectTrigger>
      <SelectContent>
        {(enumOptions as Array<{ value: string; label: string }>)?.map(
          (option) => (
            <SelectItem key={option.value} value={String(option.value)}>
              {option.label}
            </SelectItem>
          ),
        )}
      </SelectContent>
    </Select>
  );
}

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

/**
 * Custom Field Template
 */
function FieldTemplate(props: FieldTemplateProps) {
  const {
    id,
    label,
    children,
    errors,
    help,
    description,
    hidden,
    required,
    displayLabel,
  } = props;

  if (hidden) {
    return <div className="hidden">{children}</div>;
  }

  return (
    <div className="grid gap-2 mb-4">
      {displayLabel && label && (
        <div className="flex items-center gap-1.5">
          <Label htmlFor={id}>
            {label}
            {required && <span className="text-destructive ml-1">*</span>}
          </Label>
          {description && (
            <TooltipProvider delayDuration={300}>
              <Tooltip>
                <TooltipTrigger asChild>
                  <button
                    type="button"
                    className="inline-flex items-center justify-center rounded-full h-4 w-4 text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
                  >
                    <HelpCircle className="h-3.5 w-3.5" />
                  </button>
                </TooltipTrigger>
                <TooltipContent side="right" className="max-w-[300px]">
                  <p className="text-xs">{description}</p>
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
          )}
        </div>
      )}
      {children}
      {errors && <div className="text-xs text-destructive">{errors}</div>}
      {help && <p className="text-xs text-muted-foreground">{help}</p>}
    </div>
  );
}

/**
 * Custom Object Field Template
 */
function ObjectFieldTemplate(props: ObjectFieldTemplateProps) {
  const { title, description, properties } = props;

  return (
    <div className="space-y-4">
      {title && <h4 className="font-medium text-sm">{title}</h4>}
      {description && (
        <p className="text-xs text-muted-foreground mb-2">{description}</p>
      )}
      <div className="space-y-3">
        {properties.map((element) => (
          <div key={element.name}>{element.content}</div>
        ))}
      </div>
    </div>
  );
}

/**
 * Custom Array Field Template
 */
function ArrayFieldTemplate(props: ArrayFieldTemplateProps) {
  const { title, items, canAdd, onAddClick } = props;

  return (
    <div className="space-y-3">
      {title && <h4 className="font-medium text-sm">{title}</h4>}
      <div className="space-y-3">
        {items.map((element) => (
          <div
            key={element.key}
            className="rounded-md border border-border bg-muted/30 p-3 space-y-3"
          >
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-muted-foreground">
                Item {element.index + 1}
              </span>
              {element.hasRemove && (
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-6 w-6 text-muted-foreground"
                  onClick={element.onDropIndexClick(element.index)}
                >
                  <X className="h-3 w-3" />
                </Button>
              )}
            </div>
            {element.children}
          </div>
        ))}
      </div>
      {canAdd && (
        <Button variant="outline" size="sm" onClick={onAddClick}>
          <Plus className="h-3 w-3 mr-1" /> Add Item
        </Button>
      )}
    </div>
  );
}

/**
 * Custom widgets mapping
 */
export const customWidgets: RegistryWidgetsType = {
  TextWidget,
  TextareaWidget,
  NumberWidget,
  CheckboxWidget,
  SelectWidget,
  conditionOperator: ConditionOperatorWidget,
  conditionOperand: ConditionOperandWidget,
};

/**
 * Custom templates
 */
export const customTemplates = {
  FieldTemplate,
  ObjectFieldTemplate,
  ArrayFieldTemplate,
};

/**
 * Export validator for convenience
 */
export { validator };
