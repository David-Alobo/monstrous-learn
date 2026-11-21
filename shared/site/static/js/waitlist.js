// The course waitlist form (/learn/waitlist/).
//
// The page holds an ordinary HTML form. This script checks the answers in the browser, then sends
// them to the site's own receiver, the Monstrous Waitlist plugin on monstrous.com.ng
// (/wp-json/monstrous/v1/waitlist), which checks them again, adds the person to FluentCRM's
// waitlist with every answer, and has FluentCRM email them a link to confirm their address. The
// logic is in small pure functions, tested with Vitest; mount() wires them to the page.

export const MAX_GOALS = 300; // characters in the optional "what do you hope to do" answer

/**
 * The answers in a submitted form, trimmed.
 * @param {FormData} data the form's data
 * @returns {object} first_name, email, courses (a list), the optional answers, consent and the
 *   spam trap
 */
export function answersFrom(data) {
  const text = (name) => String(data.get(name) ?? "").trim();
  return {
    first_name: text("first_name"),
    email: text("email"),
    courses: data.getAll("courses").map(String),
    country: text("country"),
    role: text("role"),
    position: text("position"),
    field_of_study: text("field_of_study"),
    python_level: text("python_level"),
    heard_from: text("heard_from"),
    goals: text("goals"),
    consent: data.get("consent") === "yes",
    trap: text("website"), // hidden from people; only automated spam fills it in
  };
}

/**
 * What is wrong with the answers, in words a person can act on.
 * @param {object} a the answers, from answersFrom
 * @returns {{field: string, message: string}[]} one entry per problem; empty if all is well
 */
export function problems(a) {
  const found = [];
  if (!a.first_name) found.push({ field: "first_name", message: "Please give your first name." });
  else if (a.first_name.length > 60)
    found.push({ field: "first_name", message: "Please keep your first name under 60 characters." });
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(a.email))
    found.push({ field: "email", message: "Please give an email address like name@example.com." });
  if (a.courses.length === 0)
    found.push({ field: "courses", message: "Please choose at least one course." });
  if (a.position.length > 100)
    found.push({ field: "position", message: "Please keep your position under 100 characters." });
  if (a.goals.length > MAX_GOALS)
    found.push({ field: "goals", message: `Please keep this under ${MAX_GOALS} characters.` });
  if (!a.consent)
    found.push({ field: "consent", message: "Please tick the box to agree, so we may email you." });
  return found;
}

/**
 * The answers as the body of a request to FluentCRM's webhook. Optional answers left empty are
 * not sent, and courses go as a list (courses[]), which FluentCRM stores in a checkbox field.
 * @param {object} a the answers, from answersFrom
 * @returns {URLSearchParams} the request body
 */
export function toBody(a) {
  const body = new URLSearchParams({ email: a.email, first_name: a.first_name });
  for (const course of a.courses) body.append("courses[]", course);
  for (const name of ["country", "role", "position", "field_of_study", "python_level", "heard_from", "goals"]) {
    if (a[name]) body.append(name, a[name]);
  }
  return body;
}

/**
 * What the receiver's answer means: success only if it says {"ok": true}; otherwise its own
 * message, if it gave one (e.g. "Too many sign-ups from here").
 * @param {number} status the HTTP status
 * @param {string} text the answer's body
 * @returns {{ok: boolean, message: string}}
 */
export function outcome(status, text) {
  let data = null;
  try {
    data = JSON.parse(text);
  } catch {
    // not JSON: a page or an error from somewhere else, so it did not reach the receiver
  }
  if (status >= 200 && status < 300 && data && data.ok === true) return { ok: true, message: "" };
  const message = data && typeof data.message === "string" ? data.message : "";
  return { ok: false, message };
}

/** Text made safe to show inside HTML. */
function plain(text) {
  return text.replace(/[&<>"']/g, (c) => `&#${c.charCodeAt(0)};`);
}

/**
 * Wire the form on the page: check, send, and show what happened.
 * @param {HTMLFormElement} form the waitlist form; its data-endpoint is the webhook's address
 * @param {Function} send fetch, or a stand-in for tests
 */
export function mount(form, send = globalThis.fetch) {
  const endpoint = form.dataset.endpoint || "";
  const status = form.querySelector(".form-status");
  const button = form.querySelector("button[type=submit]");
  const say = (html, kind) => {
    status.innerHTML = html;
    status.className = `form-status ${kind}`;
  };
  if (!endpoint) {
    button.disabled = true;
    say('Sign-ups open soon. Until then, email <a href="mailto:contact@monstrous.com.ng">contact@monstrous.com.ng</a> and we will add you.', "note");
    return;
  }
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    form.querySelectorAll("[aria-invalid]").forEach((el) => el.removeAttribute("aria-invalid"));
    const answers = answersFrom(new FormData(form));
    const found = problems(answers);
    if (found.length) {
      for (const p of found) form.querySelector(`[name=${p.field}]`)?.setAttribute("aria-invalid", "true");
      say(found.map((p) => p.message).join(" "), "error");
      form.querySelector("[aria-invalid]")?.focus();
      return;
    }
    if (answers.trap) {
      say("Thank you.", "done"); // spam: pretend all is well and send nothing
      return;
    }
    button.disabled = true;
    say("Sending…", "note");
    try {
      const response = await send(endpoint, { method: "POST", body: toBody(answers) });
      const result = outcome(response.status, await response.text());
      if (!result.ok) throw new Error(result.message);
      form.reset();
      say('<b>Nearly there.</b> Please check your inbox (and the spam folder, just in case) for an email from Monstrous Data, and click <b>Confirm my email</b>. Meanwhile, the course is open to read: <a href="../start/">start here</a>.', "done");
    } catch (error) {
      button.disabled = false;
      const reason = error instanceof Error && error.message ? `${plain(error.message)} ` : "";
      say(`Sorry, that did not go through. ${reason}Please try again in a minute, or email <a href="mailto:contact@monstrous.com.ng">contact@monstrous.com.ng</a> and we will add you.`, "error");
    }
  });
}

if (typeof document !== "undefined") {
  const form = document.querySelector("form.waitlist");
  if (form) mount(form);
}
