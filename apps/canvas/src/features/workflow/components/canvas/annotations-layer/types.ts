export interface Annotation {
  id: string;
  content: string;
  position: { x: number; y: number };
  author: {
    name: string;
    avatar: string;
  };
  createdAt: string;
}
