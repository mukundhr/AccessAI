/**
 * Component rendering tests for AccessAI pages.
 * Validates that key pages render without crashing and contain expected content.
 */

import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { BrowserRouter } from "react-router-dom";
import { I18nProvider } from "@/lib/i18n";
import React from "react";

// Mock framer-motion to avoid animation issues in tests
vi.mock("framer-motion", () => {
  const createMotionComponent = (tag: string) =>
    React.forwardRef(({ children, initial, animate, transition, whileInView, whileHover, whileTap, viewport, variants, exit, ...props }: any, ref: any) =>
      React.createElement(tag, { ...props, ref }, children)
    );

  return {
    motion: new Proxy({}, {
      get: (_target, prop: string) => createMotionComponent(prop),
    }),
    AnimatePresence: ({ children }: any) => children,
    useInView: () => true,
  };
});

function renderWithRouter(ui: React.ReactElement) {
  return render(<BrowserRouter><I18nProvider>{ui}</I18nProvider></BrowserRouter>);
}

// ── Navbar ──

describe("Navbar", () => {
  it("renders brand name", async () => {
    const { default: Navbar } = await import("@/components/Navbar");
    renderWithRouter(<Navbar />);
    expect(screen.getByText("Access")).toBeInTheDocument();
    expect(screen.getByText("AI")).toBeInTheDocument();
  });

  it("renders Impact link", async () => {
    const { default: Navbar } = await import("@/components/Navbar");
    renderWithRouter(<Navbar />);
    expect(screen.getByText("Impact")).toBeInTheDocument();
  });
});

// ── Footer ──

describe("Footer", () => {
  it("renders copyright notice", async () => {
    const { default: Footer } = await import("@/components/Footer");
    renderWithRouter(<Footer />);
    expect(screen.getByText(/AccessAI/)).toBeInTheDocument();
  });

  it("contains correct navigation links", async () => {
    const { default: Footer } = await import("@/components/Footer");
    renderWithRouter(<Footer />);
    const links = screen.getAllByRole("link");
    const hrefs = links.map((l) => l.getAttribute("href"));
    expect(hrefs).toContain("/about");
    expect(hrefs).toContain("/privacy");
    expect(hrefs).toContain("/disclaimer");
  });
});

// ── About Page ──

describe("About Page", () => {
  it("renders page heading", async () => {
    const { default: About } = await import("@/pages/About");
    renderWithRouter(<About />);
    expect(screen.getAllByText("About").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText(/The Problem/i)).toBeInTheDocument();
  });

  it("lists AWS services used", async () => {
    const { default: About } = await import("@/pages/About");
    renderWithRouter(<About />);
    const text = document.body.textContent || "";
    expect(text).toMatch(/Textract/);
    expect(text).toMatch(/Bedrock/);
    expect(text).toMatch(/Polly/);
  });
});

// ── Privacy Page ──

describe("Privacy Page", () => {
  it("renders privacy policy heading", async () => {
    const { default: Privacy } = await import("@/pages/Privacy");
    renderWithRouter(<Privacy />);
    expect(screen.getByText(/Privacy Policy/i)).toBeInTheDocument();
  });

  it("mentions PII anonymisation", async () => {
    const { default: Privacy } = await import("@/pages/Privacy");
    renderWithRouter(<Privacy />);
    // Should mention that PII is anonymised before AI processing
    const text = document.body.textContent || "";
    expect(text).toMatch(/anonym/i);
  });
});

// ── Disclaimer Page ──

describe("Disclaimer Page", () => {
  it("renders disclaimer heading", async () => {
    const { default: Disclaimer } = await import("@/pages/Disclaimer");
    renderWithRouter(<Disclaimer />);
    expect(screen.getByText(/Medical Disclaimer/i)).toBeInTheDocument();
  });

  it("warns that app is not diagnostic", async () => {
    const { default: Disclaimer } = await import("@/pages/Disclaimer");
    renderWithRouter(<Disclaimer />);
    const text = document.body.textContent || "";
    expect(text).toMatch(/not.*(diagnos|medical advice)/i);
  });
});

// ── Index Page ──

describe("Index Page", () => {
  it("renders hero section", async () => {
    const { default: Index } = await import("@/pages/Index");
    renderWithRouter(<Index />);
    expect(screen.getByText(/Understand Your Medical Reports/i)).toBeInTheDocument();
  });
});
