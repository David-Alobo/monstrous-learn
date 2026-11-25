import { describe, expect, it } from "vitest";
import { OFFSET, activeSection } from "../../shared/site/static/js/toc.js";

const at = (...tops) => tops.map((top, i) => ({ id: `s${i + 1}`, top }));

describe("activeSection", () => {
  it("is none before the first heading reaches the reading line", () => {
    expect(activeSection(at(300, 900, 1500))).toBe(null);
  });
  it("is the last heading that has passed the reading line", () => {
    expect(activeSection(at(OFFSET, 900, 1500))).toBe("s1");
    expect(activeSection(at(-400, 50, 700))).toBe("s2");
    expect(activeSection(at(-2000, -1200, -10))).toBe("s3");
  });
  it("is the last section at the end of the page, even if its heading never reached the line", () => {
    expect(activeSection(at(-900, -200, 400), OFFSET, true)).toBe("s3");
  });
  it("can use another reading line", () => {
    expect(activeSection(at(200, 900), 250)).toBe("s1");
    expect(activeSection(at(200, 900), 150)).toBe(null);
  });
  it("is none for a page without sections", () => {
    expect(activeSection([])).toBe(null);
  });
});
