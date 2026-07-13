import type { ReactNode } from "react";
import { CANVAS_WIDTH, CANVAS_HEIGHT, SAFE_ZONE_INSET_X } from "@/lib/canvas";

interface SlideFrameProps {
  backgroundColor: string;
  children: ReactNode;
}

/**
 * Shared 1080x1350 canvas + centered 3:4 safe-zone padding used by every
 * template. Background color is passed explicitly (not always tokens.background_color —
 * CarouselClosing uses the mood's primary color instead).
 */
export default function SlideFrame({ backgroundColor, children }: SlideFrameProps) {
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        width: CANVAS_WIDTH,
        height: CANVAS_HEIGHT,
        backgroundColor,
        paddingLeft: SAFE_ZONE_INSET_X,
        paddingRight: SAFE_ZONE_INSET_X,
        paddingTop: 72,
        paddingBottom: 72,
      }}
    >
      {children}
    </div>
  );
}
