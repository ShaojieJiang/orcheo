import { useState } from "react";
import { Outlet } from "react-router-dom";
import SidebarLayout from "@features/workflow/components/layouts/sidebar-layout";
import { useVibe } from "@features/vibe/context/vibe-context";
import {
  VIBE_SIDEBAR_COLLAPSED_WIDTH,
  VIBE_SIDEBAR_MAX_WIDTH,
  VIBE_SIDEBAR_MIN_WIDTH,
  VIBE_SIDEBAR_WIDTH,
} from "@features/vibe/constants";
import { VibeSidebar } from "./vibe-sidebar";
import { VibeSidebarCollapsed } from "./vibe-sidebar-collapsed";

export function VibeAuthenticatedLayout() {
  const { isOpen, toggleOpen } = useVibe();
  const [sidebarWidth, setSidebarWidth] = useState(VIBE_SIDEBAR_WIDTH);

  return (
    <SidebarLayout
      sidebar={isOpen ? <VibeSidebar /> : <VibeSidebarCollapsed />}
      isCollapsed={!isOpen}
      onToggleCollapse={toggleOpen}
      sidebarWidth={sidebarWidth}
      collapsedWidth={VIBE_SIDEBAR_COLLAPSED_WIDTH}
      resizable
      minWidth={VIBE_SIDEBAR_MIN_WIDTH}
      maxWidth={VIBE_SIDEBAR_MAX_WIDTH}
      onWidthChange={setSidebarWidth}
      showCollapseButton={false}
      position="left"
      className="h-screen"
    >
      <Outlet />
    </SidebarLayout>
  );
}
