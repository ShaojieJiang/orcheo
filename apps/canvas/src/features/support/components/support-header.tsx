import type { ChangeEvent } from "react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/design-system/ui/card";
import { Input } from "@/design-system/ui/input";
import { Search } from "lucide-react";

interface SupportHeaderProps {
  searchQuery: string;
  onSearchChange: (value: string) => void;
}

export function SupportHeader({
  searchQuery,
  onSearchChange,
}: SupportHeaderProps) {
  const handleChange = (event: ChangeEvent<HTMLInputElement>) => {
    onSearchChange(event.target.value);
  };

  return (
    <section className="space-y-4">
      <div className="flex items-center justify-between space-y-2">
        <h2 className="text-3xl font-bold tracking-tight">Help & Support</h2>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>How can we help you?</CardTitle>
          <CardDescription>
            Search our knowledge base or contact support
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="relative">
            <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
            <Input
              type="search"
              placeholder="Search for help articles..."
              className="pl-8"
              value={searchQuery}
              onChange={handleChange}
            />
          </div>
        </CardContent>
      </Card>
    </section>
  );
}
