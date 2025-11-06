/**
 * Shared condition operator metadata used across schemas and UI widgets.
 */
export type ConditionOperatorOption = {
  value: string;
  label: string;
  description?: string;
};

export type ConditionOperatorGroup = {
  key: string;
  label: string;
  options: ConditionOperatorOption[];
};

export const conditionOperatorGroups: ConditionOperatorGroup[] = [
  {
    key: "any",
    label: "Any",
    options: [
      {
        value: "equals",
        label: "Equals (=)",
        description: "Left equals right",
      },
      {
        value: "not_equals",
        label: "Not Equals (≠)",
        description: "Left does not equal right",
      },
    ],
  },
  {
    key: "number",
    label: "Number",
    options: [
      {
        value: "greater_than",
        label: "Greater Than (>)",
        description: "Left is greater than right",
      },
      {
        value: "greater_than_or_equal",
        label: "Greater Than or Equal (≥)",
        description: "Left is greater than or equal to right",
      },
      {
        value: "less_than",
        label: "Less Than (<)",
        description: "Left is less than right",
      },
      {
        value: "less_than_or_equal",
        label: "Less Than or Equal (≤)",
        description: "Left is less than or equal to right",
      },
    ],
  },
  {
    key: "string",
    label: "String",
    options: [
      {
        value: "contains",
        label: "Contains",
        description: "Left contains right",
      },
      {
        value: "not_contains",
        label: "Does Not Contain",
        description: "Left does not contain right",
      },
    ],
  },
  {
    key: "collection",
    label: "Collection",
    options: [
      {
        value: "in",
        label: "In",
        description: "Left is a member of right",
      },
      {
        value: "not_in",
        label: "Not In",
        description: "Left is not a member of right",
      },
    ],
  },
  {
    key: "boolean",
    label: "Boolean",
    options: [
      {
        value: "is_truthy",
        label: "Is Truthy",
        description: "Left is evaluated as truthy",
      },
      {
        value: "is_falsy",
        label: "Is Falsy",
        description: "Left is evaluated as falsy",
      },
    ],
  },
];

export const comparisonOperatorEnum = conditionOperatorGroups.flatMap((group) =>
  group.options.map((option) => option.value),
);
