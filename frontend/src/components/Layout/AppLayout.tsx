import type { ReactNode } from "react";

interface AppLayoutProps {
  children: ReactNode;
}

const AppLayout = ({ children }: AppLayoutProps) => {
  return (
    <div style={{ minHeight: "100vh", backgroundColor: "#f5f5f5" }}>
      <header
        style={{
          backgroundColor: "#1a1a2e",
          color: "#ffffff",
          padding: "16px 32px",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
        }}
      >
        <h1 style={{ margin: 0, fontSize: "1.5rem", fontWeight: 700 }}>
          Dealership Agent
        </h1>
        <span style={{ fontSize: "0.875rem", opacity: 0.7 }}>
          Find your perfect car
        </span>
      </header>

      <main style={{ maxWidth: 1200, margin: "0 auto", padding: "32px 16px" }}>
        {children}
      </main>
    </div>
  );
};

export default AppLayout;
