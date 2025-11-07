"use client";

import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { VariantProps } from "class-variance-authority";

import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/design-system/ui/tooltip";
import { cn } from "@/lib/utils";

import { useSidebar } from "@/design-system/ui/sidebar/use-sidebar";
import { sidebarMenuButtonVariants } from "@/design-system/ui/sidebar/sidebar-menu/menu-button-variants";

const SidebarMenuButton = React.forwardRef<
  HTMLButtonElement,
  React.ComponentProps<"button"> & {
    asChild?: boolean;
    isActive?: boolean;
    tooltip?: string | React.ComponentProps<typeof TooltipContent>;
  } & VariantProps<typeof sidebarMenuButtonVariants>
>(
  (
    {
      asChild = false,
      isActive = false,
      variant = "default",
      size = "default",
      tooltip,
      className,
      ...props
    },
    ref,
  ) => {
    const Comp = asChild ? Slot : "button";
    const { isMobile, state } = useSidebar();

    const button = (
      <Comp
        ref={ref}
        data-sidebar="menu-button"
        data-size={size}
        data-active={isActive}
        className={cn(sidebarMenuButtonVariants({ variant, size }), className)}
        {...props}
      />
    );

    if (!tooltip) {
      return button;
    }

    const tooltipProps: React.ComponentProps<typeof TooltipContent> =
      typeof tooltip === "string" ? { children: tooltip } : tooltip;

    return (
      <Tooltip>
        <TooltipTrigger asChild>{button}</TooltipTrigger>
        <TooltipContent
          side="right"
          align="center"
          hidden={state !== "collapsed" || isMobile}
          {...tooltipProps}
        />
      </Tooltip>
    );
  },
);
SidebarMenuButton.displayName = "SidebarMenuButton";

export { SidebarMenuButton };
