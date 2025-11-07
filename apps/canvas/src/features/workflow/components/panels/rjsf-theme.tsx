/**
 * Entry point that assembles the custom widgets/templates for RJSF.
 */

import { RegistryWidgetsType } from "@rjsf/utils";
import validator from "@rjsf/validator-ajv8";
import { basicWidgets } from "./rjsf-basic-widgets";
import { conditionWidgets } from "./rjsf-condition-widgets";
import { customTemplates } from "./rjsf-templates";

export const customWidgets = {
  ...basicWidgets,
  ...conditionWidgets,
} satisfies RegistryWidgetsType;

export { customTemplates, validator };
