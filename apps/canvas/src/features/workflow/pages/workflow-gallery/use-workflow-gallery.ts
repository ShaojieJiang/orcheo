import { useWorkflowGalleryActions } from "./use-workflow-gallery-actions";
import { useWorkflowGalleryState } from "./use-workflow-gallery-state";

export const useWorkflowGallery = () => {
  const state = useWorkflowGalleryState();
  const actions = useWorkflowGalleryActions({
    newFolderName: state.newFolderName,
    setNewFolderName: state.setNewFolderName,
    setSelectedTab: state.setSelectedTab,
    setShowNewFolderDialog: state.setShowNewFolderDialog,
    setShowFilterPopover: state.setShowFilterPopover,
  });

  return {
    ...state,
    ...actions,
  };
};
