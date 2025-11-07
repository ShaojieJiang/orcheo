import { RJSFSchema } from "@rjsf/utils";

import { baseNodeSchema } from "@features/workflow/lib/node-schemas/base";

export const triggerNodeSchemas: Record<string, RJSFSchema> = {
  WebhookTriggerNode: {
    type: "object",
    properties: {
      ...baseNodeSchema.properties,
      allowed_methods: {
        type: "array",
        title: "Allowed Methods",
        description: "HTTP methods accepted by this webhook",
        items: {
          type: "string",
          enum: ["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD"],
        },
        minItems: 1,
        default: ["POST"],
      },
      required_headers: {
        type: "object",
        title: "Required Headers",
        description: "Headers that must be present with specific values",
        additionalProperties: { type: "string" },
        default: {},
      },
      required_query_params: {
        type: "object",
        title: "Required Query Parameters",
        description: "Query parameters that must match expected values",
        additionalProperties: { type: "string" },
        default: {},
      },
      shared_secret_header: {
        type: "string",
        title: "Shared Secret Header",
        description: "Optional HTTP header containing a shared secret",
      },
      shared_secret: {
        type: "string",
        title: "Shared Secret",
        description: "Secret value required when validating webhook requests",
      },
      rate_limit: {
        type: "object",
        title: "Rate Limit",
        description: "Optional rate limiting configuration",
        properties: {
          limit: {
            type: "integer",
            title: "Limit",
            description: "Maximum number of requests in the interval",
            minimum: 1,
            default: 60,
          },
          interval_seconds: {
            type: "integer",
            title: "Interval (seconds)",
            description: "Time window in seconds for the rate limit",
            minimum: 1,
            default: 60,
          },
        },
      },
    },
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
