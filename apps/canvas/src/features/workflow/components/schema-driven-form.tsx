import Form, { type FormProps } from "@rjsf/core";
import type {
  ErrorListProps,
  FieldTemplateProps,
  RJSFSchema,
  RJSFValidationError,
  UiSchema,
  WidgetProps,
  RegistryWidgetsType,
} from "@rjsf/utils";
import { AlertCircle } from "lucide-react";
import validator from "@rjsf/validator-ajv8";
import { Alert, AlertDescription, AlertTitle } from "@/design-system/ui/alert";
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

  const descriptionId = description ? `${id}-description` : undefined;
  const errorId = errors ? `${id}-error` : undefined;
  const helpId = help ? `${id}-help` : undefined;

  return (
    <div className={cn("space-y-2", classNames)} style={style}>
      {displayLabel && label && (
        <Label htmlFor={id} className="text-sm font-medium">
          {label}
          {required ? <span className="text-destructive ml-1">*</span> : null}
        </Label>
      )}
      {description ? (
        <div id={descriptionId} className="text-xs text-muted-foreground">
          {description}
        </div>
      ) : null}
      {children}
      <div id={errorId} className="space-y-1 text-sm text-destructive">
        {errors}
      </div>
      <div id={helpId} className="text-xs text-muted-foreground">
        {help}
      </div>
    </div>
  );
};

const buildDescribedBy = (
  id: string,
  schema: unknown,
  uiSchema: UiSchema | undefined,
  rawErrors?: string[],
) => {
  const describedBy: string[] = [];
  if (rawErrors && rawErrors.length > 0) {
    describedBy.push(`${id}-error`);
  }
  if (
    schema &&
    typeof schema === "object" &&
    schema !== null &&
    "description" in schema &&
    isString((schema as RJSFSchema).description) &&
    (schema as RJSFSchema).description.length > 0
  ) {
    describedBy.push(`${id}-description`);
  }
  const helpContent = uiSchema?.["ui:help"];
  if (
    (isString(helpContent) && helpContent.length > 0) ||
    (helpContent && typeof helpContent !== "boolean")
  ) {
    describedBy.push(`${id}-help`);
  }
  return describedBy.length > 0 ? describedBy.join(" ") : undefined;
};

const toStringValue = (value: unknown): string =>
  value === undefined || value === null ? "" : String(value);

const TextWidget = ({
  id,
  value,
  required,
  disabled,
  readonly,
  placeholder,
  label,
  rawErrors,
  schema,
  uiSchema,
  onChange,
  onBlur,
  onFocus,
}: WidgetProps) => {
  const describedBy = buildDescribedBy(id, schema, uiSchema, rawErrors);
  return (
    <Input
      id={id}
      type="text"
      value={value ?? ""}
      required={required}
      disabled={disabled || readonly}
      placeholder={isString(placeholder) ? placeholder : undefined}
      aria-label={isString(label) && label.length > 0 ? label : undefined}
      aria-invalid={rawErrors !== undefined && rawErrors.length > 0}
      aria-describedby={describedBy}
      onChange={(event) => onChange(event.target.value)}
      onBlur={(event) => onBlur(id, event.target.value)}
      onFocus={(event) => onFocus(id, event.target.value)}
    />
  );
};

const TextareaWidget = ({
  id,
  value,
  required,
  disabled,
  readonly,
  placeholder,
  label,
  rawErrors,
  schema,
  uiSchema,
  onChange,
  onBlur,
  onFocus,
}: WidgetProps) => {
  const describedBy = buildDescribedBy(id, schema, uiSchema, rawErrors);
  return (
    <Textarea
      id={id}
      value={value ?? ""}
      required={required}
      disabled={disabled || readonly}
      placeholder={isString(placeholder) ? placeholder : undefined}
      aria-label={isString(label) && label.length > 0 ? label : undefined}
      aria-invalid={rawErrors !== undefined && rawErrors.length > 0}
      aria-describedby={describedBy}
      onChange={(event) => onChange(event.target.value)}
      onBlur={(event) => onBlur(id, event.target.value)}
      onFocus={(event) => onFocus(id, event.target.value)}
      rows={4}
    />
  );
};

