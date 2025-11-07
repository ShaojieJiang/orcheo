import { useEffect, useMemo, useState } from "react";
import type { WorkflowExecution } from "./workflow-execution-history.types";

export const useSelectedExecution = (
  executions: WorkflowExecution[],
  defaultSelectedExecution?: WorkflowExecution,
) => {
  const [selectedExecution, setSelectedExecution] =
    useState<WorkflowExecution | null>(
      defaultSelectedExecution ||
        (executions.length > 0 ? executions[0] : null),
    );

  useEffect(() => {
    setSelectedExecution((current) => {
      if (executions.length === 0) {
        return null;
      }

      if (current) {
        const currentMatch = executions.find(
          (execution) => execution.id === current.id,
        );

        if (currentMatch) {
          return currentMatch;
        }
      }

      if (defaultSelectedExecution) {
        const defaultMatch = executions.find(
          (execution) => execution.id === defaultSelectedExecution.id,
        );

        if (defaultMatch) {
          return defaultMatch;
        }
      }

      return executions[0];
    });
  }, [executions, defaultSelectedExecution]);

  return { selectedExecution, setSelectedExecution };
};

export const useExecutionPagination = (
  executions: WorkflowExecution[],
  initialPageSize = 20,
) => {
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(initialPageSize);

  const totalExecutions = executions.length;
  const pageCount =
    totalExecutions === 0 ? 0 : Math.ceil(totalExecutions / pageSize);

  const currentPageExecutions = useMemo(() => {
    const startIndex = page * pageSize;
    return executions.slice(startIndex, startIndex + pageSize);
  }, [executions, page, pageSize]);

  const startOffset = page * pageSize;
  const endOffset = Math.min(totalExecutions, startOffset + pageSize);
  const isFirstPage = page === 0 || pageCount === 0;
  const isLastPage = pageCount === 0 || page === pageCount - 1;

  useEffect(() => {
    if (pageCount === 0) {
      if (page !== 0) {
        setPage(0);
      }
      return;
    }

    if (page > pageCount - 1) {
      setPage(pageCount - 1);
    }
  }, [page, pageCount]);

  const changePageSize = (size: number) => {
    setPage(0);

    if (size !== pageSize) {
      setPageSize(size);
    }
  };

  const goToPreviousPage = () => {
    if (!isFirstPage) {
      setPage((prev) => Math.max(prev - 1, 0));
    }
  };

  const goToNextPage = () => {
    if (!isLastPage) {
      setPage((prev) => prev + 1);
    }
  };

  return {
    page,
    setPage,
    pageSize,
    pageCount,
    totalExecutions,
    currentPageExecutions,
    startOffset,
    endOffset,
    isFirstPage,
    isLastPage,
    changePageSize,
    goToPreviousPage,
    goToNextPage,
  };
};
