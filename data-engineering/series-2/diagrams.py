"""Drawing helpers for Series 2's diagrams: boxes, arrows and labels as SVG, in the course's style.

Each module's figures.py draws its diagrams with these, so that every figure of the series looks
the same: the course's colours, rounded boxes, grey arrows, sans-serif text on white.

    from diagrams import Diagram

    d = Diagram(600, 200)
    d.box(20, 40, 150, 60, "raw", ["the files, unchanged"], kind="raw")
    d.box(260, 40, 150, 60, "staging", kind="stage")
    d.arrow((170, 70), (260, 70), "clean")
    d.save("figures/example.svg")
"""

from __future__ import annotations

from html import escape
from pathlib import Path

# the course's colours (the same as Series 1's figurekit), and Okabe and Ito's colours for states
INK, VIOLET, CYAN, MUTED = "#1d2130", "#7c5cf0", "#0e9fb5", "#8b91a1"
LIGHT = "#efeafd"  # a pale violet fill
GREEN, ORANGE, RED = "#009E73", "#E69F00", "#D55E00"  # passed / warned / failed
FONT = 'font-family="sans-serif"'

# box kinds: (fill, stroke, title colour, dashed?)
KINDS = {
    "raw": ("#ffffff", MUTED, INK, True),  # something outside the warehouse: files, a source
    "stage": (LIGHT, VIOLET, INK, False),  # a step or a staging table
    "mart": (VIOLET, VIOLET, "#ffffff", False),  # what people read
    "tool": ("#ffffff", CYAN, INK, False),  # a tool, a seed, a helper
    "plain": ("#ffffff", MUTED, INK, False),
    "ok": ("#e6f5f0", GREEN, INK, False),
    "warn": ("#fdf3e0", ORANGE, INK, False),
    "fail": ("#fbe9e1", RED, INK, False),
    "skip": ("#f2f3f5", MUTED, MUTED, True),
}


