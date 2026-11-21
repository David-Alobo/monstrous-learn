// The "back to top" button on every course page, like the one on monstrous.com.ng's other pages.
//
// The page holds an ordinary link to the top (#top), always visible if this script does not run.
// The script hides it until the reader has scrolled down a little, and glides back to the top when
// it is clicked (or jumps, for readers who ask their device for less motion).

export const SHOW_AFTER = 400; // pixels scrolled before the button appears

/**
 * Whether the button should show.
 * @param {number} scrolled how far the page is scrolled, in pixels
 * @param {number} [after] the distance at which it appears
 * @returns {boolean}
 */
export function shouldShow(scrolled, after = SHOW_AFTER) {
  return scrolled > after;
}

/**
 * Wire the button to the page.
 * @param {HTMLAnchorElement} button the link to the top
 * @param {Window} win the window it lives in
 */
export function mount(button, win = window) {
  button.classList.add("auto"); // from now on it is hidden until the reader scrolls
  const update = () => button.classList.toggle("show", shouldShow(win.scrollY));
  win.addEventListener("scroll", update, { passive: true });
  update();
  button.addEventListener("click", (event) => {
    event.preventDefault();
    const still = win.matchMedia("(prefers-reduced-motion: reduce)").matches;
    win.scrollTo({ top: 0, behavior: still ? "auto" : "smooth" });
    win.document.getElementById("top")?.focus({ preventScroll: true });
  });
}

if (typeof document !== "undefined") {
  const button = document.querySelector(".to-top");
  if (button) mount(button);
}
