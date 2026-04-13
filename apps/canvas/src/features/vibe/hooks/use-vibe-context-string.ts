import { useMemo } from "react";
import type { PageContext } from "@/hooks/use-page-context";

const TAB_LABELS: Record<string, string> = {
  workflow: "Workflow",
  trace: "Trace",
  readiness: "Readiness",
  settings: "Settings",
};

export function useVibeContextString(ctx: PageContext): string {
  return useMemo(() => {
    const parts: string[] = [];

    switch (ctx.page) {
      case "gallery":
        parts.push("The user is on **Canvas Gallery**.");
        break;

      case "canvas": {
        if (ctx.workflowId) {
          const label = ctx.workflowName
            ? `\`${ctx.workflowId}\` (${ctx.workflowName})`
            : `\`${ctx.workflowId}\``;
          parts.push(`The user is on workflow ${label}.`);
        } else {
          parts.push("The user is creating a new workflow.");
        }
        if (ctx.activeTab && ctx.activeTab !== "workflow") {
          const tabLabel = TAB_LABELS[ctx.activeTab] ?? ctx.activeTab;
          parts.push(`Viewing the **${tabLabel}** tab.`);
        }
        break;
      }

      case "execution":
        if (ctx.executionId) {
          parts.push(
            `The user is viewing execution details for \`${ctx.executionId}\`.`,
          );
        } else {
          parts.push("The user is viewing execution details.");
        }
        break;

      case "settings":
        parts.push("The user is on **Settings**.");
        break;

      case "profile":
        parts.push("The user is on **Profile**.");
        break;

      case "help":
        parts.push("The user is on **Help & Support**.");
        break;

      default:
        parts.push("The user is on Orcheo Canvas.");
        break;
    }

    if (ctx.vaultOpen) {
      parts.push("\n**Credential Vault** is currently open.");
    }

    return parts.join(" ");
  }, [
    ctx.page,
    ctx.workflowId,
    ctx.workflowName,
    ctx.activeTab,
    ctx.executionId,
    ctx.vaultOpen,
  ]);
}
