import { BrowserRouter as Router, Routes, Route } from "react-router-dom";
import WorkflowGallery from "@features/workflow/pages/workflow-gallery";
import WorkflowCanvas from "@features/workflow/pages/workflow-canvas";
import WorkflowExecutionDetails from "@features/workflow/pages/workflow-execution-details";
import Login from "@features/auth/pages/login";
import Signup from "@features/auth/pages/signup";
import Profile from "@features/account/pages/profile";
import Settings from "@features/account/pages/settings";
import HelpSupport from "@features/support/pages/help-support";

export default function OrcheoCanvasApp() {
  return (
    <Router>
      <Routes>
        <Route path="/" element={<WorkflowGallery />} />

        <Route path="/workflow-canvas" element={<WorkflowCanvas />} />

        <Route
          path="/workflow-execution-details/:executionId"
          element={<WorkflowExecutionDetails />}
        />

        <Route path="/login" element={<Login />} />

        <Route path="/signup" element={<Signup />} />

        <Route path="/profile" element={<Profile />} />

        <Route path="/settings" element={<Settings />} />

        <Route path="/help-support" element={<HelpSupport />} />
      </Routes>
    </Router>
  );
}