class Diagram:
    """An SVG drawing, built up part by part and saved as a file."""

    def __init__(self, width: float, height: float) -> None:
        """Start an empty drawing.

        Args:
            width: Its width, in pixels.
            height: Its height, in pixels.
        """
        self.width, self.height = width, height
        self.parts: list[str] = [f'<rect width="{width}" height="{height}" fill="#ffffff"/>']

    def text(self, x: float, y: float, label: str, size: float = 13, colour: str = INK,
             anchor: str = "start", weight: str = "normal", italic: bool = False) -> None:  # fmt: skip
        """Write a line of text.

        Args:
            x: Horizontal position.
            y: Baseline.
            label: The text.
            size: Font size in pixels.
            colour: Its colour.
            anchor: "start", "middle" or "end".
            weight: "normal" or "600" (bold).
            italic: Whether to slant it.
        """
        style = ' font-style="italic"' if italic else ""
        self.parts.append(
            f'<text x="{x}" y="{y}" {FONT} font-size="{size}" fill="{colour}" '
            f'text-anchor="{anchor}" font-weight="{weight}"{style}>{escape(label)}</text>'
        )

    def box(self, x: float, y: float, w: float, h: float, title: str,
            lines: list[str] | None = None, kind: str = "stage", size: float = 14) -> tuple:  # fmt: skip
        """A rounded box with a title and, under it, smaller lines of text.

        Args:
            x: Left edge.
            y: Top edge.
            w: Width.
            h: Height.
            title: The title, centred.
            lines: Smaller lines under the title.
            kind: One of KINDS: what the box stands for.
            size: The title's font size.

        Returns:
            The box's (left, top, right, bottom), for placing arrows.
        """
        fill, stroke, colour, dashed = KINDS[kind]
        dash = ' stroke-dasharray="5 3"' if dashed else ""
        self.parts.append(
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="10" fill="{fill}" '
            f'stroke="{stroke}" stroke-width="2"{dash}/>'
        )
        lines = lines or []
        top = y + h / 2 - (len(lines) * 16) / 2 + (5 if not lines else 0)
        self.text(x + w / 2, top + (4 if lines else 0), title, size, colour, "middle", "600")
        sub = "#ece8fd" if kind == "mart" else ("#5b6170" if kind != "skip" else MUTED)
        for k, line in enumerate(lines):
            self.text(x + w / 2, top + 20 + 16 * k, line, 12, sub, "middle")
        return x, y, x + w, y + h

    def arrow(self, start: tuple[float, float], end: tuple[float, float], label: str = "",
              colour: str = MUTED, dashed: bool = False, bend: float = 0.0,
              label_dy: float = -7) -> None:  # fmt: skip
        """An arrow from one point to another, straight or bent, with an optional label.

        Args:
            start: (x, y) where it starts.
            end: (x, y) where its head is.
            label: Text at its middle.
            colour: Its colour.
            dashed: Whether to dash it.
            bend: How far its middle bows sideways (0 for straight), in pixels.
            label_dy: How far above (negative) or below its middle the label sits.
        """
        (x1, y1), (x2, y2) = start, end
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        length = max(((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5, 1)
        nx, ny = -(y2 - y1) / length, (x2 - x1) / length  # the perpendicular, for the bend
        cx, cy = mx + nx * bend, my + ny * bend
        # stop the line short of the head, along the curve's last direction
        dx, dy = x2 - cx, y2 - cy
        d = max((dx**2 + dy**2) ** 0.5, 1)
        ux, uy = dx / d, dy / d
        hx, hy = x2 - ux * 9, y2 - uy * 9
        dash = ' stroke-dasharray="5 4"' if dashed else ""
        self.parts.append(
            f'<path d="M{x1} {y1} Q{cx} {cy} {hx} {hy}" fill="none" stroke="{colour}" '
            f'stroke-width="2"{dash}/>'
        )
        px, py = -uy * 5, ux * 5
        self.parts.append(
            f'<path d="M{x2} {y2} L{hx + px} {hy + py} L{hx - px} {hy - py} z" fill="{colour}"/>'
        )
        if label:
            lx, ly = (x1 + 2 * cx + x2) / 4, (y1 + 2 * cy + y2) / 4  # the curve's middle
            self.text(lx, ly + label_dy, label, 12, MUTED if colour == MUTED else colour, "middle")

    def line(self, start: tuple[float, float], end: tuple[float, float], colour: str = MUTED,
             width: float = 1.5, dashed: bool = False) -> None:  # fmt: skip
        """A plain line.

        Args:
            start: (x, y).
            end: (x, y).
            colour: Its colour.
            width: Its width.
            dashed: Whether to dash it.
        """
        dash = ' stroke-dasharray="4 4"' if dashed else ""
        self.parts.append(
            f'<line x1="{start[0]}" y1="{start[1]}" x2="{end[0]}" y2="{end[1]}" '
            f'stroke="{colour}" stroke-width="{width}"{dash}/>'
        )

    def dot(self, x: float, y: float, r: float, colour: str, label: str = "") -> None:
        """A filled circle, with an optional label in it.

        Args:
            x: Centre.
            y: Centre.
            r: Radius.
            colour: Its fill.
            label: Text in it (white).
        """
        self.parts.append(f'<circle cx="{x}" cy="{y}" r="{r}" fill="{colour}"/>')
        if label:
            self.text(x, y + 4, label, 11, "#ffffff", "middle", "600")

    def legend(self, x: float, y: float, items: list[tuple[str, str]], gap: float = 190) -> None:
        """A row of small boxes with captions: what each kind of box means.

        Args:
            x: Left edge.
            y: Baseline.
            items: (kind, caption) for each.
            gap: Horizontal space for each item.
        """
        for k, (kind, caption) in enumerate(items):
            fill, stroke, _, dashed = KINDS[kind]
            dash = ' stroke-dasharray="4 2"' if dashed else ""
            left = x + k * gap
            self.parts.append(
                f'<rect x="{left}" y="{y - 11}" width="20" height="13" rx="3" fill="{fill}" '
                f'stroke="{stroke}" stroke-width="2"{dash}/>'
            )
            self.text(left + 28, y, caption, 12, MUTED)

    def save(self, path: str | Path) -> None:
        """Write the drawing as an SVG file (its folder is made if needed).

        Args:
            path: The file.
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        body = "".join(self.parts)
        path.write_text(
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {self.width} {self.height}" '
            f'width="{self.width}" height="{self.height}">{body}</svg>',
            encoding="utf-8",
        )
