// The "How was this module?" box at the end of every lesson.
//
// The reader picks 1 to 5 stars and may add a comment; this script checks the answer and sends it
// to the site's own receiver (the Monstrous Waitlist plugin on monstrous.com.ng,
// /wp-json/monstrous/v1/feedback), which stores the rating anonymously: no name, email or IP
// address. Nothing is kept in the reader's browser. The logic is in small pure functions, tested
// with Vitest; mount() wires them to the page.

import { outcome } from "./waitlist.js";

export const MAX_COMMENT = 1000; // characters, the same limit as the receiver

/**
 * The answers in a submitted rating form.
 * @param {FormData} data the form's data
 * @returns {{rating: number, comment: string, trap: string}} rating is 0 if none was chosen
 */
export function ratingFrom(data) {
  return {
    rating: Number.parseInt(String(data.get("rating") ?? ""), 10) || 0,
    comment: String(data.get("comment") ?? "").trim(),
    trap: String(data.get("website") ?? "").trim(),
  };
}

/**
 * What is wrong with the answers, in words a person can act on; empty if all is well.
 * @param {{rating: number, comment: string}} a the answers
 * @returns {string[]}
 */
export function ratingProblems(a) {
  const found = [];
  if (!(a.rating >= 1 && a.rating <= 5)) found.push("Please choose from 1 to 5 stars.");
  if (a.comment.length > MAX_COMMENT) found.push(`Please keep the comment under ${MAX_COMMENT} characters.`);
  return found;
}

/**
 * The request body for the receiver: the module, the rating and the comment (if any).
 * @param {string} module the lesson's address on the site, e.g. data-engineering/series-1/01-...
 * @param {{rating: number, comment: string}} a the answers
 * @returns {URLSearchParams}
 */
export function ratingBody(module, a) {
  const body = new URLSearchParams({ module, rating: String(a.rating) });
  if (a.comment) body.append("comment", a.comment);
  return body;
}

/**
 * Wire one rating form: check, send, and thank the reader.
 * @param {HTMLFormElement} form the form; data-endpoint and data-module say where and what
 * @param {Function} send fetch, or a stand-in for tests
 */
export function mount(form, send = globalThis.fetch) {
  const status = form.querySelector(".form-status");
  const button = form.querySelector("button[type=submit]");
  const say = (text, kind) => {
    status.textContent = text; // only our own words and the receiver's message: never HTML
    status.className = `form-status ${kind}`;
  };
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const answers = ratingFrom(new FormData(form));
    const found = ratingProblems(answers);
    if (found.length) {
      say(found.join(" "), "error");
      return;
    }
    if (answers.trap) {
      say("Thank you.", "done");
      return;
    }
    button.disabled = true;
    say("Sending…", "note");
    try {
      const response = await send(form.dataset.endpoint, {
        method: "POST",
        body: ratingBody(form.dataset.module, answers),
      });
      const result = outcome(response.status, await response.text());
      if (!result.ok) throw new Error(result.message);
      form.querySelectorAll("fieldset, label.comment, button").forEach((el) => el.remove());
      say("Thank you. Every rating is read, and it shapes the next version of this module.", "done");
    } catch (error) {
      button.disabled = false;
      const reason = error instanceof Error && error.message ? `${error.message} ` : "";
      say(`Sorry, that did not go through. ${reason}Please try again in a minute.`, "error");
    }
  });
}

if (typeof document !== "undefined") {
  for (const form of document.querySelectorAll("form.rate")) mount(form);
}
