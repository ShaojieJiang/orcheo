import { Workflow } from "../workflow-types";
import { TEMPLATE_OWNER } from "./template-owner";

export const RSS_MONITOR_WORKFLOW: Workflow = {
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
};
