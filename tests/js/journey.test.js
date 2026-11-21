import { describe, expect, it } from "vitest";
import { fromHash, moveTo } from "../../shared/site/static/js/journey.js";

const ids = ["sources", "represent", "ingest"];

describe("moveTo", () => {
  it("moves forward and back, wrapping at the ends", () => {
    expect(moveTo(ids, "sources", "ArrowRight")).toBe("represent");
    expect(moveTo(ids, "ingest", "ArrowRight")).toBe("sources");
    expect(moveTo(ids, "sources", "ArrowLeft")).toBe("ingest");
    expect(moveTo(ids, "represent", "ArrowUp")).toBe("sources");
  });
  it("jumps to the first and last step", () => {
    expect(moveTo(ids, "represent", "Home")).toBe("sources");
    expect(moveTo(ids, "represent", "End")).toBe("ingest");
  });
  it("ignores other keys and unknown steps", () => {
    expect(moveTo(ids, "sources", "a")).toBeNull();
    expect(moveTo(ids, "nope", "ArrowRight")).toBeNull();
  });
});

describe("fromHash", () => {
  it("reads a step from the address", () => {
    expect(fromHash("#step-ingest", ids, "sources")).toBe("ingest");
  });
  it("falls back for an empty or unknown address", () => {
    expect(fromHash("", ids, "sources")).toBe("sources");
    expect(fromHash("#step-nope", ids, "sources")).toBe("sources");
    expect(fromHash("#big-picture", ids, "sources")).toBe("sources");
  });
});
