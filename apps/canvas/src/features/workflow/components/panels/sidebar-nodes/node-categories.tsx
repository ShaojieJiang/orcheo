import type { NodeCategory } from "../sidebar-panel.types";

import { actionCategory } from "./actions";
import { aiCategory } from "./ai";
import { dataCategory } from "./data";
import { logicCategory } from "./logic";
import { specialCategory } from "./special";
import { triggerCategory } from "./triggers";
import { visualizationCategory } from "./visualization";

export const nodeCategories: NodeCategory[] = [
  specialCategory,
  triggerCategory,
  actionCategory,
  logicCategory,
  dataCategory,
  aiCategory,
  visualizationCategory,
];
