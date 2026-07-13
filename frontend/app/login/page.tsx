"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { supabase } from "@/lib/supabaseClient";
import {
  cardStyle,
  inputStyle,
  labelStyle,
  primaryButtonStyle,
  screenStyle,
} from "@/lib/ui-styles";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      if (data.session) router.replace("/");
    });
  }, [router]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    const { error } = await supabase.auth.signInWithPassword({ email, password });
    setSubmitting(false);
    if (error) {
      setError(error.message);
      return;
    }
    router.replace("/");
  }

  return (
    <main style={screenStyle}>
      <header>
        <div style={labelStyle}>{"Women's Growth Society"}</div>
        <h1 style={{ fontSize: 26, marginTop: 4 }}>Sign in</h1>
      </header>

      <form onSubmit={handleSubmit} style={cardStyle}>
        <input
          style={inputStyle}
          type="email"
          placeholder="Email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          autoComplete="email"
          required
        />
        <input
          style={inputStyle}
          type="password"
          placeholder="Password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          autoComplete="current-password"
          required
        />
        {error && (
          <div style={{ background: "#FCE9E7", color: "#8C3B2E", borderRadius: 10, padding: "10px 14px", fontSize: 14 }}>
            {error}
          </div>
        )}
        <button
          type="submit"
          style={{ ...primaryButtonStyle, opacity: submitting ? 0.6 : 1 }}
          disabled={submitting}
        >
          {submitting ? "Signing in…" : "Sign in"}
        </button>
      </form>
    </main>
  );
}
