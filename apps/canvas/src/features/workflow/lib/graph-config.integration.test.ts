import type { Edge, Node } from "@xyflow/react";
import { describe, expect, it } from "vitest";

import { buildGraphConfigFromCanvas } from "./graph-config";

describe("buildGraphConfigFromCanvas integration", () => {
  it("serializes logic and utility nodes for backend consumption", async () => {
    const nodes: Node[] = [
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
      {
        id: "set-to-delay",
        source: "set-1",
        target: "delay-1",
      } as Edge,
    ];

    const { config, canvasToGraph, graphToCanvas, warnings } =
      await buildGraphConfigFromCanvas(nodes, edges);

    expect(warnings).toHaveLength(0);

    const ifElseName = canvasToGraph["if-1"];
    const setVariableName = canvasToGraph["set-1"];
    const delayName = canvasToGraph["delay-1"];

    expect(ifElseName).toBeDefined();
    expect(graphToCanvas[ifElseName]).toBe("if-1");

    const ifElseNode = config.nodes.find((node) => node.name === ifElseName);
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
      source: ifElseName,
      path: `results.${ifElseName}.branch`,
      mapping: {
        true: setVariableName,
        false: delayName,
      },
    });

    expect(config.edges).toContainEqual({
      source: setVariableName,
      target: delayName,
    });
  });

  it("filters out canvas start and end nodes from serialization", async () => {
    const nodes: Node[] = [
      {
        id: "start-node",
        type: "start",
        position: { x: 0, y: 0 },
        data: {
          label: "Workflow Start",
          type: "start",
        },
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
        data: {
          label: "Workflow End",
          type: "end",
        },
      } as Node,
    ];

    const edges: Edge[] = [
      {
        id: "start-to-set",
        source: "start-node",
        target: "set-var",
      } as Edge,
      {
        id: "set-to-end",
        source: "set-var",
        target: "end-node",
      } as Edge,
    ];

    const { config, canvasToGraph, warnings } =
      await buildGraphConfigFromCanvas(nodes, edges);

    expect(warnings).toHaveLength(0);

    // Canvas start/end nodes should NOT be in the mapping
    expect(canvasToGraph["start-node"]).toBeUndefined();
    expect(canvasToGraph["end-node"]).toBeUndefined();

    // Only the SetVariable node should be serialized
    expect(canvasToGraph["set-var"]).toBeDefined();
    const setVarName = canvasToGraph["set-var"];

    // Graph should have: START (hardcoded), set-variable, END (hardcoded)
    expect(config.nodes).toHaveLength(3);
    expect(config.nodes[0]).toMatchObject({
      name: "START",
      type: "START",
    });
    expect(config.nodes[1]).toMatchObject({
      name: setVarName,
      type: "SetVariableNode",
    });
    expect(config.nodes[2]).toMatchObject({
      name: "END",
      type: "END",
    });

    // Edges should connect START -> set-variable -> END
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
