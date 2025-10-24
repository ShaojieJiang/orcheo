import Form, { type FormProps } from "@rjsf/core";
import type {
  FieldTemplateProps,
  RJSFSchema,
  RJSFValidationError,
  UiSchema,
  WidgetProps,
  RegistryWidgetsType,
} from "@rjsf/utils";
import validator from "@rjsf/validator-ajv8";
import { Button } from "@/design-system/ui/button";
import { Input } from "@/design-system/ui/input";
import { Textarea } from "@/design-system/ui/textarea";
import { Switch } from "@/design-system/ui/switch";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/design-system/ui/select";
import { Label } from "@/design-system/ui/label";
import { cn } from "@/lib/utils";

export interface SchemaDrivenFormProps<FormData = Record<string, unknown>> {
  schema: RJSFSchema;
  uiSchema?: UiSchema;
  formData?: FormData;
  disabled?: boolean;
  readonly?: boolean;
  className?: string;
  onChange?: (formData: FormData) => void;
  onSubmit?: (formData: FormData) => void;
  onError?: (errors: RJSFValidationError[]) => void;
}

const isString = (value: unknown): value is string => typeof value === "string";

const BaseFieldTemplate = (props: FieldTemplateProps) => {
  const {
    id,
    classNames,
    style,
    label,
    required,
    description,
    errors,
    help,
    children,
    displayLabel,
  } = props;

  return (
    <div className={cn("space-y-2", classNames)} style={style}>
      {displayLabel && label && (
        <Label htmlFor={id} className="text-sm font-medium">
          {label}
          {required ? <span className="text-destructive ml-1">*</span> : null}
        </Label>
      )}
      {description}
      {children}
      <div className="space-y-1 text-sm text-destructive">{errors}</div>
      <div className="text-xs text-muted-foreground">{help}</div>
    </div>
  );
};

const TextWidget = ({
  id,
  value,
  required,
  disabled,
  readonly,
  placeholder,
  onChange,
  onBlur,
  onFocus,
}: WidgetProps) => (
  <Input
    id={id}
    value={value ?? ""}
    required={required}
    disabled={disabled || readonly}
    placeholder={isString(placeholder) ? placeholder : undefined}
    onChange={(event) => onChange(event.target.value)}
    onBlur={(event) => onBlur(id, event.target.value)}
    onFocus={(event) => onFocus(id, event.target.value)}
  />
);

const TextareaWidget = ({
  id,
  value,
  required,
  disabled,
  readonly,
  placeholder,
  onChange,
  onBlur,
  onFocus,
}: WidgetProps) => (
  <Textarea
    id={id}
    value={value ?? ""}
    required={required}
    disabled={disabled || readonly}
    placeholder={isString(placeholder) ? placeholder : undefined}
    onChange={(event) => onChange(event.target.value)}
    onBlur={(event) => onBlur(id, event.target.value)}
    onFocus={(event) => onFocus(id, event.target.value)}
    rows={4}
  />
);

const NumberWidget = ({
  id,
  value,
  required,
  disabled,
  readonly,
  placeholder,
  onChange,
  onBlur,
  onFocus,
}: WidgetProps) => {
  const stringValue =
    value === undefined || value === null ? "" : String(value);
  return (
    <Input
      id={id}
      type="number"
      value={stringValue}
      required={required}
      disabled={disabled || readonly}
      placeholder={isString(placeholder) ? placeholder : undefined}
      onChange={(event) => {
        const raw = event.target.value;
        onChange(raw === "" ? undefined : Number(raw));
      }}
      onBlur={(event) => onBlur(id, event.target.value)}
      onFocus={(event) => onFocus(id, event.target.value)}
    />
  );
};

