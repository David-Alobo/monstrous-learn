// The interactive "big picture" diagram on a course page.
//
// The page already holds every step's details as plain HTML (so it reads without JavaScript);
// this script turns the steps into buttons that show one step's details at a time, keeps the
// chosen step in the address (#step-ingest) so it can be shared, and lets the arrow keys move
// between steps. The logic is in small pure functions, tested with Vitest.

/**
 * The step to move to after a key press.
 * @param {string[]} ids every step, in order
 * @param {string} current the step shown now
 * @param {string} key the key pressed
 * @returns {string|null} the step to show, or null if the key does not move
 */
export function moveTo(ids, current, key) {
  const i = ids.indexOf(current);
  if (i < 0 || ids.length === 0) return null;
  switch (key) {
    case "ArrowRight":
    case "ArrowDown":
      return ids[(i + 1) % ids.length];
    case "ArrowLeft":
    case "ArrowUp":
      return ids[(i - 1 + ids.length) % ids.length];
    case "Home":
      return ids[0];
    case "End":
      return ids[ids.length - 1];
    default:
      return null;
  }
}

/**
 * The step named in the address, if it is one of ours.
 * @param {string} hash location.hash, e.g. "#step-ingest"
 * @param {string[]} ids every step
 * @param {string} fallback the step to show otherwise
 * @returns {string}
 */
export function fromHash(hash, ids, fallback) {
  const id = decodeURIComponent((hash || "").replace(/^#step-/, ""));
  return ids.includes(id) ? id : fallback;
}

/**
 * Show one step: mark its button, show its panel, hide the others.
 * @param {HTMLElement} root the diagram
 * @param {string} id the step to show
 */
export function show(root, id) {
  for (const b of root.querySelectorAll("[data-step]")) {
    const on = b.dataset.step === id;
    b.setAttribute("aria-pressed", String(on));
    b.tabIndex = on ? 0 : -1;
  }
  for (const p of root.querySelectorAll("[data-panel]")) {
    p.hidden = p.dataset.panel !== id;
  }
}

/**
 * Wire up a diagram on the page.
 * @param {HTMLElement} root the diagram
 * @param {Window} win the window (passed in so tests can use a fake one)
 */
export function mount(root, win = window) {
  const buttons = [...root.querySelectorAll("[data-step]")];
  const ids = buttons.map((b) => b.dataset.step);
  if (ids.length === 0) return;
  root.classList.add("live");
  const choose = (id, focus = false) => {
    show(root, id);
    win.history.replaceState(null, "", `#step-${id}`);
    if (focus) root.querySelector(`[data-step="${id}"]`).focus();
  };
  for (const b of buttons) {
    b.addEventListener("click", () => choose(b.dataset.step));
    b.addEventListener("keydown", (e) => {
      const next = moveTo(ids, b.dataset.step, e.key);
      if (next) {
        e.preventDefault();
        choose(next, true);
      }
    });
  }
  show(root, fromHash(win.location.hash, ids, ids[0]));
}

if (typeof document !== "undefined") {
  for (const root of document.querySelectorAll(".journey")) mount(root);
}
