import { useParams } from "react-router-dom";
import { ArrowLeftIcon, RotateCwIcon } from "lucide-react";
import { Link } from "react-router-dom";
import { Button } from "@/design-system/ui/button";
import { Badge } from "@/design-system/ui/badge";
import WorkflowExecutionHistory from "@features/workflow/components/panels/workflow-execution-history";

export default function WorkflowExecutionDetails() {
  const { executionId = "1" } = useParams();
  // Mock execution data
  const execution = {
    id: executionId,
    runId: executionId,
    workflowName: "Customer Onboarding Workflow",
    status: "success",
    startTime: new Date().toISOString(),
    endTime: new Date(Date.now() + 45000).toISOString(),
    duration: 45000, // 45 seconds
    triggeredBy: {
      name: "Avery Chen",
      avatar: "https://avatar.vercel.sh/avery",
    },
    nodes: [
      {
        id: "node-1",
        type: "webhook",
        name: "New Customer Webhook",
        position: { x: 100, y: 100 },
        status: "success",
      },
      {
        id: "node-2",
        type: "http",
        name: "Fetch Customer Details",
        position: { x: 400, y: 100 },
        status: "success",
        details: {
          method: "GET",
          url: "https://api.example.com/customers/123",
          items: 1,
        },
      },
      {
        id: "node-3",
        type: "function",
        name: "Format Customer Data",
        position: { x: 700, y: 100 },
        status: "success",
      },
      {
        id: "node-4",
        type: "api",
        name: "Create Account",
        position: { x: 400, y: 250 },
        status: "success",
      },
      {
        id: "node-5",
        type: "api",
        name: "Send Welcome Email",
        position: { x: 700, y: 250 },
        status: "success",
        details: {
          message: "Welcome to our platform!",
        },
      },
    ],

    edges: [
      { id: "edge-1", source: "node-1", target: "node-2" },
      { id: "edge-2", source: "node-2", target: "node-3" },
      { id: "edge-3", source: "node-3", target: "node-4" },
      { id: "edge-4", source: "node-4", target: "node-5" },
    ],

    logs: [
      {
        timestamp: "10:23:15",
        level: "INFO",
        message: "Workflow execution started",
      },
      {
        timestamp: "10:23:16",
        level: "DEBUG",
        message: 'Executing node "New Customer Webhook"',
      },
      {
        timestamp: "10:23:17",
        level: "INFO",
        message: 'Node "New Customer Webhook" completed successfully',
      },
      {
        timestamp: "10:23:18",
        level: "DEBUG",
        message: 'Executing node "Fetch Customer Details"',
      },
      {
        timestamp: "10:23:20",
        level: "INFO",
        message: 'Node "Fetch Customer Details" completed successfully',
      },
      {
        timestamp: "10:23:21",
        level: "DEBUG",
        message: 'Executing node "Format Customer Data"',
      },
      {
        timestamp: "10:23:23",
        level: "INFO",
        message: 'Node "Format Customer Data" completed successfully',
      },
      {
        timestamp: "10:23:24",
        level: "DEBUG",
        message: 'Executing node "Create Account"',
      },
      {
        timestamp: "10:23:40",
        level: "INFO",
        message: 'Node "Create Account" completed successfully',
      },
      {
        timestamp: "10:23:41",
        level: "DEBUG",
        message: 'Executing node "Send Welcome Email"',
      },
      {
        timestamp: "10:23:45",
        level: "INFO",
        message: 'Node "Send Welcome Email" completed successfully',
      },
      {
        timestamp: "10:23:45",
        level: "INFO",
        message: "Workflow execution completed successfully",
      },
    ],
  };

  // Get status badge based on execution status
  const getStatusBadge = (status) => {
    switch (status) {
      case "success":
        return <Badge className="bg-green-500">Success</Badge>;

      case "failed":
        return <Badge className="bg-red-500">Failed</Badge>;

      case "running":
        return <Badge className="bg-blue-500">Running</Badge>;

      case "partial":
        return <Badge className="bg-yellow-500">Partial Success</Badge>;

      default:
        return <Badge className="bg-gray-500">Unknown</Badge>;
    }
  };

  return (
    <div className="h-screen w-full flex flex-col overflow-hidden">
      {/* Header with back button */}
      <div className="flex items-center justify-between p-4 border-b border-border">
        <div className="flex items-center space-x-2">
          <Link to="/workflow-canvas">
            <Button variant="ghost" size="icon">
              <ArrowLeftIcon className="h-4 w-4" />
            </Button>
          </Link>
          <h1 className="text-2xl font-bold">Execution Details</h1>
          {getStatusBadge(execution.status)}
        </div>
        <div className="flex items-center space-x-2">
          <Button variant="outline">
            <RotateCwIcon className="mr-2 h-4 w-4" />
            Re-run Workflow
          </Button>
        </div>
      </div>

      {/* Main content */}
      <div className="flex-1 overflow-hidden">
        <WorkflowExecutionHistory
          executions={[execution]}
          onViewDetails={() => {}}
          onRefresh={() => {}}
          onCopyToEditor={() => {}}
          onDelete={() => {}}
          showList={false}
          defaultSelectedExecution={execution}
        />
      </div>
    </div>
  );
}
