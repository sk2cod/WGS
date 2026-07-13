import type { ReactNode } from "react";
import { CANVAS_WIDTH, CANVAS_HEIGHT } from "@/lib/canvas";

interface ScaledSlideProps {
  scale: number;
  children: ReactNode;
}

/** Displays a full 1080x1350 slide component shrunk to fit the preview grid. */
export default function ScaledSlide({ scale, children }: ScaledSlideProps) {
  return (
    <div
      style={{
        width: CANVAS_WIDTH * scale,
        height: CANVAS_HEIGHT * scale,
        overflow: "hidden",
        borderRadius: 8,
        boxShadow: "0 1px 4px rgba(0,0,0,0.15)",
      }}
    >
      <div
        style={{
          width: CANVAS_WIDTH,
          height: CANVAS_HEIGHT,
          transform: `scale(${scale})`,
          transformOrigin: "top left",
        }}
      >
        {children}
      </div>
    </div>
  );
}
