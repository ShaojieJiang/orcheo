import {
  isRecord,
  toStringRecord,
} from "@features/workflow/lib/graph-config/utils";

export const applyDelayConfig = (
  data: Record<string, unknown>,
  nodeConfig: Record<string, unknown>,
): void => {
  const delayValue = data?.durationSeconds;
  const parsed =
    typeof delayValue === "number" ? delayValue : Number(delayValue ?? 0);
  nodeConfig.duration_seconds = Number.isFinite(parsed) ? parsed : 0;
};

export const applyMongoConfig = (
  data: Record<string, unknown>,
  nodeConfig: Record<string, unknown>,
): void => {
  if (typeof data?.database === "string" && data.database.length > 0) {
    nodeConfig.database = data.database;
  }
  if (typeof data?.collection === "string" && data.collection.length > 0) {
    nodeConfig.collection = data.collection;
  }
  nodeConfig.operation =
    typeof data?.operation === "string" && data.operation.length > 0
      ? data.operation
      : "find";
  nodeConfig.query = isRecord(data?.query) ? data.query : {};
};

export const applySlackConfig = (
  data: Record<string, unknown>,
  nodeConfig: Record<string, unknown>,
): void => {
  if (typeof data?.tool_name === "string" && data.tool_name.length > 0) {
    nodeConfig.tool_name = data.tool_name;
  }
  nodeConfig.kwargs = isRecord(data?.kwargs) ? data.kwargs : {};
};

export const applyTelegramConfig = (
  data: Record<string, unknown>,
  nodeConfig: Record<string, unknown>,
): void => {
  if (typeof data?.token === "string" && data.token.length > 0) {
    nodeConfig.token = data.token;
  }
  if (typeof data?.chat_id === "string" && data.chat_id.length > 0) {
    nodeConfig.chat_id = data.chat_id;
  }
  if (typeof data?.message === "string" && data.message.length > 0) {
    nodeConfig.message = data.message;
  }
  if (typeof data?.parse_mode === "string" && data.parse_mode.length > 0) {
    nodeConfig.parse_mode = data.parse_mode;
  }
};

export const applyCronTriggerConfig = (
  data: Record<string, unknown>,
  nodeConfig: Record<string, unknown>,
): void => {
  nodeConfig.expression =
    typeof data?.expression === "string" && data.expression.length > 0
      ? data.expression
      : "0 * * * *";
  nodeConfig.timezone =
    typeof data?.timezone === "string" && data.timezone.length > 0
      ? data.timezone
      : "UTC";
  nodeConfig.allow_overlapping = Boolean(data?.allow_overlapping);
  if (typeof data?.start_at === "string" && data.start_at.length > 0) {
    nodeConfig.start_at = data.start_at;
  }
  if (typeof data?.end_at === "string" && data.end_at.length > 0) {
    nodeConfig.end_at = data.end_at;
  }
};

export const applyManualTriggerConfig = (
  data: Record<string, unknown>,
  nodeConfig: Record<string, unknown>,
): void => {
  nodeConfig.label =
    typeof data?.label === "string" && data.label.length > 0
      ? data.label
      : "manual";
  nodeConfig.allowed_actors = Array.isArray(data?.allowed_actors)
    ? (data.allowed_actors as string[])
    : [];
  nodeConfig.require_comment = Boolean(data?.require_comment);
  nodeConfig.default_payload = isRecord(data?.default_payload)
    ? data.default_payload
    : {};
  const cooldownValue = data?.cooldown_seconds;
  const parsedCooldown =
    typeof cooldownValue === "number"
      ? cooldownValue
      : Number(cooldownValue ?? 0);
  nodeConfig.cooldown_seconds = Number.isFinite(parsedCooldown)
    ? parsedCooldown
    : 0;
};

export const applyHttpPollingTriggerConfig = (
  data: Record<string, unknown>,
  nodeConfig: Record<string, unknown>,
): void => {
  nodeConfig.url =
    typeof data?.url === "string" && data.url.length > 0 ? data.url : "";
  nodeConfig.method =
    typeof data?.method === "string" && data.method.length > 0
      ? data.method
      : "GET";
  nodeConfig.headers = isRecord(data?.headers) ? data.headers : {};
  nodeConfig.query_params = isRecord(data?.query_params)
    ? data.query_params
    : {};
  if (isRecord(data?.body)) {
    nodeConfig.body = data.body;
  }
  const intervalValue = data?.interval_seconds;
  const parsedInterval =
    typeof intervalValue === "number"
      ? intervalValue
      : Number(intervalValue ?? 0);
  nodeConfig.interval_seconds = Number.isFinite(parsedInterval)
    ? parsedInterval
    : 300;
  const timeoutValue = data?.timeout_seconds;
  const parsedTimeout =
    typeof timeoutValue === "number" ? timeoutValue : Number(timeoutValue ?? 0);
  nodeConfig.timeout_seconds = Number.isFinite(parsedTimeout)
    ? parsedTimeout
    : 30;
  nodeConfig.verify_tls = data?.verify_tls !== false;
  nodeConfig.follow_redirects = Boolean(data?.follow_redirects);
  if (
    typeof data?.deduplicate_on === "string" &&
    data.deduplicate_on.length > 0
  ) {
    nodeConfig.deduplicate_on = data.deduplicate_on;
  }
};

export const applyWebhookTriggerConfig = (
  data: Record<string, unknown>,
  nodeConfig: Record<string, unknown>,
): void => {
  const allowedMethodsRaw = Array.isArray(data?.allowed_methods)
    ? (data.allowed_methods as unknown[])
    : [];
  const allowedMethods = allowedMethodsRaw
    .filter(
      (method): method is string =>
        typeof method === "string" && method.trim().length > 0,
    )
    .map((method) => method.trim().toUpperCase());

  nodeConfig.allowed_methods =
    allowedMethods.length > 0 ? allowedMethods : ["POST"];
  nodeConfig.required_headers = toStringRecord(data?.required_headers);
  nodeConfig.required_query_params = toStringRecord(
    data?.required_query_params,
  );

  if (
    typeof data?.shared_secret_header === "string" &&
    data.shared_secret_header.length > 0
  ) {
    nodeConfig.shared_secret_header = data.shared_secret_header;
  }

  if (
    typeof data?.shared_secret === "string" &&
    data.shared_secret.length > 0
  ) {
    nodeConfig.shared_secret = data.shared_secret;
  }

  const rateLimitRaw = data?.rate_limit;
  if (isRecord(rateLimitRaw)) {
    const limitValue = rateLimitRaw.limit;
    const intervalValue = rateLimitRaw.interval_seconds;
    const parsedLimit =
      typeof limitValue === "number" ? limitValue : Number(limitValue ?? NaN);
    const parsedInterval =
      typeof intervalValue === "number"
        ? intervalValue
        : Number(intervalValue ?? NaN);

    if (Number.isFinite(parsedLimit) && Number.isFinite(parsedInterval)) {
      nodeConfig.rate_limit = {
        limit: Math.max(1, Math.trunc(parsedLimit)),
        interval_seconds: Math.max(1, Math.trunc(parsedInterval)),
      };
    }
  }
};