const NumberWidget = ({
  id,
  value,
  required,
  disabled,
  readonly,
  placeholder,
  label,
  rawErrors,
  schema,
  uiSchema,
  onChange,
  onBlur,
  onFocus,
}: WidgetProps) => {
  const stringValue = toStringValue(value);
  const describedBy = buildDescribedBy(id, schema, uiSchema, rawErrors);
  return (
    <Input
      id={id}
      type="number"
      value={stringValue}
      required={required}
      disabled={disabled || readonly}
      placeholder={isString(placeholder) ? placeholder : undefined}
      aria-label={isString(label) && label.length > 0 ? label : undefined}
      aria-invalid={rawErrors !== undefined && rawErrors.length > 0}
      aria-describedby={describedBy}
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
  label,
  rawErrors,
  schema,
  uiSchema,
  onChange,
  onBlur,
  onFocus,
}: WidgetProps) => {
  const checked = Boolean(value);
  const describedBy = buildDescribedBy(id, schema, uiSchema, rawErrors);
  return (
    <div className="flex items-center gap-2">
      <Switch
        id={id}
        checked={checked}
        disabled={disabled || readonly}
        aria-label={isString(label) && label.length > 0 ? label : undefined}
        aria-checked={checked}
        aria-describedby={describedBy}
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
  label,
  rawErrors,
  schema,
  uiSchema,
  onChange,
  onBlur,
  onFocus,
}: WidgetProps) => {
  const { enumOptions = [] } = options;
  const stringValue = toStringValue(value);
  const describedBy = buildDescribedBy(id, schema, uiSchema, rawErrors);

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
        aria-label={isString(label) && label.length > 0 ? label : undefined}
        aria-invalid={rawErrors !== undefined && rawErrors.length > 0}
        aria-describedby={describedBy}
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

const createTypedInputWidget = (
  type: React.ComponentProps<typeof Input>["type"],
) =>
  function TypedInputWidget(props: WidgetProps) {
    const {
      id,
      value,
      required,
      disabled,
      readonly,
      placeholder,
      label,
      rawErrors,
      schema,
      uiSchema,
      onChange,
      onBlur,
      onFocus,
    } = props;
    const describedBy = buildDescribedBy(id, schema, uiSchema, rawErrors);
    return (
      <Input
        id={id}
        type={type}
        value={value ?? ""}
        required={required}
        disabled={disabled || readonly}
        placeholder={isString(placeholder) ? placeholder : undefined}
        aria-label={isString(label) && label.length > 0 ? label : undefined}
        aria-invalid={rawErrors !== undefined && rawErrors.length > 0}
        aria-describedby={describedBy}
        onChange={(event) => onChange(event.target.value)}
        onBlur={(event) => onBlur(id, event.target.value)}
        onFocus={(event) => onFocus(id, event.target.value)}
      />
    );
  };

const PasswordWidget = createTypedInputWidget("password");
const EmailWidget = createTypedInputWidget("email");
const URLWidget = createTypedInputWidget("url");
const DateWidget = createTypedInputWidget("date");
const DateTimeWidget = createTypedInputWidget("datetime-local");
const TimeWidget = createTypedInputWidget("time");
const ColorWidget = createTypedInputWidget("color");

const widgets: RegistryWidgetsType = {
  TextWidget,
  TextareaWidget,
  SelectWidget,
  CheckboxWidget,
  PasswordWidget,
  EmailWidget,
  URLWidget,
  DateWidget,
  DateTimeWidget,
  AltDateWidget: DateWidget,
  TimeWidget,
  ColorWidget,
  NumberWidget,
  IntegerWidget: NumberWidget,
};

const ErrorListTemplate = ({ errors }: ErrorListProps) => {
  if (!errors || errors.length === 0) {
    return null;
  }

  return (
    <Alert variant="destructive" className="flex items-start gap-3">
      <AlertCircle className="mt-0.5 h-4 w-4" />
      <div className="space-y-2">
        <AlertTitle>Check the highlighted fields</AlertTitle>
        <AlertDescription>
          <ul className="list-disc space-y-1 pl-4 text-sm">
            {errors.map((error) => (
              <li key={error.stack}>{error.stack}</li>
            ))}
          </ul>
        </AlertDescription>
      </div>
    </Alert>
  );
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
        ErrorListTemplate,
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
      showErrorList
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
