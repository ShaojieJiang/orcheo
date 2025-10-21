export interface WorkflowNode {
  id: string;
  type: string;
  position: { x: number; y: number };
  data: {
    label: string;
    description?: string;
    status?: "idle" | "running" | "success" | "error";
    isDisabled?: boolean;
    credentials?: {
      id: string;
    } | null;
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

export interface WorkflowCredential {
  id: string;
  name: string;
  type: string;
  access: "private" | "shared" | "public";
  owner: string;
  createdAt: string;
  updatedAt: string;
  secrets: Record<string, string>;
  description?: string;
}

export interface ReusableSubWorkflow {
  id: string;
  name: string;
  description: string;
  category: string;
  tags: string[];
  lastUpdated: string;
  estimatedDurationMinutes: number;
  nodes: WorkflowNode[];
  edges: WorkflowEdge[];
}

export interface Workflow {
  id: string;
  name: string;
  description?: string;
  createdAt: string;
  updatedAt: string;
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
  credentials?: WorkflowCredential[];
  linkedSubworkflowIds?: string[];
}

export const SAMPLE_CREDENTIALS: WorkflowCredential[] = [
  {
    id: "cred-salesforce-oauth",
    name: "Salesforce OAuth",
    type: "oauth",
    access: "shared",
    owner: "RevOps Team",
    createdAt: "2023-09-01T08:30:00Z",
    updatedAt: "2023-10-25T15:20:00Z",
    secrets: { refreshToken: "••••••••••" },
    description: "Shared credential for Salesforce CRM access",
  },
  {
    id: "cred-sendgrid-api",
    name: "SendGrid API Key",
    type: "api_key",
    access: "private",
    owner: "Lifecycle Marketing",
    createdAt: "2023-08-12T17:45:00Z",
    updatedAt: "2023-11-04T12:10:00Z",
    secrets: { apiKey: "SG.****.****" },
    description: "Email delivery credential scoped to onboarding campaigns",
  },
  {
    id: "cred-data-warehouse",
    name: "Snowflake Warehouse",
    type: "database",
    access: "shared",
    owner: "Data Platform",
    createdAt: "2023-07-03T11:00:00Z",
    updatedAt: "2023-11-02T09:05:00Z",
    secrets: { password: "********" },
    description: "Credential for loading curated onboarding datasets",
  },
];

export const SAMPLE_SUBWORKFLOWS: ReusableSubWorkflow[] = [
  {
    id: "customer-enrichment",
    name: "Customer Enrichment",
    description:
      "Enrich a newly created customer with Clearbit data and persist the record to analytics stores.",
    category: "data",
    tags: ["customer", "enrichment", "api"],
    lastUpdated: "2023-10-18T14:05:00Z",
    estimatedDurationMinutes: 4,
    nodes: [
      {
        id: "enrich-trigger",
        type: "trigger",
        position: { x: 0, y: 0 },
        data: {
          label: "Customer Created",
          description: "Runs when a new customer is captured",
          status: "idle",
        },
      },
      {
        id: "enrich-api",
        type: "api",
        position: { x: 260, y: 0 },
        data: {
          label: "Clearbit Enrichment",
          description: "Fetch firmographics and intent data",
          status: "idle",
          credentials: { id: "cred-salesforce-oauth" },
        },
      },
      {
        id: "enrich-db",
        type: "data",
        position: { x: 520, y: 0 },
        data: {
          label: "Persist to Warehouse",
          description: "Store enriched payload in Snowflake",
          status: "idle",
          credentials: { id: "cred-data-warehouse" },
        },
      },
    ],
    edges: [
      { id: "enrich-edge-1", source: "enrich-trigger", target: "enrich-api" },
      { id: "enrich-edge-2", source: "enrich-api", target: "enrich-db" },
    ],
  },
  {
    id: "post-onboarding-survey",
    name: "Post-Onboarding Survey",
    description:
      "Send a triggered onboarding survey and collect responses for the success team dashboard.",
    category: "engagement",
    tags: ["survey", "communication", "email"],
    lastUpdated: "2023-11-03T09:40:00Z",
    estimatedDurationMinutes: 6,
    nodes: [
      {
        id: "survey-delay",
        type: "function",
        position: { x: 0, y: 0 },
        data: {
          label: "Wait 3 Days",
          description: "Ensure user has completed onboarding tasks",
          status: "idle",
        },
      },
      {
        id: "survey-email",
        type: "api",
        position: { x: 260, y: 0 },
        data: {
          label: "Send Survey Email",
          description: "Deliver NPS survey via SendGrid",
          status: "idle",
          credentials: { id: "cred-sendgrid-api" },
        },
      },
      {
        id: "survey-logging",
        type: "data",
        position: { x: 520, y: 0 },
        data: {
          label: "Log Response",
          description: "Track survey response in analytics table",
          status: "idle",
          credentials: { id: "cred-data-warehouse" },
        },
      },
    ],
    edges: [
      { id: "survey-edge-1", source: "survey-delay", target: "survey-email" },
      { id: "survey-edge-2", source: "survey-email", target: "survey-logging" },
    ],
  },
];

export const SAMPLE_WORKFLOWS: Workflow[] = [
  {
    id: "workflow-1",
    name: "Customer Onboarding",
    description: "Automates the customer onboarding process",
    createdAt: "2023-10-15T10:30:00Z",
    updatedAt: "2023-11-02T14:45:00Z",
    owner: {
      id: "user-1",
      name: "Avery Chen",
      avatar: "https://avatar.vercel.sh/avery",
    },
    tags: ["production", "customer", "automation", "template"],
    lastRun: {
      status: "success",
      timestamp: "2023-11-05T09:15:00Z",
      duration: 45.2,
    },
    credentials: SAMPLE_CREDENTIALS,
    linkedSubworkflowIds: ["customer-enrichment"],
    nodes: [
      {
        id: "node-1",
        type: "trigger",
        position: { x: 100, y: 100 },
        data: {
          label: "New Customer Webhook",
          description: "Triggered when a new customer is created in CRM",
          status: "success",
        },
      },
      {
        id: "node-2",
        type: "api",
        position: { x: 400, y: 100 },
        data: {
          label: "Fetch Customer Details",
          description: "Get full customer information from CRM API",
          status: "success",
          credentials: { id: "cred-salesforce-oauth" },
        },
      },
      {
        id: "node-3",
        type: "function",
        position: { x: 700, y: 100 },
        data: {
          label: "Format Customer Data",
          description: "Transform customer data for downstream systems",
          status: "success",
        },
      },
      {
        id: "node-4",
        type: "api",
        position: { x: 400, y: 300 },
        data: {
          label: "Create Account",
          description: "Create customer account in billing system",
          status: "success",
          credentials: { id: "cred-salesforce-oauth" },
        },
      },
      {
        id: "node-5",
        type: "api",
        position: { x: 700, y: 300 },
        data: {
          label: "Send Welcome Email",
          description: "Send personalized welcome email to customer",
          status: "success",
          credentials: { id: "cred-sendgrid-api" },
        },
      },
    ],

    edges: [
      {
        id: "edge-1-2",
        source: "node-1",
        target: "node-2",
        animated: false,
      },
      {
        id: "edge-2-3",
        source: "node-2",
        target: "node-3",
        animated: false,
      },
      {
        id: "edge-3-4",
        source: "node-3",
        target: "node-4",
        animated: false,
      },
      {
        id: "edge-4-5",
        source: "node-4",
        target: "node-5",
        animated: false,
      },
    ],
  },
  {
    id: "workflow-2",
    name: "Data Sync Pipeline",
    description: "Synchronizes data between systems",
    createdAt: "2023-09-20T08:15:00Z",
    updatedAt: "2023-11-01T11:30:00Z",
    owner: {
      id: "user-2",
      name: "Sky Patel",
      avatar: "https://avatar.vercel.sh/sky",
    },
    tags: ["data", "integration", "scheduled", "template"],
    lastRun: {
      status: "error",
      timestamp: "2023-11-05T02:00:00Z",
      duration: 134.7,
    },
    credentials: [SAMPLE_CREDENTIALS[0], SAMPLE_CREDENTIALS[2]],
    linkedSubworkflowIds: ["post-onboarding-survey"],
    nodes: [
      {
        id: "node-1",
        type: "trigger",
        position: { x: 100, y: 100 },
        data: {
          label: "Scheduled Trigger",
          description: "Runs every day at 2:00 AM",
          status: "success",
        },
      },
      {
        id: "node-2",
        type: "api",
        position: { x: 400, y: 100 },
        data: {
          label: "Extract Data",
          description: "Pull data from source system",
          status: "success",
          credentials: { id: "cred-salesforce-oauth" },
        },
      },
      {
        id: "node-3",
        type: "function",
        position: { x: 700, y: 100 },
        data: {
          label: "Transform Data",
          description: "Clean and transform data",
          status: "success",
        },
      },
      {
        id: "node-4",
        type: "data",
        position: { x: 1000, y: 100 },
        data: {
          label: "Load to Database",
          description: "Insert data into target database",
          status: "error",
          credentials: { id: "cred-data-warehouse" },
        },
      },
      {
        id: "node-5",
        type: "api",
        position: { x: 1000, y: 300 },
        data: {
          label: "Send Notification",
          description: "Notify team about sync results",
          status: "idle",
          isDisabled: true,
          credentials: { id: "cred-sendgrid-api" },
        },
      },
    ],

    edges: [
      {
        id: "edge-1-2",
        source: "node-1",
        target: "node-2",
        animated: false,
      },
      {
        id: "edge-2-3",
        source: "node-2",
        target: "node-3",
        animated: false,
      },
      {
        id: "edge-3-4",
        source: "node-3",
        target: "node-4",
        animated: false,
      },
      {
        id: "edge-4-5",
        source: "node-4",
        target: "node-5",
        animated: false,
      },
    ],
  },
  {
    id: "workflow-3",
    name: "AI Content Generator",
    description: "Generates and publishes content using AI",
    createdAt: "2023-10-05T15:45:00Z",
    updatedAt: "2023-11-03T09:20:00Z",
    owner: {
      id: "user-1",
      name: "Avery Chen",
      avatar: "https://avatar.vercel.sh/avery",
    },
    tags: ["ai", "content", "automation", "template"],
    lastRun: {
      status: "running",
      timestamp: "2023-11-05T10:30:00Z",
      duration: 67.3,
    },
    nodes: [
      {
        id: "node-1",
        type: "trigger",
        position: { x: 100, y: 100 },
        data: {
          label: "Content Request",
          description: "Triggered when content is requested",
          status: "success",
        },
      },
      {
        id: "node-2",
        type: "function",
        position: { x: 400, y: 100 },
        data: {
          label: "Prepare Prompt",
          description: "Format content request into AI prompt",
          status: "success",
        },
      },
      {
        id: "node-3",
        type: "ai",
        position: { x: 700, y: 100 },
        data: {
          label: "Generate Content",
          description: "Use AI model to generate content",
          status: "running",
        },
      },
      {
        id: "node-4",
        type: "function",
        position: { x: 1000, y: 100 },
        data: {
          label: "Format Content",
          description: "Format and structure the generated content",
          status: "idle",
        },
      },
      {
        id: "node-5",
        type: "api",
        position: { x: 1000, y: 300 },
        data: {
          label: "Publish Content",
          description: "Publish to CMS or social media",
          status: "idle",
        },
      },
    ],

    edges: [
      {
        id: "edge-1-2",
        source: "node-1",
        target: "node-2",
        animated: false,
      },
      {
        id: "edge-2-3",
        source: "node-2",
        target: "node-3",
        animated: true,
      },
      {
        id: "edge-3-4",
        source: "node-3",
        target: "node-4",
        animated: false,
      },
      {
        id: "edge-4-5",
        source: "node-4",
        target: "node-5",
        animated: false,
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
};
