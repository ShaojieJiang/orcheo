import { createElement, type ReactNode } from "react";
import type { WorkflowCredentialReadinessResponse } from "./workflow-storage.types";
import { toast } from "@/hooks/use-toast";

export const CREDENTIAL_VAULT_REMINDER =
  "Add any required credentials to the vault before running this workflow.";

const formatCredentialNames = (names: string[]): string => names.join(", ");

const escapeRegExp = (value: string): string =>
  value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

const highlightCredentialNames = (
  description: string,
  highlightedCredentialNames: string[],
): ReactNode => {
  if (highlightedCredentialNames.length === 0) {
    return description;
  }

  const uniqueNames = [...new Set(highlightedCredentialNames)].sort(
    (left, right) => right.length - left.length,
  );
  const pattern = new RegExp(
    `(${uniqueNames.map(escapeRegExp).join("|")})`,
    "g",
  );
  const parts = description.split(pattern);

  return parts.map((part, index) =>
    uniqueNames.includes(part)
      ? createElement("strong", { key: `${part}-${index}` }, part)
      : part,
  );
};

const PLACEHOLDER_PATTERN = /\[\[([^[\]]+)\]\]/g;

const addPlaceholderMatches = (
  value: string,
  placeholders: Set<string>,
): void => {
  for (const match of value.matchAll(PLACEHOLDER_PATTERN)) {
    const rawBody = match[1]?.trim();
    if (!rawBody) {
      continue;
    }
    const identifier = rawBody.split("#", 1)[0]?.trim();
    if (!identifier) {
      continue;
    }
    placeholders.add(identifier);
  }
};

export const collectCredentialPlaceholderNames = (value: unknown): string[] => {
  const placeholders = new Set<string>();

  const walk = (candidate: unknown): void => {
    if (typeof candidate === "string") {
      addPlaceholderMatches(candidate, placeholders);
      return;
    }
    if (Array.isArray(candidate)) {
      candidate.forEach(walk);
      return;
    }
    if (candidate && typeof candidate === "object") {
      Object.values(candidate).forEach(walk);
    }
  };

  walk(value);
  return [...placeholders].sort((left, right) => left.localeCompare(right));
};

export const describeRequiredCredentialPlaceholders = (
  placeholders: string[],
): string => {
  if (placeholders.length === 0) {
    return CREDENTIAL_VAULT_REMINDER;
  }
  return `Add these vault credentials before running this workflow: ${formatCredentialNames(
    placeholders,
  )}.`;
};

export const describeCredentialVaultReadiness = (
  readiness: WorkflowCredentialReadinessResponse | null | undefined,
): string | null => {
  if (!readiness) {
    return CREDENTIAL_VAULT_REMINDER;
  }
  const available = readiness.available_credentials ?? [];
  if (readiness.missing_credentials.length > 0) {
    const missingMessage = `Add missing vault credentials before running this workflow: ${formatCredentialNames(
      readiness.missing_credentials,
    )}.`;
    if (available.length === 0) {
      return missingMessage;
    }
    return `${missingMessage} Already available in the vault: ${formatCredentialNames(
      available,
    )}.`;
  }
  return null;
};

export const showCredentialReminderToast = ({
  title,
  description,
  highlightedCredentialNames = [],
}: {
  title: string;
  description: string;
  highlightedCredentialNames?: string[];
}): (() => void) => {
  const instance = toast({
    title,
    description: highlightCredentialNames(
      description,
      highlightedCredentialNames,
    ),
  });

  return () => {
    instance.dismiss();
  };
};
