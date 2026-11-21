import { describe, expect, it } from "vitest";
import { MAX_COMMENT, ratingBody, ratingFrom, ratingProblems } from "../../shared/site/static/js/feedback.js";

/** A rating form's data, with any field given. */
function form(fields) {
  const data = new FormData();
  for (const [name, value] of Object.entries(fields)) data.append(name, value);
  return data;
}

describe("ratingFrom and ratingProblems", () => {
  it("accepts 1 to 5 stars, with or without a comment", () => {
    for (const rating of ["1", "3", "5"]) {
      expect(ratingProblems(ratingFrom(form({ rating, comment: "" })))).toEqual([]);
    }
    expect(ratingFrom(form({ rating: "4", comment: "  Clear.  " })).comment).toBe("Clear.");
  });
  it("asks for a rating and a comment of sensible length", () => {
    expect(ratingProblems(ratingFrom(form({})))).toEqual(["Please choose from 1 to 5 stars."]);
    expect(ratingProblems(ratingFrom(form({ rating: "6" })))).toHaveLength(1);
    const long = ratingFrom(form({ rating: "2", comment: "x".repeat(MAX_COMMENT + 1) }));
    expect(ratingProblems(long)).toHaveLength(1);
  });
});

describe("ratingBody", () => {
  it("sends the module, the rating and only a comment that was written", () => {
    const module = "data-engineering/series-1/01-graphs-and-matrices";
    const body = ratingBody(module, ratingFrom(form({ rating: "5", comment: "" })));
    expect(body.get("module")).toBe(module);
    expect(body.get("rating")).toBe("5");
    expect(body.has("comment")).toBe(false);
    expect(body.has("website")).toBe(false); // the spam trap is never sent
  });
});
