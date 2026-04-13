import type {
  ExternalAgentProviderName,
  ExternalAgentProviderStatus,
} from "@/lib/api";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/design-system/ui/select";

interface VibeAgentSelectorProps {
  readyProviders: ExternalAgentProviderStatus[];
  selectedProvider: ExternalAgentProviderName | null;
  onSelect: (provider: ExternalAgentProviderName) => void;
}

export function VibeAgentSelector({
  readyProviders,
  selectedProvider,
  onSelect,
}: VibeAgentSelectorProps) {
  const hasProviders = readyProviders.length > 0;

  return (
    <Select
      value={selectedProvider ?? undefined}
      onValueChange={(value) => onSelect(value as ExternalAgentProviderName)}
      disabled={!hasProviders}
    >
      <SelectTrigger className="w-full">
        <SelectValue
          placeholder={hasProviders ? "Select an agent" : "No agents connected"}
        />
      </SelectTrigger>
      <SelectContent>
        {readyProviders.map((provider) => (
          <SelectItem key={provider.provider} value={provider.provider}>
            {provider.display_name}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
