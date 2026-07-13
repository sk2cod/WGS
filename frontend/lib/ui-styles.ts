import type { CSSProperties } from "react";
import { WGS_BRAND_KIT } from "./wgs-brand-kit";

export const colors = {
  bg: WGS_BRAND_KIT.background_color,
  text: WGS_BRAND_KIT.text_color,
  accent: WGS_BRAND_KIT.mood_palettes.wisdom.accent,
  primary: WGS_BRAND_KIT.mood_palettes.wisdom.primary,
};

export const screenStyle: CSSProperties = {
  maxWidth: 480,
  margin: "0 auto",
  minHeight: "100vh",
  padding: "24px 20px 48px",
  fontFamily: "Inter, sans-serif",
  color: colors.text,
  background: colors.bg,
  display: "flex",
  flexDirection: "column",
  gap: 20,
};

export const cardStyle: CSSProperties = {
  border: "1px solid rgba(36,28,51,0.12)",
  borderRadius: 16,
  padding: 20,
  background: "#fff",
  display: "flex",
  flexDirection: "column",
  gap: 10,
};

export const primaryButtonStyle: CSSProperties = {
  background: colors.primary,
  color: "#fff",
  border: "none",
  borderRadius: 999,
  padding: "14px 20px",
  fontSize: 16,
  fontWeight: 600,
  cursor: "pointer",
  fontFamily: "Inter, sans-serif",
};

export const secondaryButtonStyle: CSSProperties = {
  ...primaryButtonStyle,
  background: "transparent",
  color: colors.primary,
  border: `1.5px solid ${colors.primary}`,
};

export const ghostButtonStyle: CSSProperties = {
  ...primaryButtonStyle,
  background: "transparent",
  color: colors.text,
  border: "none",
  opacity: 0.65,
  padding: "10px 14px",
};

export const labelStyle: CSSProperties = {
  fontSize: 12,
  fontWeight: 600,
  letterSpacing: 1.5,
  textTransform: "uppercase",
  opacity: 0.55,
};

export const inputStyle: CSSProperties = {
  fontFamily: "Inter, sans-serif",
  fontSize: 15,
  padding: "10px 12px",
  borderRadius: 10,
  border: "1px solid rgba(36,28,51,0.2)",
  color: colors.text,
  background: "#fff",
  width: "100%",
};
