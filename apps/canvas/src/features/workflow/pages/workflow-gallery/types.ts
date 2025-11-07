export type WorkflowGalleryTab = "all" | "favorites" | "shared" | "templates";

export type WorkflowGallerySort = "updated" | "created" | "name";

export interface WorkflowGalleryFilters {
  owner: {
    me: boolean;
    shared: boolean;
  };
  status: {
    active: boolean;
    draft: boolean;
    archived: boolean;
  };
  tags: {
    favorite: boolean;
    template: boolean;
    production: boolean;
    development: boolean;
  };
}
