import { conditionOperatorGroups } from "@features/workflow/lib/node-schemas/condition-operators";

const baseUiSchema: Record<string, unknown> = {
  description: {
    "ui:widget": "textarea",
    "ui:options": {
      rows: 3,
    },
  },
};

const buildConditionUi = () => ({
  conditions: {
    items: {
      left: {
        "ui:widget": "conditionOperand",
        "ui:placeholder": "Enter left operand",
      },
      operator: {
        "ui:widget": "conditionOperator",
        "ui:options": {
          operatorGroups: conditionOperatorGroups,
        },
      },
      right: {
        "ui:widget": "conditionOperand",
        "ui:placeholder": "Enter right operand (if required)",
      },
    },
  },
});

export const nodeUiSchemas: Record<string, Record<string, unknown>> = {
  default: baseUiSchema,
  IfElseNode: buildConditionUi(),
  WhileNode: buildConditionUi(),
  PythonCode: {
    code: {
      "ui:widget": "textarea",
      "ui:options": {
        rows: 15,
      },
    },
  },
  Agent: {
    systemPrompt: {
      "ui:widget": "textarea",
      "ui:options": {
        rows: 5,
      },
    },
    structuredOutput: {
      schemaStr: {
        "ui:widget": "textarea",
        "ui:options": {
          rows: 10,
        },
      },
    },
  },
  MessageTelegram: {
    message: {
      "ui:widget": "textarea",
      "ui:options": {
        rows: 5,
      },
    },
    token: {
      "ui:widget": "password",
    },
  },
  SlackNode: {
    kwargs: {
      "ui:widget": "textarea",
      "ui:options": {
        rows: 5,
      },
    },
  },
  WebhookTriggerNode: {
    allowed_methods: {
      "ui:widget": "checkboxes",
    },
    shared_secret: {
      "ui:widget": "password",
    },
  },
};