const CheckboxWidget = ({
  id,
  value,
  disabled,
  readonly,
  onChange,
  onBlur,
  onFocus,
}: WidgetProps) => {
  const checked = Boolean(value);
  return (
    <div className="flex items-center gap-2">
      <Switch
        id={id}
        checked={checked}
        disabled={disabled || readonly}
        onCheckedChange={(next) => onChange(Boolean(next))}
        onBlur={() => onBlur(id, checked)}
        onFocus={() => onFocus(id, checked)}
      />
      <Label htmlFor={id} className="text-sm text-muted-foreground">
        {checked ? "Enabled" : "Disabled"}
      </Label>
    </div>
  );
};

const SelectWidget = ({
  id,
  value,
  disabled,
  readonly,
  placeholder,
  options,
  onChange,
  onBlur,
  onFocus,
}: WidgetProps) => {
  const { enumOptions = [] } = options;
  const stringValue =
    value === undefined || value === null
      ? ""
      : String(value as string | number | boolean);

  return (
    <Select
      value={stringValue}
      onValueChange={(nextValue) => {
        const match = enumOptions.find(
          (option) => String(option.value) === nextValue,
        );
        onChange(match ? match.value : nextValue);
      }}
      disabled={disabled || readonly}
    >
      <SelectTrigger
        id={id}
        onBlur={() => onBlur(id, value)}
        onFocus={() => onFocus(id, value)}
      >
        <SelectValue
          placeholder={isString(placeholder) ? placeholder : undefined}
        />
      </SelectTrigger>
      <SelectContent>
        {enumOptions.map((option) => (
          <SelectItem key={String(option.value)} value={String(option.value)}>
            {isString(option.label) ? option.label : String(option.value)}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
};

const widgets: RegistryWidgetsType = {
  TextWidget,
  TextareaWidget,
  SelectWidget,
  CheckboxWidget,
  PasswordWidget: TextWidget,
  EmailWidget: TextWidget,
  URLWidget: TextWidget,
  DateWidget: TextWidget,
  DateTimeWidget: TextWidget,
  AltDateWidget: TextWidget,
  TimeWidget: TextWidget,
  ColorWidget: TextWidget,
  NumberWidget,
  IntegerWidget: NumberWidget,
};

export function SchemaDrivenForm<FormData = Record<string, unknown>>({
  schema,
  uiSchema,
  formData,
  disabled,
  readonly,
  className,
  onChange,
  onSubmit,
  onError,
}: SchemaDrivenFormProps<FormData>) {
  const handleChange: FormProps<FormData>["onChange"] | undefined = onChange
    ? (event) => {
        onChange(event.formData ?? ({} as FormData));
      }
    : undefined;

  const handleSubmit: FormProps<FormData>["onSubmit"] | undefined = onSubmit
    ? (event, originalEvent) => {
        if (
          originalEvent &&
          typeof originalEvent.preventDefault === "function"
        ) {
          originalEvent.preventDefault();
        }
        onSubmit(event.formData ?? ({} as FormData));
      }
    : undefined;

  const handleError: FormProps<FormData>["onError"] | undefined = onError
    ? (errors) => {
        onError(errors);
      }
    : undefined;

  return (
    <Form<FormData>
      className={cn("space-y-4", className)}
      schema={schema}
      uiSchema={uiSchema}
      formData={formData}
      validator={validator}
      widgets={widgets}
      templates={{
        FieldTemplate: BaseFieldTemplate,
        ButtonTemplates: {
          SubmitButton: (props) =>
            onSubmit ? (
              <Button
                type="submit"
                size="sm"
                className="ml-auto"
                disabled={props.disabled}
              >
                {props.uiSchema?.["ui:options"]?.submitButtonText ??
                  "Save configuration"}
              </Button>
            ) : null,
        },
      }}
      noHtml5Validate
      showErrorList={false}
      disabled={disabled}
      readonly={readonly}
      onChange={handleChange}
      onSubmit={handleSubmit}
      onError={handleError}
    >
      {onSubmit ? undefined : null}
    </Form>
  );
}

export default SchemaDrivenForm;
