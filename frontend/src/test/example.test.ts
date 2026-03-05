import { describe, it, expect } from "vitest";
import { cn } from "@/lib/utils";

describe("utils", () => {
  it("cn merges class names correctly", () => {
    expect(cn("foo", "bar")).toBe("foo bar");
  });

  it("cn handles conditional classes", () => {
    expect(cn("base", false && "hidden", "visible")).toBe("base visible");
  });

  it("cn deduplicates tailwind classes", () => {
    const result = cn("p-4 px-2", "px-6");
    expect(result).toContain("px-6");
    expect(result).not.toContain("px-2");
  });
});
