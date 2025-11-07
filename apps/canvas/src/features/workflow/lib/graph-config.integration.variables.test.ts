import type { Edge, Node } from "@xyflow/react";
import { describe, expect, it } from "vitest";

import { buildGraphConfigFromCanvas } from "./graph-config";

describe("buildGraphConfigFromCanvas integration - variable preservation", () => {
  it("preserves template expressions for typed variables", async () => {
    const nodes: Node[] = [
      {
        id: "producer",
        type: "function",
        position: { x: 0, y: 0 },
        data: {
          label: "Producer",
          backendType: "SetVariableNode",
          variables: [{ name: "value", valueType: "number", value: 10 }],
        },
      } as Node,
      {
        id: "consumer",
        type: "function",
        position: { x: 1, y: 0 },
        data: {
          label: "Consumer",
          backendType: "SetVariableNode",
          variables: [
            {
              name: "from_template",
              valueType: "number",
              value: "{{ results.producer.value }}",
            },
          ],
        },
      } as Node,
    ];

    const edges: Edge[] = [
      {
        id: "producer-to-consumer",
        source: "producer",
        target: "consumer",
      } as Edge,
    ];

    const { config, canvasToGraph } = await buildGraphConfigFromCanvas(
      nodes,
      edges,
    );

    const consumerName = canvasToGraph["consumer"];
    expect(consumerName).toBeDefined();

    const consumerNode = config.nodes.find(
      (node) => node.name === consumerName,
    );

    expect(consumerNode).toBeDefined();
    const consumerVariables = (consumerNode?.variables ?? {}) as Record<
      string,
      unknown
    >;

    expect(consumerVariables).toMatchObject({
      from_template: "{{ results.producer.value }}",
    });
  });
});
