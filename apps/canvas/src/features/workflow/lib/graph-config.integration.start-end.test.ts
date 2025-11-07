import type { Edge, Node } from "@xyflow/react";
import { describe, expect, it } from "vitest";

import { buildGraphConfigFromCanvas } from "./graph-config";

describe("buildGraphConfigFromCanvas integration - start/end filtering", () => {
  it("filters out canvas start and end nodes from serialization", async () => {
    const nodes: Node[] = [
      {
        id: "start-node",
        type: "start",
        position: { x: 0, y: 0 },
        data: { label: "Workflow Start", type: "start" },
      } as Node,
      {
        id: "set-var",
        type: "function",
        position: { x: 100, y: 0 },
        data: {
          label: "Set Variable",
          backendType: "SetVariableNode",
          variables: [
            { name: "my_variable", valueType: "string", value: "sample" },
            { name: "num", valueType: "number", value: 2 },
          ],
        },
      } as Node,
      {
        id: "end-node",
        type: "end",
        position: { x: 200, y: 0 },
        data: { label: "Workflow End", type: "end" },
      } as Node,
    ];

    const edges: Edge[] = [
      { id: "start-to-set", source: "start-node", target: "set-var" } as Edge,
      { id: "set-to-end", source: "set-var", target: "end-node" } as Edge,
    ];

    const { config, canvasToGraph, warnings } =
      await buildGraphConfigFromCanvas(nodes, edges);

    expect(warnings).toHaveLength(0);
    expect(canvasToGraph["start-node"]).toBeUndefined();
    expect(canvasToGraph["end-node"]).toBeUndefined();

    expect(canvasToGraph["set-var"]).toBeDefined();
    const setVarName = canvasToGraph["set-var"];

    expect(config.nodes).toHaveLength(3);
    expect(config.nodes[0]).toMatchObject({ name: "START", type: "START" });
    expect(config.nodes[1]).toMatchObject({
      name: setVarName,
      type: "SetVariableNode",
    });
    expect(config.nodes[2]).toMatchObject({ name: "END", type: "END" });

    expect(config.edges).toContainEqual({
      source: "START",
      target: setVarName,
    });
    expect(config.edges).toContainEqual({
      source: setVarName,
      target: "END",
    });
  });
});
