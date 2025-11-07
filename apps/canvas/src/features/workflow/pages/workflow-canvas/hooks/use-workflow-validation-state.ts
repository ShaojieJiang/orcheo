import { useState } from "react";

import type { ValidationError } from "@features/workflow/components/canvas/connection-validator";

export function useWorkflowValidationState() {
  const [validationErrors, setValidationErrors] = useState<ValidationError[]>(
    [],
  );
  const [isValidating, setIsValidating] = useState(false);
  const [lastValidationRun, setLastValidationRun] = useState<string | null>(
    null,
  );

  return {
    validationErrors,
    setValidationErrors,
    isValidating,
    setIsValidating,
    lastValidationRun,
    setLastValidationRun,
  };
}
