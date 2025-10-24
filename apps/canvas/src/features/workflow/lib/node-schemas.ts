/**
 * JSON Schema definitions for Orcheo nodes
 * These schemas match the backend Pydantic models for full parity
 */

import { RJSFSchema } from "@rjsf/utils";

/**
 * Schema for BaseNode fields (inherited by all nodes)
 */
const baseNodeSchema: RJSFSchema = {
  type: "object",
  properties: {
    label: {
      type: "string",
      title: "Node Name",
      description: "Human-readable label for this node",
    },
    description: {
      type: "string",
      title: "Description",
      description: "Optional description of what this node does",
    },
  },
};

/**
 * Schema for ComparisonOperator (used in conditions)
 */
const comparisonOperatorEnum = [
  "equals",
  "not_equals",
  "greater_than",
  "greater_than_or_equal",
  "less_than",
  "less_than_or_equal",
  "contains",
  "not_contains",
  "in",
  "not_in",
  "is_truthy",
  "is_falsy",
];

/**
 * Schema for Condition model
 */
const conditionSchema: RJSFSchema = {
  type: "object",
  title: "Condition",
  properties: {
    left: {
      title: "Left Operand",
      description: "Left-hand operand",
      oneOf: [
        { type: "string" },
        { type: "number" },
        { type: "boolean" },
        { type: "null" },
      ],
    },
    operator: {
      type: "string",
      title: "Operator",
      description: "Comparison operator to evaluate",
      enum: comparisonOperatorEnum,
      default: "equals",
    },
    right: {
      title: "Right Operand",
      description: "Right-hand operand (if required)",
      oneOf: [
        { type: "string" },
        { type: "number" },
        { type: "boolean" },
        { type: "null" },
      ],
    },
    caseSensitive: {
      type: "boolean",
      title: "Case Sensitive",
      description: "Apply case-sensitive comparison for string operands",
      default: true,
    },
  },
  required: ["operator"],
};

/**
 * Schema for SwitchCase model
 */
const switchCaseSchema: RJSFSchema = {
  type: "object",
  title: "Switch Case",
  properties: {
    match: {
      title: "Match Value",
      description: "Value that activates this branch",
      oneOf: [
        { type: "string" },
        { type: "number" },
        { type: "boolean" },
        { type: "null" },
      ],
    },
    label: {
      type: "string",
      title: "Label",
      description: "Optional label used in the canvas",
    },
    branchKey: {
      type: "string",
      title: "Branch Key",
      description: "Identifier emitted when this branch is selected",
    },
    caseSensitive: {
      type: "boolean",
      title: "Case Sensitive",
      description: "Override case-sensitivity for this branch",
    },
  },
};

/**
 * Node-specific schemas
 */
