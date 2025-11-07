import React from "react";

import type { CarouselContextValue } from "./types";

export const CarouselContext = React.createContext<CarouselContextValue | null>(
  null,
);

export function useCarouselContext() {
  const context = React.useContext(CarouselContext);

  if (!context) {
    throw new Error("useCarousel must be used within a <Carousel />");
  }

  return context;
}
