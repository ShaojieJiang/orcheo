import React from "react";

import { CarouselContext } from "./carousel-context";
import type { CarouselContextValue } from "./types";

export function CarouselProvider({
  value,
  children,
}: {
  value: CarouselContextValue;
  children: React.ReactNode;
}) {
  return (
    <CarouselContext.Provider value={value}>
      {children}
    </CarouselContext.Provider>
  );
}
