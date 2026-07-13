import Link from "next/link";

export default function Home() {
  return (
    <main
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        minHeight: "100vh",
        gap: 16,
        fontFamily: "Inter, sans-serif",
      }}
    >
      <h1>AI Content Studio</h1>
      <p>Phase 1 — design foundation.</p>
      <Link href="/preview" style={{ textDecoration: "underline" }}>
        View the template preview grid →
      </Link>
    </main>
  );
}
