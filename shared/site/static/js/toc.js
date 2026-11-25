// The contents list beside a lesson ("In this lesson"): the section being read is shown in purple.
//
// The list is ordinary links, and works without this script. The script watches where the reader
// is and marks the link of the current section with the class "active" and aria-current="true"
// (so screen readers announce it too).

export const OFFSET = 120; // pixels below the top of the window where a section counts as reached

/**
 * The section being read: the last one whose heading has scrolled above the reading line.
 * @param {{id: string, top: number}[]} headings each section's id and its heading's distance from
 *   the top of the window, in page order
 * @param {number} [offset] how far below the top of the window the reading line is
 * @param {boolean} [atBottom] whether the page is scrolled to its end (the last section counts as
 *   read then, even if its heading never reaches the line)
 * @returns {string | null} the id, or null before the first section
 */
export function activeSection(headings, offset = OFFSET, atBottom = false) {
  if (headings.length === 0) return null;
  if (atBottom) return headings[headings.length - 1].id;
  let active = null;
  for (const heading of headings) {
    if (heading.top <= offset) active = heading.id;
    else break;
  }
  return active;
}

/**
 * Wire a contents list to the page.
 * @param {HTMLElement} list the contents list (its links point to #section-id)
 * @param {Window} win the window it lives in
 */
export function mount(list, win = window) {
  const links = [...list.querySelectorAll('a[href^="#"]')];
  const targets = links
    .map((link) => win.document.getElementById(decodeURIComponent(link.hash.slice(1))))
    .filter(Boolean);
  let current = null;
  const update = () => {
    const headings = targets.map((el) => ({ id: el.id, top: el.getBoundingClientRect().top }));
    const page = win.document.documentElement;
    const atBottom = win.innerHeight + win.scrollY >= page.scrollHeight - 2;
    const id = activeSection(headings, OFFSET, atBottom);
    if (id === current) return;
    current = id;
    for (const link of links) {
      const on = link.hash.slice(1) === id;
      link.classList.toggle("active", on);
      if (on) link.setAttribute("aria-current", "true");
      else link.removeAttribute("aria-current");
    }
  };
  let queued = false;
  win.addEventListener(
    "scroll",
    () => {
      if (queued) return;
      queued = true; // at most once per frame, however fast the reader scrolls
      win.requestAnimationFrame(() => {
        queued = false;
        update();
      });
    },
    { passive: true },
  );
  win.addEventListener("resize", update);
  update();
}

if (typeof document !== "undefined") {
  const list = document.querySelector(".toc .contents");
  if (list) mount(list);
}
