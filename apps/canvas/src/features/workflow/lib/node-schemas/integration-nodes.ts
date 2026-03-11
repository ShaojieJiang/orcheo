import { RJSFSchema } from "@rjsf/utils";

import { baseNodeSchema } from "@features/workflow/lib/node-schemas/base";

export const integrationNodeSchemas: Record<string, RJSFSchema> = {
  MongoDBNode: {
    type: "object",
    properties: {
      ...baseNodeSchema.properties,
      database: {
        type: "string",
        title: "Database",
        description: "Database to target",
      },
      collection: {
        type: "string",
        title: "Collection",
        description: "Collection to operate on",
      },
      operation: {
        type: "string",
        title: "Operation",
        description: "MongoDB operation to perform",
        enum: [
          "find",
          "find_one",
          "find_raw_batches",
          "insert_one",
          "insert_many",
          "update_one",
          "update_many",
          "replace_one",
          "delete_one",
          "delete_many",
          "aggregate",
          "aggregate_raw_batches",
          "count_documents",
          "estimated_document_count",
          "distinct",
          "find_one_and_delete",
          "find_one_and_replace",
          "find_one_and_update",
          "bulk_write",
          "create_index",
          "create_indexes",
          "drop_index",
          "drop_indexes",
          "list_indexes",
          "index_information",
          "create_search_index",
          "create_search_indexes",
          "drop_search_index",
          "update_search_index",
          "list_search_indexes",
          "drop",
          "rename",
          "options",
          "watch",
        ],
        default: "find",
      },
      query: {
        type: "object",
        title: "Query",
        description: "Arguments passed to the selected operation",
        additionalProperties: true,
        default: {},
      },
    },
    required: ["database", "collection", "operation"],
  },

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

  MessageTelegramNode: {
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

  MessageDiscordNode: {
    type: "object",
    properties: {
      ...baseNodeSchema.properties,
      token: {
        type: "string",
        title: "Bot Token",
        description: "Bot token used to authenticate with Discord",
      },
      channel_id: {
        type: "string",
        title: "Channel ID",
        description: "Discord channel ID",
      },
      message: {
        type: "string",
        title: "Message",
        description: "Message text to send",
      },
      reply_to_message_id: {
        type: "string",
        title: "Reply To Message ID",
        description: "Optional Discord message ID to reply to",
      },
    },
    required: ["token", "channel_id", "message"],
  },

  MessageQQNode: {
    type: "object",
    properties: {
      ...baseNodeSchema.properties,
      app_id: {
        type: "string",
        title: "App ID",
        description: "QQ bot App ID",
      },
      client_secret: {
        type: "string",
        title: "Client Secret",
        description: "QQ bot client secret",
      },
      openid: {
        type: "string",
        title: "User OpenID",
        description: "QQ user openid for C2C replies",
      },
      group_openid: {
        type: "string",
        title: "Group OpenID",
        description: "QQ group openid for group replies",
      },
      channel_id: {
        type: "string",
        title: "Channel ID",
        description: "QQ channel ID for channel replies",
      },
      guild_id: {
        type: "string",
        title: "Guild ID",
        description: "Optional guild ID for channel-context replies",
      },
      message: {
        type: "string",
        title: "Message",
        description: "Message text to send",
      },
      msg_id: {
        type: "string",
        title: "Reply Message ID",
        description: "Optional QQ source message ID for passive replies",
      },
      msg_seq: {
        type: "integer",
        title: "Reply Sequence",
        description: "Sequence number paired with msg_id",
        minimum: 1,
        default: 1,
      },
      sandbox: {
        type: "boolean",
        title: "Sandbox",
        description: "Use the QQ sandbox OpenAPI base URL",
        default: false,
      },
    },
    required: ["app_id", "client_secret", "message"],
  },
};
