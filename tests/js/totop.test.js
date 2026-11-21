import { describe, expect, it } from "vitest";
import { SHOW_AFTER, shouldShow } from "../../shared/site/static/js/totop.js";

describe("shouldShow", () => {
  it("stays hidden near the top and appears once the reader has scrolled down", () => {
    expect(shouldShow(0)).toBe(false);
    expect(shouldShow(SHOW_AFTER)).toBe(false);
    expect(shouldShow(SHOW_AFTER + 1)).toBe(true);
    expect(shouldShow(5000)).toBe(true);
  });
  it("can appear sooner or later", () => {
    expect(shouldShow(150, 100)).toBe(true);
    expect(shouldShow(150, 200)).toBe(false);
  });
});
