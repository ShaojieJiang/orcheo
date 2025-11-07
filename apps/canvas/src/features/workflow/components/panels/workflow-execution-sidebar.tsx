import { Button } from "@/design-system/ui/button";
import { Badge } from "@/design-system/ui/badge";
import { ScrollArea } from "@/design-system/ui/scroll-area";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/design-system/ui/select";
import {
  Pagination,
  PaginationContent,
  PaginationItem,
  PaginationLink,
  PaginationNext,
  PaginationPrevious,
} from "@/design-system/ui/pagination";
import { Clock, Filter, MessageSquare, RefreshCw } from "lucide-react";
import { cn } from "@/lib/utils";
import {
  formatDuration,
  formatExecutionDate,
  getStatusBadgeClass,
} from "./workflow-execution-history.utils";
import type { WorkflowExecution } from "./workflow-execution-history.types";

interface WorkflowExecutionSidebarProps {
  totalExecutions: number;
  currentPageExecutions: WorkflowExecution[];
  selectedExecutionId?: string | null;
  page: number;
  pageCount: number;
  pageSize: number;
  pageSizeOptions: number[];
  isFirstPage: boolean;
  isLastPage: boolean;
  startOffset: number;
  endOffset: number;
  onSelectExecution: (execution: WorkflowExecution) => void;
  onPreviousPage: () => void;
  onNextPage: () => void;
  onPageSizeChange: (size: number) => void;
  onRefresh?: () => void;
  onViewDetails?: (execution: WorkflowExecution) => void;
}

const WorkflowExecutionSidebar = ({
  totalExecutions,
  currentPageExecutions,
  selectedExecutionId,
  page,
  pageCount,
  pageSize,
  pageSizeOptions,
  isFirstPage,
  isLastPage,
  startOffset,
  endOffset,
  onSelectExecution,
  onPreviousPage,
  onNextPage,
  onPageSizeChange,
  onRefresh,
  onViewDetails,
}: WorkflowExecutionSidebarProps) => (
  <div className="flex h-full flex-col">
    <div className="space-y-2 border-b border-border p-2">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold">Executions</h2>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="icon"
            onClick={onRefresh}
            title="Refresh"
          >
            <RefreshCw className="h-4 w-4" />
          </Button>
          <Button variant="outline" size="icon" title="Filter">
            <Filter className="h-4 w-4" />
          </Button>
        </div>
      </div>
      <div className="flex items-center justify-between text-xs text-muted-foreground">
        <span>
          {totalExecutions === 1
            ? "1 execution"
            : `${totalExecutions} executions`}
        </span>
        <div className="flex items-center gap-2">
          <span>Rows</span>
          <Select
            value={String(pageSize)}
            onValueChange={(value) => onPageSizeChange(Number(value))}
          >
            <SelectTrigger className="h-8 w-[80px]">
              <SelectValue aria-label="Rows per page" />
            </SelectTrigger>
            <SelectContent>
              {pageSizeOptions.map((option) => (
                <SelectItem key={option} value={String(option)}>
                  {option}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>
    </div>
    <ScrollArea className="flex-1">
      <div className="p-2">
        {totalExecutions === 0 ? (
          <div className="py-8 text-center text-muted-foreground">
            No executions found
          </div>
        ) : (
          currentPageExecutions.map((execution) => (
            <div
              key={execution.id}
              className={cn(
                "mb-2 cursor-pointer rounded-lg border p-4 transition-colors",
                selectedExecutionId === execution.id
                  ? "border-primary bg-primary/5"
                  : "border-border hover:border-primary/50",
              )}
              onClick={() => onSelectExecution(execution)}
            >
              <div className="mb-2 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Badge className={cn(getStatusBadgeClass(execution.status))}>
                    {execution.status.charAt(0).toUpperCase() +
                      execution.status.slice(1)}
                  </Badge>
                  <span className="font-medium">Run #{execution.runId}</span>
                </div>
                <span className="text-sm text-muted-foreground">
                  {formatExecutionDate(execution.startTime)}
                </span>
              </div>
              <div className="flex items-center justify-between text-sm">
                <div className="flex items-center gap-4">
                  <div className="flex items-center gap-1">
                    <Clock className="h-4 w-4 text-muted-foreground" />
                    <span>{formatDuration(execution.duration)}</span>
                  </div>
                  <div className="flex items-center gap-1">
                    <MessageSquare className="h-4 w-4 text-muted-foreground" />
                    <span>
                      {execution.issues}{" "}
                      {execution.issues === 1 ? "issue" : "issues"}
                    </span>
                  </div>
                </div>
                <div className="flex gap-2">
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-7 px-2"
                    onClick={(e) => {
                      e.stopPropagation();
                      onViewDetails?.(execution);
                    }}
                  >
                    View Details
                  </Button>
                </div>
              </div>
            </div>
          ))
        )}
      </div>
    </ScrollArea>
    <div className="flex flex-col gap-2 border-t border-border p-2 text-sm md:flex-row md:items-center md:justify-between">
      <span className="text-xs text-muted-foreground md:text-sm">
        {totalExecutions === 0
          ? "No executions to display"
          : `Showing ${startOffset + 1}-${endOffset} of ${totalExecutions}`}
      </span>
      <Pagination className="mx-0 justify-center md:justify-end">
        <PaginationContent>
          <PaginationItem>
            <PaginationPrevious
              href="#"
              onClick={(event) => {
                event.preventDefault();
                onPreviousPage();
              }}
              className={cn(isFirstPage && "pointer-events-none opacity-50")}
            />
          </PaginationItem>
          <PaginationItem>
            <PaginationLink
              href="#"
              isActive
              onClick={(event) => event.preventDefault()}
              className="px-3"
            >
              {`Page ${pageCount === 0 ? 0 : page + 1} of ${Math.max(
                pageCount,
                1,
              )}`}
            </PaginationLink>
          </PaginationItem>
          <PaginationItem>
            <PaginationNext
              href="#"
              onClick={(event) => {
                event.preventDefault();
                onNextPage();
              }}
              className={cn(isLastPage && "pointer-events-none opacity-50")}
            />
          </PaginationItem>
        </PaginationContent>
      </Pagination>
    </div>
  </div>
);

export default WorkflowExecutionSidebar;
