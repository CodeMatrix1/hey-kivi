import { describe, expect, it } from "vitest";

function nextIndex(current: number, delta: 1 | -1, length: number): number {
  if (length === 0) return -1;
  if (current < 0) return delta > 0 ? 0 : length - 1;
  if (delta > 0) return Math.min(length - 1, current + 1);
  return Math.max(0, current - 1);
}

describe("arrow list navigation index", () => {
  it("starts at first item from unset on arrow down", () => {
    expect(nextIndex(-1, 1, 5)).toBe(0);
  });

  it("starts at last item from unset on arrow up", () => {
    expect(nextIndex(-1, -1, 5)).toBe(4);
  });

  it("clamps at ends", () => {
    expect(nextIndex(4, 1, 5)).toBe(4);
    expect(nextIndex(0, -1, 5)).toBe(0);
  });
});
