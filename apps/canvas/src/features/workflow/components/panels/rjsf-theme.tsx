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
import { Plus, X } from "lucide-react";

/**
 * Custom Text Input Widget
 */
function TextWidget(props: WidgetProps) {
  const { id, value, onChange, required, disabled, readonly, placeholder } =
    props;

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
        <Label htmlFor={id}>
          {label}
          {required && <span className="text-destructive ml-1">*</span>}
        </Label>
      )}
      {description && (
        <p className="text-xs text-muted-foreground">{description}</p>
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
