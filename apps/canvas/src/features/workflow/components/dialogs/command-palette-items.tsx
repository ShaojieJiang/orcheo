import {
  Folder,
  FileText,
  Code,
  Settings,
  Zap,
  Database,
  Sparkles,
} from "lucide-react";
import { type CommandItem } from "./command-palette-types";

export const COMMAND_ITEMS: CommandItem[] = [
  {
    id: "workflow-1",
    name: "Customer Onboarding",
    description: "Automated customer onboarding workflow",
    icon: <Folder className="h-4 w-4" />,
    type: "workflow",
    href: "/workflow-canvas",
  },
  {
    id: "workflow-2",
    name: "Email Campaign",
    description: "Marketing email sequence",
    icon: <Folder className="h-4 w-4" />,
    type: "workflow",
    href: "/workflow-canvas",
  },
  {
    id: "node-1",
    name: "HTTP Request",
    description: "Make HTTP requests to external APIs",
    icon: <Code className="h-4 w-4" />,
    type: "node",
  },
  {
    id: "node-2",
    name: "Transform Data",
    description: "Process and transform data",
    icon: <Code className="h-4 w-4" />,
    type: "node",
  },
  {
    id: "node-3",
    name: "Database Query",
    description: "Execute SQL queries",
    icon: <Database className="h-4 w-4" />,
    type: "node",
  },
  {
    id: "node-4",
    name: "AI Text Generation",
    description: "Generate text using AI models",
    icon: <Sparkles className="h-4 w-4" />,
    type: "node",
  },
  {
    id: "action-1",
    name: "Create New Workflow",
    icon: <FileText className="h-4 w-4" />,
    type: "action",
  },
  {
    id: "action-2",
    name: "Run Current Workflow",
    icon: <Zap className="h-4 w-4" />,
    type: "action",
    shortcut: "⌘R",
  },
  {
    id: "setting-1",
    name: "User Settings",
    icon: <Settings className="h-4 w-4" />,
    type: "setting",
    href: "/settings",
  },
];
