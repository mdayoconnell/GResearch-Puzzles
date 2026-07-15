#!/usr/bin/env python3
"""
Mean Sudoku Workbench
---------------------
A small Tkinter app for setting up and solving G-Research's "Mean Sudoku".

Features
- 9x9 Sudoku grid with thick 3x3 boundaries
- Setup mode:
    * enter permanent givens
    * toggle yellow cells
    * toggle circled cells
- Solve mode:
    * enter scratch answers
    * add/remove pencil marks
- Keyboard-first controls
- Conflict highlighting
- Save/load boards as JSON
- Copy the puzzle's 27-digit answer string (columns 1, 4, and 7)

Run:
    python mean_sudoku.py
"""

from __future__ import annotations

import json
import tkinter as tk
from dataclasses import dataclass, asdict
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import Optional


N = 9
CELL = 68
MARGIN = 16
GRID_PIXELS = N * CELL
CANVAS_SIZE = GRID_PIXELS + 2 * MARGIN

BG = "#17191d"
PANEL = "#23262d"
GRID_BG = "#f4f3ec"
YELLOW = "#e5ff43"
SELECT = "#9fd3ff"
CONFLICT = "#ffb2b2"
GIVEN_TEXT = "#111111"
SCRATCH_TEXT = "#155b8a"
NOTE_TEXT = "#56616c"
GRID_LINE = "#252525"


@dataclass
class Cell:
    given: int = 0
    scratch: int = 0
    yellow: bool = False
    circled: bool = False
    notes: list[int] | None = None

    def __post_init__(self) -> None:
        if self.notes is None:
            self.notes = []


class MeanSudokuApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Mean Sudoku Workbench")
        self.root.configure(bg=BG)
        self.root.resizable(False, False)

        self.cells = [[Cell() for _ in range(N)] for _ in range(N)]
        self.selected: Optional[tuple[int, int]] = (0, 0)

        self.mode = tk.StringVar(value="solve")     # setup / solve
        self.tool = tk.StringVar(value="number")   # number / yellow / circle / notes
        self.status = tk.StringVar(value="Ready")

        self._build_ui()
        self._bind_keys()
        self.redraw()

    # ---------- UI ----------

    def _build_ui(self) -> None:
        outer = tk.Frame(self.root, bg=BG, padx=16, pady=16)
        outer.pack()

        left = tk.Frame(outer, bg=BG)
        left.grid(row=0, column=0, sticky="n")

        right = tk.Frame(outer, bg=PANEL, padx=14, pady=14)
        right.grid(row=0, column=1, padx=(16, 0), sticky="ns")

        title = tk.Label(
            left,
            text="MEAN SUDOKU",
            bg=BG,
            fg="#f5f5f5",
            font=("Helvetica", 18, "bold"),
        )
        title.pack(anchor="w", pady=(0, 8))

        self.canvas = tk.Canvas(
            left,
            width=CANVAS_SIZE,
            height=CANVAS_SIZE,
            bg=BG,
            highlightthickness=0,
        )
        self.canvas.pack()
        self.canvas.bind("<Button-1>", self.on_left_click)
        self.canvas.bind("<Button-3>", self.on_right_click)
        self.canvas.bind("<Control-Button-1>", self.on_right_click)

        tk.Label(
            right,
            text="MODE",
            bg=PANEL,
            fg="#aeb5c0",
            font=("Helvetica", 10, "bold"),
        ).pack(anchor="w")

        self._radio(right, "Solve", "solve", self.mode, self._on_mode_change)
        self._radio(right, "Setup puzzle", "setup", self.mode, self._on_mode_change)

        self._separator(right)

        tk.Label(
            right,
            text="TOOL",
            bg=PANEL,
            fg="#aeb5c0",
            font=("Helvetica", 10, "bold"),
        ).pack(anchor="w")

        self._radio(right, "Number", "number", self.tool, self.redraw)
        self._radio(right, "Pencil marks", "notes", self.tool, self.redraw)
        self._radio(right, "Yellow", "yellow", self.tool, self.redraw)
        self._radio(right, "Circle", "circle", self.tool, self.redraw)

        self._separator(right)

        keypad = tk.Frame(right, bg=PANEL)
        keypad.pack(pady=(0, 10))
        for value in range(1, 10):
            button = tk.Button(
                keypad,
                text=str(value),
                width=3,
                height=1,
                font=("Helvetica", 13, "bold"),
                command=lambda v=value: self.enter_number(v),
            )
            button.grid(row=(value - 1) // 3, column=(value - 1) % 3, padx=3, pady=3)

        tk.Button(
            right,
            text="Clear selected",
            command=self.clear_selected,
            width=19,
        ).pack(pady=3)

        tk.Button(
            right,
            text="Clear all scratch",
            command=self.clear_scratch,
            width=19,
        ).pack(pady=3)

        self._separator(right)

        tk.Button(right, text="Save board…", command=self.save_board, width=19).pack(pady=3)
        tk.Button(right, text="Load board…", command=self.load_board, width=19).pack(pady=3)
        tk.Button(
            right,
            text="Copy 27-digit answer",
            command=self.copy_answer,
            width=19,
        ).pack(pady=3)

        self._separator(right)

        help_text = (
            "Keyboard\n"
            "1–9  enter/toggle\n"
            "Arrows  move\n"
            "Backspace  clear\n"
            "Y  toggle yellow\n"
            "C  toggle circle\n"
            "N  pencil marks\n"
            "S  solve/setup\n\n"
            "Mouse\n"
            "Click selects a cell.\n"
            "Right-click toggles yellow."
        )
        tk.Label(
            right,
            text=help_text,
            justify="left",
            bg=PANEL,
            fg="#d6dae0",
            font=("Helvetica", 10),
        ).pack(anchor="w")

        tk.Label(
            self.root,
            textvariable=self.status,
            bg=BG,
            fg="#b8c0ca",
            anchor="w",
            padx=18,
            pady=8,
        ).pack(fill="x")

    def _radio(
        self,
        parent: tk.Widget,
        text: str,
        value: str,
        variable: tk.StringVar,
        command,
    ) -> None:
        tk.Radiobutton(
            parent,
            text=text,
            value=value,
            variable=variable,
            command=command,
            bg=PANEL,
            fg="#eeeeee",
            selectcolor="#353a44",
            activebackground=PANEL,
            activeforeground="#ffffff",
            anchor="w",
            font=("Helvetica", 11),
        ).pack(fill="x", pady=1)

    @staticmethod
    def _separator(parent: tk.Widget) -> None:
        tk.Frame(parent, bg="#3a3f49", height=1).pack(fill="x", pady=12)

    # ---------- Drawing ----------

    def redraw(self) -> None:
        self.canvas.delete("all")
        conflicts = self.find_conflicts()

        x0 = y0 = MARGIN
        self.canvas.create_rectangle(
            x0,
            y0,
            x0 + GRID_PIXELS,
            y0 + GRID_PIXELS,
            fill=GRID_BG,
            outline="",
        )

        for r in range(N):
            for c in range(N):
                cell = self.cells[r][c]
                x1 = x0 + c * CELL
                y1 = y0 + r * CELL
                x2 = x1 + CELL
                y2 = y1 + CELL

                fill = GRID_BG
                if cell.yellow:
                    fill = YELLOW
                if (r, c) in conflicts:
                    fill = CONFLICT

                self.canvas.create_rectangle(x1, y1, x2, y2, fill=fill, outline="")

                if self.selected == (r, c):
                    self.canvas.create_rectangle(
                        x1 + 2,
                        y1 + 2,
                        x2 - 2,
                        y2 - 2,
                        outline=SELECT,
                        width=4,
                    )

                if cell.circled:
                    pad = 8
                    self.canvas.create_oval(
                        x1 + pad,
                        y1 + pad,
                        x2 - pad,
                        y2 - pad,
                        outline=GRID_LINE,
                        width=2,
                    )

                value = cell.given or cell.scratch
                if value:
                    self.canvas.create_text(
                        (x1 + x2) / 2,
                        (y1 + y2) / 2,
                        text=str(value),
                        fill=GIVEN_TEXT if cell.given else SCRATCH_TEXT,
                        font=("Helvetica", 26, "bold" if cell.given else "normal"),
                    )
                elif cell.notes:
                    for note in cell.notes:
                        nr = (note - 1) // 3
                        nc = (note - 1) % 3
                        self.canvas.create_text(
                            x1 + (nc + 0.5) * CELL / 3,
                            y1 + (nr + 0.5) * CELL / 3,
                            text=str(note),
                            fill=NOTE_TEXT,
                            font=("Helvetica", 10),
                        )

        for i in range(N + 1):
            width = 4 if i % 3 == 0 else 1
            x = x0 + i * CELL
            y = y0 + i * CELL
            self.canvas.create_line(x, y0, x, y0 + GRID_PIXELS, fill=GRID_LINE, width=width)
            self.canvas.create_line(x0, y, x0 + GRID_PIXELS, y, fill=GRID_LINE, width=width)

        mode_name = "SETUP" if self.mode.get() == "setup" else "SOLVE"
        tool_name = self.tool.get().upper()
        self.status.set(f"{mode_name} mode · {tool_name} tool · {len(conflicts)} conflicting cell(s)")

    # ---------- Input ----------

    def _bind_keys(self) -> None:
        self.root.bind("<Key>", self.on_key)
        self.root.bind("<BackSpace>", lambda _e: self.clear_selected())
        self.root.bind("<Delete>", lambda _e: self.clear_selected())
        self.root.bind("<Escape>", lambda _e: self._select_none())

    def _select_none(self) -> None:
        self.selected = None
        self.redraw()

    def cell_from_event(self, event: tk.Event) -> Optional[tuple[int, int]]:
        x = event.x - MARGIN
        y = event.y - MARGIN
        if not (0 <= x < GRID_PIXELS and 0 <= y < GRID_PIXELS):
            return None
        return int(y // CELL), int(x // CELL)

    def on_left_click(self, event: tk.Event) -> None:
        pos = self.cell_from_event(event)
        if pos is None:
            return
        self.selected = pos

        tool = self.tool.get()
        if tool == "yellow":
            self.toggle_yellow()
        elif tool == "circle":
            self.toggle_circle()
        else:
            self.redraw()

        self.canvas.focus_set()

    def on_right_click(self, event: tk.Event) -> None:
        pos = self.cell_from_event(event)
        if pos is None:
            return
        self.selected = pos
        self.toggle_yellow()

    def on_key(self, event: tk.Event) -> None:
        key = event.keysym.lower()

        if event.char in "123456789":
            self.enter_number(int(event.char))
            return

        movement = {
            "left": (0, -1),
            "right": (0, 1),
            "up": (-1, 0),
            "down": (1, 0),
        }
        if key in movement:
            self.move_selection(*movement[key])
        elif key == "y":
            self.toggle_yellow()
        elif key == "c":
            self.toggle_circle()
        elif key == "n":
            self.tool.set("notes" if self.tool.get() != "notes" else "number")
            self.redraw()
        elif key == "s":
            self.mode.set("setup" if self.mode.get() == "solve" else "solve")
            self._on_mode_change()

    def move_selection(self, dr: int, dc: int) -> None:
        if self.selected is None:
            self.selected = (0, 0)
        else:
            r, c = self.selected
            self.selected = ((r + dr) % N, (c + dc) % N)
        self.redraw()

    def enter_number(self, value: int) -> None:
        if self.selected is None:
            return

        r, c = self.selected
        cell = self.cells[r][c]

        if self.mode.get() == "setup":
            if self.tool.get() == "notes":
                messagebox.showinfo("Setup mode", "Pencil marks are only used in Solve mode.")
                return
            cell.given = 0 if cell.given == value else value
            cell.scratch = 0
            cell.notes.clear()
        else:
            if cell.given:
                self.status.set("That cell is a permanent given.")
                return
            if self.tool.get() == "notes":
                if value in cell.notes:
                    cell.notes.remove(value)
                else:
                    cell.notes.append(value)
                    cell.notes.sort()
                cell.scratch = 0
            else:
                cell.scratch = 0 if cell.scratch == value else value
                cell.notes.clear()

        self.redraw()

    def clear_selected(self) -> None:
        if self.selected is None:
            return

        r, c = self.selected
        cell = self.cells[r][c]

        if self.mode.get() == "setup":
            if self.tool.get() == "yellow":
                cell.yellow = False
            elif self.tool.get() == "circle":
                cell.circled = False
            else:
                cell.given = 0
        elif not cell.given:
            cell.scratch = 0
            cell.notes.clear()

        self.redraw()

    def toggle_yellow(self) -> None:
        if self.selected is None:
            return
        r, c = self.selected
        self.cells[r][c].yellow = not self.cells[r][c].yellow
        self.redraw()

    def toggle_circle(self) -> None:
        if self.selected is None:
            return
        r, c = self.selected
        self.cells[r][c].circled = not self.cells[r][c].circled
        self.redraw()

    def _on_mode_change(self) -> None:
        if self.mode.get() == "setup" and self.tool.get() == "notes":
            self.tool.set("number")
        self.redraw()

    # ---------- Sudoku checks ----------

    def value_at(self, r: int, c: int) -> int:
        cell = self.cells[r][c]
        return cell.given or cell.scratch

    def find_conflicts(self) -> set[tuple[int, int]]:
        conflicts: set[tuple[int, int]] = set()

        groups: list[list[tuple[int, int]]] = []
        groups.extend([[(r, c) for c in range(N)] for r in range(N)])
        groups.extend([[(r, c) for r in range(N)] for c in range(N)])

        for br in range(0, N, 3):
            for bc in range(0, N, 3):
                groups.append(
                    [(r, c) for r in range(br, br + 3) for c in range(bc, bc + 3)]
                )

        for group in groups:
            locations: dict[int, list[tuple[int, int]]] = {}
            for r, c in group:
                value = self.value_at(r, c)
                if value:
                    locations.setdefault(value, []).append((r, c))
            for positions in locations.values():
                if len(positions) > 1:
                    conflicts.update(positions)

        return conflicts

    # ---------- Files / export ----------

    def clear_scratch(self) -> None:
        if not messagebox.askyesno("Clear scratch", "Remove all scratch entries and pencil marks?"):
            return
        for row in self.cells:
            for cell in row:
                cell.scratch = 0
                cell.notes.clear()
        self.redraw()

    def save_board(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Save Mean Sudoku board",
            defaultextension=".json",
            filetypes=[("JSON board", "*.json"), ("All files", "*.*")],
        )
        if not path:
            return

        payload = {
            "format": "mean-sudoku-workbench-v1",
            "cells": [[asdict(cell) for cell in row] for row in self.cells],
        }

        try:
            Path(path).write_text(json.dumps(payload, indent=2), encoding="utf-8")
            self.status.set(f"Saved {Path(path).name}")
        except OSError as exc:
            messagebox.showerror("Save failed", str(exc))

    def load_board(self) -> None:
        path = filedialog.askopenfilename(
            title="Load Mean Sudoku board",
            filetypes=[("JSON board", "*.json"), ("All files", "*.*")],
        )
        if not path:
            return

        try:
            payload = json.loads(Path(path).read_text(encoding="utf-8"))
            raw_cells = payload["cells"]
            if len(raw_cells) != N or any(len(row) != N for row in raw_cells):
                raise ValueError("Board must contain exactly 9 rows of 9 cells.")

            loaded: list[list[Cell]] = []
            for row in raw_cells:
                loaded.append(
                    [
                        Cell(
                            given=int(raw.get("given", 0)),
                            scratch=int(raw.get("scratch", 0)),
                            yellow=bool(raw.get("yellow", False)),
                            circled=bool(raw.get("circled", False)),
                            notes=[int(n) for n in raw.get("notes", [])],
                        )
                        for raw in row
                    ]
                )

            self.cells = loaded
            self.selected = (0, 0)
            self.redraw()
            self.status.set(f"Loaded {Path(path).name}")
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
            messagebox.showerror("Load failed", str(exc))

    def copy_answer(self) -> None:
        columns = (0, 3, 6)
        digits: list[str] = []

        # "reading the first, fourth and seventh columns from top to bottom"
        for c in columns:
            for r in range(N):
                value = self.value_at(r, c)
                if not value:
                    messagebox.showwarning(
                        "Incomplete board",
                        "All cells in columns 1, 4, and 7 must be filled first.",
                    )
                    return
                digits.append(str(value))

        answer = "".join(digits)
        self.root.clipboard_clear()
        self.root.clipboard_append(answer)
        self.status.set(f"Copied: {answer}")
        messagebox.showinfo("Answer copied", answer)


def main() -> None:
    root = tk.Tk()
    MeanSudokuApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
