import type { Edge, Node } from "@xyflow/react";
import { describe, expect, it } from "vitest";

import { buildGraphConfigFromCanvas } from "./graph-config";

describe("buildGraphConfigFromCanvas integration - logic and utility nodes", () => {
  it("serializes logic and utility nodes for backend consumption", async () => {
    const nodes: Node[] = [
      {
        id: "prep-1",
        type: "utility",
        position: { x: -1, y: 0 },
        data: {
          label: "Prepare score",
          backendType: "SetVariableNode",
          variables: [
            { name: "state.user.score", valueType: "number", value: "8" },
          ],
        },
      } as Node,
      {
        id: "if-1",
        type: "logic",
        position: { x: 0, y: 0 },
        data: {
          label: "Decision",
          backendType: "IfElseNode",
          conditions: [
            {
              id: "cond-1",
              left: "{{ state.user.score }}",
              operator: "greater_than",
              right: 5,
              caseSensitive: false,
            },
            {
              id: "cond-2",
              left: true,
              operator: "is_truthy",
              right: null,
              caseSensitive: true,
            },
          ],
          conditionLogic: "and",
        },
      } as Node,
      {
        id: "set-1",
        type: "utility",
        position: { x: 1, y: 0 },
        data: {
          label: "Assign",
          backendType: "SetVariableNode",
          variables: [
            { name: "profile.name", valueType: "string", value: "Ada" },
            { name: "profile.score", valueType: "number", value: "42" },
            {
              name: "preferences",
              valueType: "object",
              value: { theme: "dark" },
            },
            {
              name: "flags",
              valueType: "array",
              value: ["beta", "ops"],
            },
            { name: "isActive", valueType: "boolean", value: "true" },
          ],
        },
      } as Node,
      {
        id: "delay-1",
        type: "utility",
        position: { x: 2, y: 0 },
        data: {
          label: "Delay",
          backendType: "DelayNode",
          durationSeconds: "2.5",
        },
      } as Node,
    ];

    const edges: Edge[] = [
      { id: "prep-to-if", source: "prep-1", target: "if-1" } as Edge,
      {
        id: "if-to-set",
        source: "if-1",
        target: "set-1",
        sourceHandle: "true",
      } as Edge,
      {
        id: "if-to-delay",
        source: "if-1",
        target: "delay-1",
        sourceHandle: "false",
      } as Edge,
      { id: "set-to-delay", source: "set-1", target: "delay-1" } as Edge,
    ];

    const { config, canvasToGraph, graphToCanvas, warnings } =
      await buildGraphConfigFromCanvas(nodes, edges);

    expect(warnings).toHaveLength(0);

    const prepName = canvasToGraph["prep-1"];
    const ifElseName = canvasToGraph["if-1"];
    const setVariableName = canvasToGraph["set-1"];
    const delayName = canvasToGraph["delay-1"];

    expect(prepName).toBeDefined();
    expect(ifElseName).toBeDefined();
    expect(graphToCanvas[ifElseName]).toBe("if-1");

    expect(config.nodes.some((node) => node.name === ifElseName)).toBe(false);
    expect(config.edge_nodes).toBeDefined();

    const ifElseNode = config.edge_nodes?.find(
      (node) => node.name === ifElseName,
    );
    expect(ifElseNode).toBeDefined();
    expect(ifElseNode).toMatchObject({
      type: "IfElseNode",
      condition_logic: "and",
    });
    expect(ifElseNode?.conditions).toEqual([
      expect.objectContaining({
        left: "{{ state.user.score }}",
        operator: "greater_than",
        right: 5,
        case_sensitive: false,
      }),
      expect.objectContaining({
        left: true,
        operator: "is_truthy",
        case_sensitive: true,
      }),
    ]);

    const setVariableNode = config.nodes.find(
      (node) => node.name === setVariableName,
    );
    expect(setVariableNode).toBeDefined();
    expect(setVariableNode?.variables).toEqual({
      "profile.name": "Ada",
      "profile.score": 42,
      preferences: { theme: "dark" },
      flags: ["beta", "ops"],
      isActive: true,
    });

    const delayNode = config.nodes.find((node) => node.name === delayName);
    expect(delayNode).toMatchObject({
      type: "DelayNode",
      duration_seconds: 2.5,
    });

    expect(config.conditional_edges).toContainEqual({
      source: prepName,
      path: ifElseName,
      mapping: { true: setVariableName, false: delayName },
    });

    expect(config.edges).toContainEqual({
      source: setVariableName,
      target: delayName,
    });
  });
});
