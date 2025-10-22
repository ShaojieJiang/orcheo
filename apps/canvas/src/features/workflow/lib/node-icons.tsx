import React from "react";
import {
  AlertCircle,
  BarChart,
  Briefcase,
  Calendar,
  Clock,
  Code,
  Database,
  Filter,
  FileText,
  GitBranch,
  Globe,
  LineChart,
  Mail,
  MessageSquare,
  PieChart,
  Play,
  RotateCw,
  Settings,
  Sparkles,
  Square,
  Zap,
} from "lucide-react";

type IconFactory = () => React.ReactNode;

const ICON_CLASSES = "h-4 w-4";

const NODE_ICON_FACTORIES = {
  webhook: () => <Globe className={`${ICON_CLASSES} text-amber-500`} />,
  schedule: () => <Clock className={`${ICON_CLASSES} text-amber-500`} />,
  calendar: () => <Calendar className={`${ICON_CLASSES} text-amber-500`} />,
  chatTrigger: () => (
    <MessageSquare className={`${ICON_CLASSES} text-amber-500`} />
  ),
  http: () => <Globe className={`${ICON_CLASSES} text-blue-500`} />,
  email: () => <Mail className={`${ICON_CLASSES} text-blue-500`} />,
  slack: () => <MessageSquare className={`${ICON_CLASSES} text-blue-500`} />,
  condition: () => <GitBranch className={`${ICON_CLASSES} text-purple-500`} />,
  loop: () => <RotateCw className={`${ICON_CLASSES} text-purple-500`} />,
  switch: () => <Filter className={`${ICON_CLASSES} text-purple-500`} />,
  delay: () => <Clock className={`${ICON_CLASSES} text-purple-500`} />,
  errorHandler: () => (
    <AlertCircle className={`${ICON_CLASSES} text-purple-500`} />
  ),
  database: () => <Database className={`${ICON_CLASSES} text-green-500`} />,
  transform: () => <Code className={`${ICON_CLASSES} text-green-500`} />,
  filterData: () => <Filter className={`${ICON_CLASSES} text-green-500`} />,
  aggregate: () => <BarChart className={`${ICON_CLASSES} text-green-500`} />,
  python: () => <Code className={`${ICON_CLASSES} text-orange-500`} />,
  code: () => <Code className={`${ICON_CLASSES} text-purple-500`} />,
  textGeneration: () => (
    <FileText className={`${ICON_CLASSES} text-indigo-500`} />
  ),
  chatCompletion: () => (
    <MessageSquare className={`${ICON_CLASSES} text-indigo-500`} />
  ),
  classification: () => (
    <Sparkles className={`${ICON_CLASSES} text-indigo-500`} />
  ),
  imageGeneration: () => (
    <Sparkles className={`${ICON_CLASSES} text-indigo-500`} />
  ),
  barChart: () => <BarChart className={`${ICON_CLASSES} text-orange-500`} />,
  lineChart: () => <LineChart className={`${ICON_CLASSES} text-orange-500`} />,
  pieChart: () => <PieChart className={`${ICON_CLASSES} text-orange-500`} />,
  defaultTrigger: () => <Zap className={`${ICON_CLASSES} text-amber-500`} />,
  defaultApi: () => <Globe className={`${ICON_CLASSES} text-blue-500`} />,
  defaultFunction: () => (
    <Settings className={`${ICON_CLASSES} text-purple-500`} />
  ),
  defaultData: () => <Database className={`${ICON_CLASSES} text-green-500`} />,
  defaultAi: () => <Sparkles className={`${ICON_CLASSES} text-indigo-500`} />,
  defaultVisualization: () => (
    <BarChart className={`${ICON_CLASSES} text-orange-500`} />
  ),
  group: () => <Briefcase className={`${ICON_CLASSES} text-blue-500`} />,
  start: () => <Play className="h-4 w-4 text-emerald-600" />,
  end: () => <Square className="h-4 w-4 text-rose-600" />,
} satisfies Record<string, IconFactory>;

export type NodeIconKey = keyof typeof NODE_ICON_FACTORIES;

const DEFAULT_TYPE_ICON_KEY: Record<string, NodeIconKey> = {
  trigger: "defaultTrigger",
  api: "defaultApi",
  function: "defaultFunction",
  data: "defaultData",
  ai: "defaultAi",
  visualization: "defaultVisualization",
  python: "python",
  chatTrigger: "chatTrigger",
  group: "group",
  start: "start",
  end: "end",
};

const LABEL_ICON_MATCHERS: Array<[RegExp, NodeIconKey]> = [
  [/webhook/i, "webhook"],
  [/(schedule|cron)/i, "schedule"],
  [/calendar/i, "calendar"],
  [/(chat trigger|chat)/i, "chatTrigger"],
  [/http|api/i, "http"],
  [/email/i, "email"],
  [/slack/i, "slack"],
  [/condition/i, "condition"],
  [/(loop|iterate)/i, "loop"],
  [/switch/i, "switch"],
  [/(delay|wait)/i, "delay"],
  [/error/i, "errorHandler"],
  [/database|sql/i, "database"],
  [/transform/i, "transform"],
  [/python/i, "python"],
  [/filter/i, "filterData"],
  [/(aggregate|group)/i, "aggregate"],
  [/(code|script)/i, "code"],
  [/(text generation|text)/i, "textGeneration"],
  [/(chat completion|chat response)/i, "chatCompletion"],
  [/classification/i, "classification"],
  [/image/i, "imageGeneration"],
  [/bar chart/i, "barChart"],
  [/line chart/i, "lineChart"],
  [/pie chart/i, "pieChart"],
];

export const isNodeIconKey = (value: string): value is NodeIconKey => {
  return value in NODE_ICON_FACTORIES;
};

export const getNodeIcon = (
  key?: string | null,
): React.ReactNode | undefined => {
  if (!key) {
    return undefined;
  }

  const iconKey = isNodeIconKey(key) ? key : undefined;
  const factory = iconKey ? NODE_ICON_FACTORIES[iconKey] : undefined;
  return factory ? factory() : undefined;
};

export const inferNodeIconKey = (options: {
  iconKey?: string;
  label?: string;
  type?: string;
}): NodeIconKey | undefined => {
  const { iconKey, label, type } = options;

  if (iconKey && isNodeIconKey(iconKey)) {
    return iconKey;
  }

  if (label) {
    const match = LABEL_ICON_MATCHERS.find(([regex]) => regex.test(label));
    if (match) {
      return match[1];
    }
  }

  if (type) {
    const inferred = DEFAULT_TYPE_ICON_KEY[type];
    if (inferred && isNodeIconKey(inferred)) {
      return inferred;
    }
  }

  return undefined;
};
