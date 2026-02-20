import TopNavigation from "@features/shared/components/top-navigation";
import useCredentialVault from "@/hooks/use-credential-vault";
import { WorkflowGalleryHeader } from "@/features/workflow/pages/workflow-gallery/workflow-gallery-header";
import { WorkflowGalleryTabs } from "@/features/workflow/pages/workflow-gallery/workflow-gallery-tabs";
import { useWorkflowGallery } from "@/features/workflow/pages/workflow-gallery/use-workflow-gallery";

export default function WorkflowGallery() {
  const {
    credentials,
    isLoading: isCredentialsLoading,
    onAddCredential,
    onUpdateCredential,
    onDeleteCredential,
    onRevealCredentialSecret,
  } = useCredentialVault();

  const {
    searchQuery,
    setSearchQuery,
    sortBy,
    setSortBy,
    filters,
    setFilters,
    showFilterPopover,
    setShowFilterPopover,
    showNewFolderDialog,
    setShowNewFolderDialog,
    newFolderName,
    setNewFolderName,
    showNewWorkflowDialog,
    setShowNewWorkflowDialog,
    newWorkflowName,
    setNewWorkflowName,
    selectedTab,
    setSelectedTab,
    sortedWorkflows,
    isTemplateView,
    handleCreateFolder,
    handleCreateWorkflow,
    handleUseTemplate,
    handleDuplicateWorkflow,
    handleExportWorkflow,
    handleDeleteWorkflow,
    handleApplyFilters,
    handleOpenWorkflow,
  } = useWorkflowGallery();

  return (
    <div className="flex h-screen flex-col">
      <TopNavigation
        credentials={credentials}
        isCredentialsLoading={isCredentialsLoading}
        onAddCredential={onAddCredential}
        onUpdateCredential={onUpdateCredential}
        onDeleteCredential={onDeleteCredential}
        onRevealCredentialSecret={onRevealCredentialSecret}
      />

      <main className="flex-1 overflow-auto">
        <div className="h-full">
          <div className="flex h-[calc(100%-80px)] flex-col">
            <div className="flex-1 overflow-auto">
              <WorkflowGalleryHeader
                searchQuery={searchQuery}
                onSearchQueryChange={setSearchQuery}
                sortBy={sortBy}
                onSortChange={setSortBy}
                filters={filters}
                onFiltersChange={setFilters}
                showFilterPopover={showFilterPopover}
                onFilterPopoverChange={setShowFilterPopover}
                showNewFolderDialog={showNewFolderDialog}
                onNewFolderDialogChange={setShowNewFolderDialog}
                newFolderName={newFolderName}
                onFolderNameChange={setNewFolderName}
                onCreateFolder={handleCreateFolder}
                showNewWorkflowDialog={showNewWorkflowDialog}
                onNewWorkflowDialogChange={setShowNewWorkflowDialog}
                newWorkflowName={newWorkflowName}
                onWorkflowNameChange={setNewWorkflowName}
                onCreateWorkflow={handleCreateWorkflow}
                onApplyFilters={handleApplyFilters}
              />

              <WorkflowGalleryTabs
                selectedTab={selectedTab}
                onSelectedTabChange={setSelectedTab}
                sortedWorkflows={sortedWorkflows}
                isTemplateView={isTemplateView}
                searchQuery={searchQuery}
                onCreateWorkflowRequest={() => setShowNewWorkflowDialog(true)}
                onOpenWorkflow={handleOpenWorkflow}
                onUseTemplate={handleUseTemplate}
                onDuplicateWorkflow={handleDuplicateWorkflow}
                onExportWorkflow={handleExportWorkflow}
                onDeleteWorkflow={handleDeleteWorkflow}
              />
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
