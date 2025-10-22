export interface WorkflowNode {
  id: string;
  type: string;
  position: { x: number; y: number };
  data: {
    label: string;
    description?: string;
    status?: "idle" | "running" | "success" | "error";
    isDisabled?: boolean;
    [key: string]: unknown;
  };
}

export interface WorkflowEdge {
  id: string;
  source: string;
  target: string;
  sourceHandle?: string | null;
  targetHandle?: string | null;
  label?: string;
  type?: string;
  animated?: boolean;
  style?: Record<string, unknown>;
}

export interface Workflow {
  id: string;
  name: string;
  description?: string;
  createdAt: string;
  updatedAt: string;
  sourceExample?: string;
  owner: {
    id: string;
    name: string;
    avatar: string;
  };
  tags: string[];
  lastRun?: {
    status: "success" | "error" | "running" | "idle";
    timestamp: string;
    duration: number;
  };
  nodes: WorkflowNode[];
  edges: WorkflowEdge[];
}

const TEMPLATE_OWNER: Workflow["owner"] = {
  id: "team-templates",
  name: "Orcheo Templates",
  avatar: "https://avatar.vercel.sh/templates",
};

export const SAMPLE_WORKFLOWS: Workflow[] = [
  {
    id: "workflow-quickstart",
    name: "Canvas Quickstart — Welcome Bot",
    description:
      "Greets a new teammate with a PythonCode node and saves the message to the canvas flow.",
    createdAt: "2024-01-15T10:00:00Z",
    updatedAt: "2024-03-04T15:30:00Z",
    sourceExample: "examples/quickstart/canvas_welcome.json",
    owner: TEMPLATE_OWNER,
    tags: ["template", "quickstart", "canvas"],
    lastRun: {
      status: "success",
      timestamp: "2024-03-05T08:45:00Z",
      duration: 3.1,
    },
    nodes: [
      {
        id: "start",
        type: "start",
        position: { x: 0, y: 0 },
        data: {
          label: "Start",
          type: "start",
          description: "Entry point for the welcome flow.",
        },
      },
      {
        id: "compose-welcome-message",
        type: "function",
        position: { x: 260, y: 0 },
        data: {
          label: "Compose welcome message",
          type: "function",
          description:
            "PythonCode node returns a templated greeting for the new teammate.",
          examplePath: "examples/quickstart/canvas_welcome.json",
        },
      },
      {
        id: "end",
        type: "end",
        position: { x: 520, y: 0 },
        data: {
          label: "Finish",
          type: "end",
          description: "Flow completes after crafting the welcome message.",
        },
      },
    ],
    edges: [
      {
        id: "edge-start-compose",
        source: "start",
        target: "compose-welcome-message",
      },
      {
        id: "edge-compose-end",
        source: "compose-welcome-message",
        target: "end",
      },
    ],
  },
  {
    id: "workflow-python-hello",
    name: "Simple Python Task",
    description: "Runs a standalone PythonCode node and returns a greeting.",
    createdAt: "2024-01-18T12:00:00Z",
    updatedAt: "2024-03-10T09:15:00Z",
    owner: TEMPLATE_OWNER,
    tags: ["template", "python", "utility"],
    nodes: [
      {
        id: "python-start",
        type: "start",
        position: { x: 0, y: 0 },
        data: {
          label: "Start",
          type: "start",
          description: "Kick off the simple Python workflow.",
        },
      },
      {
        id: "python-greet",
        type: "Python",
        position: { x: 260, y: 0 },
        data: {
          label: "Run Python code",
          type: "python",
          description: "PythonCode node that returns a hello message.",
          codeExample: "return {'message': 'Hello from Python!'}",
        },
      },
      {
        id: "python-end",
        type: "end",
        position: { x: 520, y: 0 },
        data: {
          label: "Finish",
          type: "end",
          description: "Ends after the Python node executes.",
        },
      },
    ],
    edges: [
      {
        id: "edge-python-start-greet",
        source: "python-start",
        target: "python-greet",
      },
      {
        id: "edge-python-greet-end",
        source: "python-greet",
        target: "python-end",
      },
    ],
  },
  {
    id: "workflow-feedly-digest",
    name: "Feedly Digest to Telegram",
    description:
      "Captures a Feedly token, fetches unread items, and sends a Telegram digest.",
    createdAt: "2024-01-22T09:10:00Z",
    updatedAt: "2024-03-07T12:05:00Z",
    sourceExample: "examples/feedly_news.py",
    owner: TEMPLATE_OWNER,
    tags: ["template", "news", "telegram", "automation"],
    lastRun: {
      status: "success",
      timestamp: "2024-03-08T05:00:00Z",
      duration: 57.8,
    },
    nodes: [
      {
        id: "feedly-start",
        type: "start",
        position: { x: 0, y: 0 },
        data: {
          label: "Start",
          type: "start",
          description: "Kick off the Feedly news digest workflow.",
        },
      },
      {
        id: "collect-feedly-token",
        type: "function",
        position: { x: 220, y: 0 },
        data: {
          label: "Collect Feedly token",
          type: "function",
          description:
            "Browser automation retrieves the Feedly developer token.",
          examplePath: "examples/feedly_news.py",
        },
      },
      {
        id: "fetch-unread-articles",
        type: "api",
        position: { x: 440, y: 0 },
        data: {
          label: "Fetch unread articles",
          type: "api",
          description:
            "HTTP request pulls unread articles and formats them for Telegram.",
          examplePath: "examples/feedly_news.py",
        },
      },
      {
        id: "send-telegram-digest",
        type: "api",
        position: { x: 660, y: 0 },
        data: {
          label: "Send Telegram digest",
          type: "api",
          description:
            "MessageTelegram sends the formatted digest to the configured chat.",
          examplePath: "examples/feedly_news.py",
        },
      },
      {
        id: "mark-as-read",
        type: "api",
        position: { x: 660, y: 160 },
        data: {
          label: "Mark entries as read",
          type: "api",
          description:
            "Optional HTTP call updates Feedly with the read status.",
          isDisabled: true,
          examplePath: "examples/feedly_news.py",
        },
      },
      {
        id: "feedly-end",
        type: "end",
        position: { x: 880, y: 0 },
        data: {
          label: "Finish",
          type: "end",
          description: "Workflow completes after sending notifications.",
        },
      },
    ],
    edges: [
      {
        id: "edge-start-token",
        source: "feedly-start",
        target: "collect-feedly-token",
      },
      {
        id: "edge-token-fetch",
        source: "collect-feedly-token",
        target: "fetch-unread-articles",
      },
      {
        id: "edge-fetch-telegram",
        source: "fetch-unread-articles",
        target: "send-telegram-digest",
      },
      {
        id: "edge-telegram-end",
        source: "send-telegram-digest",
        target: "feedly-end",
      },
      {
        id: "edge-telegram-mark",
        source: "send-telegram-digest",
        target: "mark-as-read",
      },
      {
        id: "edge-mark-end",
        source: "mark-as-read",
        target: "feedly-end",
      },
    ],
  },
  {
    id: "workflow-slack-broadcast",
    name: "Slack Channel Broadcast",
    description: "Posts an announcement to a Slack channel.",
    createdAt: "2024-02-01T13:20:00Z",
    updatedAt: "2024-03-02T18:40:00Z",
    sourceExample: "examples/slack.py",
    owner: TEMPLATE_OWNER,
    tags: ["template", "slack", "messaging"],
    nodes: [
      {
        id: "slack-start",
        type: "start",
        position: { x: 0, y: 0 },
        data: {
          label: "Start",
          type: "start",
          description: "Begin the Slack announcement workflow.",
        },
      },
      {
        id: "send-slack-message",
        type: "api",
        position: { x: 260, y: 0 },
        data: {
          label: "Send Slack message",
          type: "api",
          description:
            "Slack node posts the message to the configured channel.",
          examplePath: "examples/slack.py",
        },
      },
      {
        id: "slack-end",
        type: "end",
        position: { x: 520, y: 0 },
        data: {
          label: "Finish",
          type: "end",
          description: "Slack announcement has been delivered.",
        },
      },
    ],
    edges: [
      {
        id: "edge-slack-start-send",
        source: "slack-start",
        target: "send-slack-message",
      },
      {
        id: "edge-slack-end",
        source: "send-slack-message",
        target: "slack-end",
      },
    ],
  },
  {
    id: "workflow-rss-monitor",
    name: "RSS Feed Monitor",
    description: "Pulls unread entries from multiple RSS feeds.",
    createdAt: "2024-02-12T07:05:00Z",
    updatedAt: "2024-03-06T11:20:00Z",
    sourceExample: "examples/pull_rss_updates.py",
    owner: TEMPLATE_OWNER,
    tags: ["template", "rss", "monitoring"],
    nodes: [
      {
        id: "rss-start",
        type: "start",
        position: { x: 0, y: 0 },
        data: {
          label: "Start",
          type: "start",
          description: "Begin monitoring configured RSS feeds.",
        },
      },
      {
        id: "rss-fetch",
        type: "data",
        position: { x: 260, y: 0 },
        data: {
          label: "Fetch RSS updates",
          type: "data",
          description:
            "RSS node retrieves the latest unread entries from the feed list.",
          examplePath: "examples/pull_rss_updates.py",
        },
      },
      {
        id: "rss-end",
        type: "end",
        position: { x: 520, y: 0 },
        data: {
          label: "Finish",
          type: "end",
          description:
            "Results are ready for downstream storage or notifications.",
        },
      },
    ],
    edges: [
      {
        id: "edge-rss-start-fetch",
        source: "rss-start",
        target: "rss-fetch",
      },
      {
        id: "edge-rss-fetch-end",
        source: "rss-fetch",
        target: "rss-end",
      },
    ],
  },
  {
    id: "workflow-mongodb-session",
    name: "MongoDB Query Session",
    description: "Demonstrates MongoDB node reuse across runs.",
    createdAt: "2024-02-18T16:10:00Z",
    updatedAt: "2024-03-05T19:55:00Z",
    sourceExample: "examples/mongodb.py",
    owner: TEMPLATE_OWNER,
    tags: ["template", "database", "storage"],
    nodes: [
      {
        id: "mongodb-start",
        type: "start",
        position: { x: 0, y: 0 },
        data: {
          label: "Start",
          type: "start",
          description: "Start the MongoDB query workflow.",
        },
      },
      {
        id: "mongodb-query",
        type: "data",
        position: { x: 260, y: 0 },
        data: {
          label: "Query MongoDB collection",
          type: "data",
          description:
            "MongoDB node performs a find operation using the configured session.",
          examplePath: "examples/mongodb.py",
        },
      },
      {
        id: "mongodb-end",
        type: "end",
        position: { x: 520, y: 0 },
        data: {
          label: "Finish",
          type: "end",
          description: "Workflow ends after retrieving the MongoDB results.",
        },
      },
    ],
    edges: [
      {
        id: "edge-mongodb-start-query",
        source: "mongodb-start",
        target: "mongodb-query",
      },
      {
        id: "edge-mongodb-query-end",
        source: "mongodb-query",
        target: "mongodb-end",
      },
    ],
  },
  {
    id: "workflow-telegram-broadcast",
    name: "Python to Telegram Broadcast",
    description: "Generates a message in Python and forwards it to Telegram.",
    createdAt: "2024-02-24T21:00:00Z",
    updatedAt: "2024-03-08T09:30:00Z",
    sourceExample: "examples/telegram_example.py",
    owner: TEMPLATE_OWNER,
    tags: ["template", "telegram", "python"],
    nodes: [
      {
        id: "telegram-start",
        type: "start",
        position: { x: 0, y: 0 },
        data: {
          label: "Start",
          type: "start",
          description: "Entry point for the Telegram broadcast.",
        },
      },
      {
        id: "compose-telegram-message",
        type: "function",
        position: { x: 220, y: 0 },
        data: {
          label: "Compose message with Python",
          type: "function",
          description:
            "PythonCode node prepares the message payload for Telegram.",
          examplePath: "examples/telegram_example.py",
        },
      },
      {
        id: "send-telegram-message",
        type: "api",
        position: { x: 440, y: 0 },
        data: {
          label: "Send Telegram message",
          type: "api",
          description:
            "MessageTelegram node sends the composed message to the target chat.",
          examplePath: "examples/telegram_example.py",
        },
      },
      {
        id: "telegram-end",
        type: "end",
        position: { x: 660, y: 0 },
        data: {
          label: "Finish",
          type: "end",
          description: "Broadcast completed successfully.",
        },
      },
    ],
    edges: [
      {
        id: "edge-telegram-start-compose",
        source: "telegram-start",
        target: "compose-telegram-message",
      },
      {
        id: "edge-telegram-compose-send",
        source: "compose-telegram-message",
        target: "send-telegram-message",
      },
      {
        id: "edge-telegram-send-end",
        source: "send-telegram-message",
        target: "telegram-end",
      },
    ],
  },
];

export const NODE_TYPES = {
  trigger: {
    label: "Trigger",
    description: "Starts a workflow execution",
    color: "amber",
  },
  api: {
    label: "API",
    description: "Makes HTTP requests to external services",
    color: "blue",
  },
  function: {
    label: "Function",
    description: "Executes custom code or transformations",
    color: "purple",
  },
  data: {
    label: "Data",
    description: "Works with databases and data storage",
    color: "green",
  },
  ai: {
    label: "AI",
    description: "Uses artificial intelligence models",
    color: "indigo",
  },
  python: {
    label: "Python",
    description: "Executes custom Python code within the workflow",
    color: "orange",
  },
};
