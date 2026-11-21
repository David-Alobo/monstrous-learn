import { describe, expect, it } from "vitest";
import { answersFrom, MAX_GOALS, outcome, problems, toBody } from "../../shared/site/static/js/waitlist.js";

/** A filled-in form, with any field replaced or removed (null removes it). */
function form(changes = {}) {
  const fields = {
    first_name: " Ada ",
    email: "ada@example.com",
    courses: ["Data Engineering, Series 1"],
    country: "Nigeria",
    role: "PhD student",
    position: "Research Scientist",
    field_of_study: "",
    python_level: "A little",
    heard_from: "LinkedIn",
    goals: "",
    consent: "yes",
    ...changes,
  };
  const data = new FormData();
  for (const [name, value] of Object.entries(fields)) {
    if (value === null) continue;
    for (const v of Array.isArray(value) ? value : [value]) data.append(name, v);
  }
  return data;
}

describe("answersFrom", () => {
  it("reads and trims every answer, with courses as a list", () => {
    const a = answersFrom(form({ courses: ["Data Engineering, Series 1", "MLOps for Chemists"] }));
    expect(a.first_name).toBe("Ada");
    expect(a.courses).toEqual(["Data Engineering, Series 1", "MLOps for Chemists"]);
    expect(a.consent).toBe(true);
    expect(a.trap).toBe("");
  });
});

describe("problems", () => {
  it("finds nothing wrong with a good form", () => {
    expect(problems(answersFrom(form()))).toEqual([]);
  });
  it("asks for a name, a real email, a course and consent", () => {
    const fields = (changes) => problems(answersFrom(form(changes))).map((p) => p.field);
    expect(fields({ first_name: "  " })).toEqual(["first_name"]);
    expect(fields({ email: "ada@example" })).toEqual(["email"]);
    expect(fields({ email: "not an email" })).toEqual(["email"]);
    expect(fields({ courses: [] })).toEqual(["courses"]);
    expect(fields({ consent: null })).toEqual(["consent"]);
    expect(fields({ goals: "x".repeat(MAX_GOALS + 1) })).toEqual(["goals"]);
    expect(fields({ position: "x".repeat(101) })).toEqual(["position"]);
  });
  it("leaves the demographic questions optional", () => {
    const blank = { country: "", role: "", position: "", python_level: "", heard_from: "" };
    expect(problems(answersFrom(form(blank)))).toEqual([]);
  });
});

describe("toBody", () => {
  it("sends what FluentCRM needs and leaves out empty answers", () => {
    const body = toBody(answersFrom(form()));
    expect(body.get("email")).toBe("ada@example.com");
    expect(body.get("first_name")).toBe("Ada");
    expect(body.getAll("courses[]")).toEqual(["Data Engineering, Series 1"]);
    expect(body.get("country")).toBe("Nigeria");
    expect(body.get("position")).toBe("Research Scientist");
    expect(body.has("field_of_study")).toBe(false);
    expect(body.has("goals")).toBe(false);
    expect(body.has("consent")).toBe(false); // consent is checked here, not stored as an answer
    expect(body.has("website")).toBe(false); // the spam trap is never sent
  });
});

describe("outcome", () => {
  it("counts as success only the receiver's own ok", () => {
    expect(outcome(200, '{"ok":true}').ok).toBe(true);
    expect(outcome(200, "<!doctype html><html>a page, not the receiver</html>").ok).toBe(false);
    expect(outcome(200, '{"ok":false}').ok).toBe(false);
  });
  it("passes on the receiver's message when it refuses", () => {
    const tooMany = outcome(429, '{"code":"too_many","message":"Too many sign-ups from here."}');
    expect(tooMany).toEqual({ ok: false, message: "Too many sign-ups from here." });
    expect(outcome(500, "Internal Server Error")).toEqual({ ok: false, message: "" });
  });
});
