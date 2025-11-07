import type { CommandItem, CommandGroupMap } from "./command-palette-types";

export const filterCommandItems = (
  items: CommandItem[],
  query: string,
): CommandItem[] => {
  if (!query) {
    return items;
  }

  const lowerQuery = query.toLowerCase();
  return items.filter(
    (item) =>
      item.name.toLowerCase().includes(lowerQuery) ||
      item.description?.toLowerCase().includes(lowerQuery),
  );
};

export const groupCommandItems = (
  items: CommandItem[],
): Partial<CommandGroupMap> => {
  return items.reduce<Partial<CommandGroupMap>>((acc, item) => {
    if (!acc[item.type]) {
      acc[item.type] = [];
    }
    acc[item.type]?.push(item);
    return acc;
  }, {});
};

export const getTypeLabel = (type: CommandItem["type"]) => {
  switch (type) {
    case "workflow":
      return "Workflows";
    case "node":
      return "Nodes";
    case "action":
      return "Actions";
    case "setting":
      return "Settings";
    default:
      return type;
  }
};
