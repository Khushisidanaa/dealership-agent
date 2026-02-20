import { useState } from "react";
import { api } from "../api/client";
import type { AuthUser } from "../api/client";
import "./WelcomePage.css";

interface WelcomePageProps {
  onAuth: (user: AuthUser) => void;
}

type Tab = "login" | "signup";

export function WelcomePage({ onAuth }: WelcomePageProps) {
  const [tab, setTab] = useState<Tab>("signup");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!email.trim() || !password.trim()) {
      setError("Email and password are required.");
      return;
    }
    if (tab === "signup" && !name.trim()) {
      setError("Name is required.");
      return;
    }

    setLoading(true);
    try {
      const user =
        tab === "signup"
          ? await api.auth.signup(name.trim(), email.trim(), password)
          : await api.auth.login(email.trim(), password);
      onAuth(user);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="welcome">
      <div className="welcome-bg">
        <div className="welcome-glow welcome-glow--1" />
        <div className="welcome-glow welcome-glow--2" />
        <div className="welcome-grid" />
      </div>

      <div className="welcome-content">
        <div className="welcome-badge">AI-Powered Car Buying</div>
        <h1 className="welcome-title">
          Find Your Perfect Car.
          <br />
          <span className="welcome-title-accent">We Handle the Rest.</span>
        </h1>
        <p className="welcome-subtitle">
          Tell us what you want. We search dealers, call them with our AI voice
          agent, negotiate prices, and give you a shortlist -- all in minutes.
        </p>

        <div className="welcome-auth-card">
          <div className="welcome-tabs">
            <button
              type="button"
              className={`welcome-tab ${tab === "signup" ? "welcome-tab--active" : ""}`}
              onClick={() => {
                setTab("signup");
                setError(null);
              }}
            >
              Sign Up
            </button>
            <button
              type="button"
              className={`welcome-tab ${tab === "login" ? "welcome-tab--active" : ""}`}
              onClick={() => {
                setTab("login");
                setError(null);
              }}
            >
              Log In
            </button>
          </div>

          <form className="welcome-auth-form" onSubmit={handleSubmit}>
            {tab === "signup" && (
              <div className="welcome-field">
                <label htmlFor="auth-name">Name</label>
                <input
                  id="auth-name"
                  type="text"
                  placeholder="Your name"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  autoFocus
                />
              </div>
            )}

            <div className="welcome-field">
              <label htmlFor="auth-email">Email</label>
              <input
                id="auth-email"
                type="email"
                placeholder="you@example.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                autoFocus={tab === "login"}
              />
            </div>

            <div className="welcome-field">
              <label htmlFor="auth-password">Password</label>
              <input
                id="auth-password"
                type="password"
                placeholder="Your password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </div>

            {error && <p className="welcome-auth-error">{error}</p>}

            <button
              type="submit"
              className="welcome-btn welcome-btn--full"
              disabled={loading}
            >
              {loading
                ? "Please wait..."
                : tab === "signup"
                  ? "Create Account"
                  : "Log In"}
              {!loading && (
                <svg
                  width="18"
                  height="18"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2.5"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <path d="M5 12h14M12 5l7 7-7 7" />
                </svg>
              )}
            </button>
          </form>
        </div>

        <div className="welcome-features">
          <div className="welcome-feature">
            <div className="welcome-feature-icon">
              <svg
                width="20"
                height="20"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <circle cx="11" cy="11" r="8" />
                <path d="m21 21-4.3-4.3" />
              </svg>
            </div>
            <div>
              <strong>Smart Search</strong>
              <span>Scans thousands of listings across dealers</span>
            </div>
          </div>
          <div className="welcome-feature">
            <div className="welcome-feature-icon">
              <svg
                width="20"
                height="20"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72c.127.96.361 1.903.7 2.81a2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45c.907.339 1.85.573 2.81.7A2 2 0 0 1 22 16.92z" />
              </svg>
            </div>
            <div>
              <strong>AI Voice Calls</strong>
              <span>Our agent calls dealers and negotiates for you</span>
            </div>
          </div>
          <div className="welcome-feature">
            <div className="welcome-feature-icon">
              <svg
                width="20"
                height="20"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z" />
              </svg>
            </div>
            <div>
              <strong>Top Picks</strong>
              <span>Ranked recommendations based on real conversations</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