export const nodeSchemas: Record<string, RJSFSchema> = {
  // Base/default schema for unknown node types
  default: {
    ...baseNodeSchema,
  },

  // IfElseNode schema
  IfElseNode: {
    type: "object",
    properties: {
      ...baseNodeSchema.properties,
      conditions: {
        type: "array",
        title: "Conditions",
        description: "Collection of conditions that control branching",
        items: conditionSchema,
        minItems: 1,
        default: [
          {
            left: true,
            operator: "is_truthy",
            right: null,
            caseSensitive: true,
          },
        ],
      },
      conditionLogic: {
        type: "string",
        title: "Condition Logic",
        description: "Combine conditions using logical AND/OR semantics",
        enum: ["and", "or"],
        default: "and",
      },
    },
    required: ["conditions", "conditionLogic"],
  },

  // SwitchNode schema
  SwitchNode: {
    type: "object",
    properties: {
      ...baseNodeSchema.properties,
      value: {
        title: "Value",
        description: "Value to inspect for routing decisions",
        oneOf: [
          { type: "string" },
          { type: "number" },
          { type: "boolean" },
          { type: "object" },
        ],
      },
      caseSensitive: {
        type: "boolean",
        title: "Case Sensitive",
        description: "Preserve case when deriving branch keys",
        default: true,
      },
      defaultBranchKey: {
        type: "string",
        title: "Default Branch Key",
        description: "Branch identifier returned when no cases match",
        default: "default",
      },
      cases: {
        type: "array",
        title: "Cases",
        description: "Collection of matchable branches",
        items: switchCaseSchema,
        minItems: 1,
      },
    },
    required: ["value", "cases"],
  },

  // WhileNode schema
  WhileNode: {
    type: "object",
    properties: {
      ...baseNodeSchema.properties,
      conditions: {
        type: "array",
        title: "Loop Conditions",
        description: "Collection of conditions that control continuation",
        items: conditionSchema,
        minItems: 1,
        default: [
          {
            operator: "less_than",
            caseSensitive: true,
          },
        ],
      },
      conditionLogic: {
        type: "string",
        title: "Condition Logic",
        description: "Combine conditions using logical AND/OR semantics",
        enum: ["and", "or"],
        default: "and",
      },
      maxIterations: {
        type: "integer",
        title: "Max Iterations",
        description: "Optional guard to stop after this many iterations",
        minimum: 1,
      },
    },
    required: ["conditions", "conditionLogic"],
  },

  // SetVariableNode schema
  SetVariableNode: {
    type: "object",
    properties: {
      ...baseNodeSchema.properties,
      targetPath: {
        type: "string",
        title: "Target Path",
        description:
          "Path to store the provided value (e.g., context.user.name)",
        default: "context.value",
      },
      value: {
        title: "Value",
        description: "Value to persist",
        oneOf: [
          { type: "string" },
          { type: "number" },
          { type: "boolean" },
          { type: "object" },
          { type: "array" },
        ],
      },
    },
    required: ["targetPath", "value"],
  },

  // DelayNode schema
  DelayNode: {
    type: "object",
    properties: {
      ...baseNodeSchema.properties,
      durationSeconds: {
        type: "number",
        title: "Duration (seconds)",
        description: "Duration of the pause expressed in seconds",
        minimum: 0,
        default: 0,
      },
    },
    required: ["durationSeconds"],
  },

  // Agent (AI) Node schema
  Agent: {
    type: "object",
    properties: {
      ...baseNodeSchema.properties,
      modelSettings: {
        type: "object",
        title: "Model Settings",
        description: "Configuration for the AI model",
        properties: {
          model: {
            type: "string",
            title: "Model",
            description: "Model identifier (e.g., gpt-4, claude-3-opus)",
          },
          temperature: {
            type: "number",
            title: "Temperature",
            description: "Controls randomness in responses",
            minimum: 0,
            maximum: 2,
            default: 0.7,
          },
          maxTokens: {
            type: "integer",
            title: "Max Tokens",
            description: "Maximum number of tokens to generate",
            minimum: 1,
          },
        },
      },
      systemPrompt: {
        type: "string",
        title: "System Prompt",
        description: "System prompt for the agent",
      },
      checkpointer: {
        type: "string",
        title: "Checkpointer",
        description: "Checkpointer used to save the agent's state",
        enum: ["memory", "sqlite", "postgres"],
      },
      structuredOutput: {
        type: "object",
        title: "Structured Output",
        description: "Configuration for structured output",
        properties: {
          schemaType: {
            type: "string",
            title: "Schema Type",
            enum: ["json_schema", "json_dict", "pydantic", "typed_dict"],
          },
          schemaStr: {
            type: "string",
            title: "Schema Definition",
            description: "The schema definition as a string",
          },
        },
      },
    },
    required: ["modelSettings"],
  },

  // PythonCode Node schema
  PythonCode: {
    type: "object",
    properties: {
      ...baseNodeSchema.properties,
      code: {
        type: "string",
        title: "Python Code",
        description: "Python code to execute",
        default: "def run(state, config):\n    return {}\n",
      },
    },
    required: ["code"],
  },

  // MongoDBNode schema
  MongoDBNode: {
    type: "object",
    properties: {
      ...baseNodeSchema.properties,
      connectionString: {
        type: "string",
        title: "Connection String",
        description: "MongoDB connection string",
      },
      database: {
        type: "string",
        title: "Database",
        description: "Database name",
      },
      collection: {
        type: "string",
        title: "Collection",
        description: "Collection name",
      },
      operation: {
        type: "string",
        title: "Operation",
        description: "MongoDB operation to perform",
        enum: [
          "find",
          "findOne",
          "insertOne",
          "insertMany",
          "updateOne",
          "updateMany",
          "deleteOne",
          "deleteMany",
        ],
      },
      query: {
        type: "object",
        title: "Query",
        description: "Query filter",
      },
      document: {
        type: "object",
        title: "Document",
        description: "Document to insert or update",
      },
    },
    required: ["connectionString", "database", "collection", "operation"],
  },

  // RSSNode schema
  RSSNode: {
    type: "object",
    properties: {
      ...baseNodeSchema.properties,
      feedUrl: {
        type: "string",
        title: "Feed URL",
        description: "URL of the RSS feed",
        format: "uri",
      },
      maxItems: {
        type: "integer",
        title: "Max Items",
        description: "Maximum number of items to fetch",
        minimum: 1,
        default: 10,
      },
    },
    required: ["feedUrl"],
  },

  // SlackNode schema
  SlackNode: {
    type: "object",
    properties: {
      ...baseNodeSchema.properties,
      tool_name: {
        type: "string",
        title: "Slack Tool",
        description: "Select the MCP Slack tool to invoke",
        enum: [
          "slack_list_channels",
          "slack_post_message",
          "slack_reply_to_thread",
          "slack_add_reaction",
          "slack_get_channel_history",
          "slack_get_thread_replies",
          "slack_get_users",
          "slack_get_user_profile",
        ],
      },
      kwargs: {
        type: "object",
        title: "Tool Arguments",
        description:
          "Arguments passed to the selected Slack MCP tool (JSON object)",
        additionalProperties: true,
        default: {},
      },
    },
    required: ["tool_name"],
  },

  // MessageTelegram (Telegram) Node schema
  MessageTelegram: {
    type: "object",
    properties: {
      ...baseNodeSchema.properties,
      token: {
        type: "string",
        title: "Bot Token",
        description: "Bot token used to authenticate with Telegram",
      },
      chat_id: {
        type: "string",
        title: "Chat ID",
        description: "Telegram chat ID",
      },
      message: {
        type: "string",
        title: "Message",
        description: "Message text to send",
      },
      parse_mode: {
        type: "string",
        title: "Parse Mode",
        description: "Message parsing mode",
        enum: ["Markdown", "HTML", "MarkdownV2"],
      },
    },
    required: ["token", "chat_id", "message"],
  },

  // Trigger nodes
  WebhookTriggerNode: {
    type: "object",
    properties: {
      ...baseNodeSchema.properties,
      path: {
        type: "string",
        title: "Webhook Path",
        description: "URL path for the webhook",
        pattern: "^/.*",
      },
      method: {
        type: "string",
        title: "HTTP Method",
        description: "HTTP method to accept",
        enum: ["GET", "POST", "PUT", "PATCH", "DELETE"],
        default: "POST",
      },
      validateSignature: {
        type: "boolean",
        title: "Validate Signature",
        description: "Require signature validation",
        default: false,
      },
    },
    required: ["path"],
  },

  CronTriggerNode: {
    type: "object",
    properties: {
      ...baseNodeSchema.properties,
      expression: {
        type: "string",
        title: "Cron Expression",
        description:
          "Cron expression (e.g., '0 0 * * *' for daily at midnight)",
        default: "0 * * * *",
      },
      timezone: {
        type: "string",
        title: "Timezone",
        description: "Timezone for the schedule (e.g., 'America/New_York')",
        default: "UTC",
      },
      allow_overlapping: {
        type: "boolean",
        title: "Allow Overlapping Runs",
        description: "Permit multiple runs to overlap in time",
        default: false,
      },
      start_at: {
        type: "string",
        format: "date-time",
        title: "Start At",
        description: "Optional ISO timestamp for when the schedule begins",
      },
      end_at: {
        type: "string",
        format: "date-time",
        title: "End At",
        description: "Optional ISO timestamp for when the schedule ends",
      },
    },
    required: ["expression"],
  },

  ManualTriggerNode: {
    type: "object",
    properties: {
      ...baseNodeSchema.properties,
      label: {
        type: "string",
        title: "Label",
        description: "Label displayed for manual trigger actions",
        default: "manual",
      },
      allowed_actors: {
        type: "array",
        title: "Allowed Actors",
        description: "Users permitted to trigger this workflow",
        items: {
          type: "string",
        },
        default: [],
      },
      require_comment: {
        type: "boolean",
        title: "Require Comment",
        description: "Require users to supply a comment when triggering",
        default: false,
      },
      default_payload: {
        type: "object",
        title: "Default Payload",
        description: "JSON payload provided to the workflow on trigger",
        default: {},
      },
      cooldown_seconds: {
        type: "integer",
        title: "Cooldown (seconds)",
        description: "Minimum seconds between manual trigger runs",
        minimum: 0,
        default: 0,
      },
    },
  },

  HttpPollingTriggerNode: {
    type: "object",
    properties: {
      ...baseNodeSchema.properties,
      url: {
        type: "string",
        title: "URL",
        description: "URL to poll",
        format: "uri",
      },
      method: {
        type: "string",
        title: "HTTP Method",
        description: "HTTP method to use when polling",
        enum: ["GET", "POST", "PUT", "PATCH", "DELETE"],
        default: "GET",
      },
      headers: {
        type: "object",
        title: "Headers",
        description: "HTTP headers to send with the request",
        default: {},
      },
      query_params: {
        type: "object",
        title: "Query Parameters",
        description: "Query parameters to include in the request",
        default: {},
      },
      body: {
        type: "object",
        title: "Request Body",
        description: "JSON body to send with the request",
      },
      interval_seconds: {
        type: "integer",
        title: "Poll Interval (seconds)",
        description: "How often to poll the URL",
        minimum: 1,
        default: 300,
      },
      timeout_seconds: {
        type: "integer",
        title: "Timeout (seconds)",
        description: "How long to wait for the request before timing out",
        minimum: 1,
        default: 30,
      },
      verify_tls: {
        type: "boolean",
        title: "Verify TLS",
        description: "Verify TLS certificates for HTTPS requests",
        default: true,
      },
      follow_redirects: {
        type: "boolean",
        title: "Follow Redirects",
        description: "Follow HTTP redirects when polling",
        default: false,
      },
      deduplicate_on: {
        type: "string",
        title: "Deduplicate On",
        description:
          "Optional key in the response used to deduplicate trigger events",
      },
    },
    required: ["url", "interval_seconds"],
  },
};

/**
 * UI Schema definitions for custom form rendering
 */
export const nodeUiSchemas: Record<string, Record<string, unknown>> = {
  default: {
    description: {
      "ui:widget": "textarea",
      "ui:options": {
        rows: 3,
      },
    },
  },

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
};

/**
 * Get the JSON Schema for a specific node type
 */
export function getNodeSchema(
  backendType: string | null | undefined,
): RJSFSchema {
  if (!backendType) {
    return nodeSchemas.default;
  }
  return nodeSchemas[backendType] || nodeSchemas.default;
}

/**
 * Get the UI Schema for a specific node type
 */
export function getNodeUiSchema(
  backendType: string | null | undefined,
): Record<string, unknown> {
  if (!backendType) {
    return nodeUiSchemas.default;
  }
  return {
    ...nodeUiSchemas.default,
    ...(nodeUiSchemas[backendType] || {}),
  };
}
