export interface WorkflowControlsProps {
  isRunning?: boolean;
  onRun?: () => void;
  onPause?: () => void;
  onSave?: () => void;
  onUndo?: () => void;
  onRedo?: () => void;
  canUndo?: boolean;
  canRedo?: boolean;
  onDuplicate?: () => void;
  onExport?: () => void;
  onImport?: () => void;
  onShare?: () => void;
  onVersionHistory?: () => void;
  onToggleSearch?: () => void;
  isSearchOpen?: boolean;
  className?: string;
}
