#!/usr/bin/env python3
"""
Greyscale Gambit Explorer
-------------------------
A small Tkinter workbench for experimenting with G-Research's
"Greyscale Gambit" chess-position puzzle.

Features
- 8x8 chessboard
- Setup mode for placing/removing grey pieces
- Colour mode for assigning each placed piece White, Black, or Grey
- Toggle which displayed corner is a1
- Board-square colours update automatically
- Click pieces to cycle their colour
- Right-click to remove a piece
- Clear/reset controls

Run:
    python grayscale_gambit_explorer.py
"""

from __future__ import annotations

import tkinter as tk
from dataclasses import dataclass
from tkinter import messagebox
from typing import Optional


BOARD_SIZE = 8
CELL = 72
MARGIN = 18
BOARD_PIXELS = BOARD_SIZE * CELL
CANVAS_SIZE = BOARD_PIXELS + 2 * MARGIN

BG = "#181a1f"
PANEL = "#252932"
LIGHT_SQUARE = "#f1f1ee"
DARK_SQUARE = "#8e939b"
UNKNOWN_SQUARE = "#b7bac0"
SELECT = "#4aa3ff"
WHITE_PIECE = "#ffffff"
BLACK_PIECE = "#111111"
GREY_PIECE = "#9da1a8"
OUTLINE = "#2b2b2b"
PIECE_STROKE_WIDTH = 2
TEXT = "#eeeeee"
MUTED = "#aeb4bf"


PIECE_SYMBOLS = {
    "K": "♔",
    "Q": "♕",
    "R": "♖",
    "B": "♗",
    "N": "♘",
    "P": "♙",
}

PIECE_NAMES = {
    "K": "King",
    "Q": "Queen",
    "R": "Rook",
    "B": "Bishop",
    "N": "Knight",
    "P": "Pawn",
}


@dataclass
class Piece:
    kind: str
    colour: str = "grey"  # grey / white / black


class GreyscaleGambitExplorer:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Greyscale Gambit Explorer")
        self.root.configure(bg=BG)
        self.root.resizable(False, False)

        self.board: list[list[Optional[Piece]]] = [
            [None for _ in range(BOARD_SIZE)] for _ in range(BOARD_SIZE)
        ]

        self.mode = tk.StringVar(value="setup")  # setup / colour
        self.selected_piece = tk.StringVar(value="K")
        self.a1_corner = tk.StringVar(value="indeterminate")
        self.selected_square: Optional[tuple[int, int]] = None
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

        tk.Label(
            left,
            text="GREYSCALE GAMBIT",
            bg=BG,
            fg=TEXT,
            font=("Helvetica", 18, "bold"),
        ).pack(anchor="w", pady=(0, 8))

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

        self._section_label(right, "MODE")
        self._radio(right, "Setup pieces", "setup", self.mode, self.redraw)
        self._radio(right, "Assign colours", "colour", self.mode, self.redraw)

        self._separator(right)

        self._section_label(right, "PIECE")
        piece_grid = tk.Frame(right, bg=PANEL)
        piece_grid.pack(anchor="w", pady=(3, 0))

        for i, kind in enumerate(("K", "Q", "R", "B", "N", "P")):
            button = tk.Radiobutton(
                piece_grid,
                text=f"{PIECE_SYMBOLS[kind]}  {PIECE_NAMES[kind]}",
                value=kind,
                variable=self.selected_piece,
                indicatoron=False,
                width=12,
                bg="#343944",
                fg=TEXT,
                selectcolor="#4b5361",
                activebackground="#404753",
                activeforeground="#ffffff",
                font=("Helvetica", 11),
                padx=4,
                pady=5,
            )
            button.grid(row=i // 2, column=i % 2, padx=3, pady=3, sticky="ew")

        self._separator(right)

        self._section_label(right, "A1 CORNER")
        for text, value in (
            ("Indeterminate", "indeterminate"),
            ("Bottom-left", "bottom-left"),
            ("Bottom-right", "bottom-right"),
            ("Top-left", "top-left"),
            ("Top-right", "top-right"),
        ):
            self._radio(right, text, value, self.a1_corner, self.redraw)

        self._separator(right)

        tk.Button(
            right,
            text="Cycle selected colour",
            width=21,
            command=self.cycle_selected_colour,
        ).pack(pady=3)

        tk.Button(
            right,
            text="Remove selected piece",
            width=21,
            command=self.remove_selected,
        ).pack(pady=3)

        tk.Button(
            right,
            text="Reset all to grey",
            width=21,
            command=self.reset_colours,
        ).pack(pady=3)

        tk.Button(
            right,
            text="Clear board",
            width=21,
            command=self.clear_board,
        ).pack(pady=3)

        self._separator(right)

        help_text = (
            "Setup mode\n"
            "Left-click: place/replace piece\n"
            "Right-click: remove piece\n\n"
            "Assign colours mode\n"
            "Left-click: grey → white → black\n"
            "Right-click: remove piece\n\n"
            "Keyboard\n"
            "K Q R B N P: choose piece\n"
            "Space: cycle selected colour\n"
            "Delete: remove selected piece\n"
            "M: toggle mode"
        )

        tk.Label(
            right,
            text=help_text,
            justify="left",
            bg=PANEL,
            fg=MUTED,
            font=("Helvetica", 10),
        ).pack(anchor="w")

        tk.Label(
            self.root,
            textvariable=self.status,
            bg=BG,
            fg=MUTED,
            anchor="w",
            padx=18,
            pady=8,
        ).pack(fill="x")

    @staticmethod
    def _section_label(parent: tk.Widget, text: str) -> None:
        tk.Label(
            parent,
            text=text,
            bg=PANEL,
            fg=MUTED,
            font=("Helvetica", 10, "bold"),
        ).pack(anchor="w")

    @staticmethod
    def _separator(parent: tk.Widget) -> None:
        tk.Frame(parent, bg="#3a3f49", height=1).pack(fill="x", pady=12)

    @staticmethod
    def _radio(
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
            fg=TEXT,
            selectcolor="#353a44",
            activebackground=PANEL,
            activeforeground="#ffffff",
            anchor="w",
            font=("Helvetica", 11),
        ).pack(fill="x", pady=1)

    # ---------- Board coordinates ----------

    def square_name(self, row: int, col: int) -> str:
        corner = self.a1_corner.get()
        if corner == "indeterminate":
            return ""

        if "left" in corner:
            file_index = col
        else:
            file_index = 7 - col

        if "bottom" in corner:
            rank_index = 7 - row
        else:
            rank_index = row

        return f"{chr(ord('a') + file_index)}{rank_index + 1}"

    def is_dark_square(self, row: int, col: int) -> Optional[bool]:
        name = self.square_name(row, col)
        if not name:
            return None

        file_index = ord(name[0]) - ord("a") + 1
        rank = int(name[1])
        return (file_index + rank) % 2 == 0

    # ---------- Drawing ----------

    def redraw(self) -> None:
        self.canvas.delete("all")

        for row in range(BOARD_SIZE):
            for col in range(BOARD_SIZE):
                x1 = MARGIN + col * CELL
                y1 = MARGIN + row * CELL
                x2 = x1 + CELL
                y2 = y1 + CELL

                square_colour = self.is_dark_square(row, col)
                if square_colour is None:
                    fill = UNKNOWN_SQUARE
                else:
                    fill = DARK_SQUARE if square_colour else LIGHT_SQUARE
                self.canvas.create_rectangle(x1, y1, x2, y2, fill=fill, outline="")

                if self.selected_square == (row, col):
                    self.canvas.create_rectangle(
                        x1 + 2,
                        y1 + 2,
                        x2 - 2,
                        y2 - 2,
                        outline=SELECT,
                        width=4,
                    )

                piece = self.board[row][col]
                if piece is not None:
                    colour = {
                        "white": WHITE_PIECE,
                        "black": BLACK_PIECE,
                        "grey": GREY_PIECE,
                    }[piece.colour]

                    piece_x = (x1 + x2) / 2
                    piece_y = (y1 + y2) / 2 - 2
                    stroke_colour = {
                        "white": "#555555",
                        "black": "#eeeeee",
                        "grey": "#555960",
                    }[piece.colour]

                    for dx, dy in (
                        (-PIECE_STROKE_WIDTH, 0),
                        (PIECE_STROKE_WIDTH, 0),
                        (0, -PIECE_STROKE_WIDTH),
                        (0, PIECE_STROKE_WIDTH),
                        (-PIECE_STROKE_WIDTH, -PIECE_STROKE_WIDTH),
                        (-PIECE_STROKE_WIDTH, PIECE_STROKE_WIDTH),
                        (PIECE_STROKE_WIDTH, -PIECE_STROKE_WIDTH),
                        (PIECE_STROKE_WIDTH, PIECE_STROKE_WIDTH),
                    ):
                        self.canvas.create_text(
                            piece_x + dx,
                            piece_y + dy,
                            text=PIECE_SYMBOLS[piece.kind],
                            fill=stroke_colour,
                            font=("DejaVu Sans", 44),
                        )

                    self.canvas.create_text(
                        piece_x,
                        piece_y,
                        text=PIECE_SYMBOLS[piece.kind],
                        fill=colour,
                        font=("DejaVu Sans", 44),
                    )

                    if piece.colour == "white":
                        outline = OUTLINE
                    elif piece.colour == "black":
                        outline = "#dddddd"
                    else:
                        outline = "#454950"

                    self.canvas.create_text(
                        x1 + 6,
                        y1 + 5,
                        text=piece.colour[0].upper(),
                        anchor="nw",
                        fill=outline,
                        font=("Helvetica", 8, "bold"),
                    )

                square_name = self.square_name(row, col)
                if square_name:
                    self.canvas.create_text(
                        x1 + 5,
                        y2 - 4,
                        text=square_name,
                        anchor="sw",
                        fill=(
                            "#e1e3e6"
                            if self.is_dark_square(row, col)
                            else "#555a63"
                        ),
                        font=("Helvetica", 8),
                    )

        for i in range(BOARD_SIZE + 1):
            x = MARGIN + i * CELL
            y = MARGIN + i * CELL
            self.canvas.create_line(
                x,
                MARGIN,
                x,
                MARGIN + BOARD_PIXELS,
                fill="#26282d",
                width=2 if i in (0, BOARD_SIZE) else 1,
            )
            self.canvas.create_line(
                MARGIN,
                y,
                MARGIN + BOARD_PIXELS,
                y,
                fill="#26282d",
                width=2 if i in (0, BOARD_SIZE) else 1,
            )

        piece_count = sum(
            1 for row in self.board for piece in row if piece is not None
        )
        mode_name = "SETUP" if self.mode.get() == "setup" else "COLOUR"
        corner_status = self.a1_corner.get()
        if corner_status == "indeterminate":
            orientation_text = "a1 indeterminate"
        else:
            orientation_text = f"a1 at {corner_status}"

        self.status.set(
            f"{mode_name} mode · {orientation_text} · {piece_count} piece(s)"
        )

    # ---------- Input ----------

    def _bind_keys(self) -> None:
        self.root.bind("<Key>", self.on_key)
        self.root.bind("<space>", lambda _event: self.cycle_selected_colour())
        self.root.bind("<BackSpace>", lambda _event: self.remove_selected())
        self.root.bind("<Delete>", lambda _event: self.remove_selected())

    def cell_from_event(self, event: tk.Event) -> Optional[tuple[int, int]]:
        x = event.x - MARGIN
        y = event.y - MARGIN
        if not (0 <= x < BOARD_PIXELS and 0 <= y < BOARD_PIXELS):
            return None
        return int(y // CELL), int(x // CELL)

    def on_left_click(self, event: tk.Event) -> None:
        pos = self.cell_from_event(event)
        if pos is None:
            return

        self.selected_square = pos
        row, col = pos

        if self.mode.get() == "setup":
            self.board[row][col] = Piece(self.selected_piece.get(), "grey")
        else:
            piece = self.board[row][col]
            if piece is not None:
                piece.colour = self.next_colour(piece.colour)

        self.redraw()
        self.canvas.focus_set()

    def on_right_click(self, event: tk.Event) -> None:
        pos = self.cell_from_event(event)
        if pos is None:
            return

        self.selected_square = pos
        row, col = pos
        self.board[row][col] = None
        self.redraw()

    def on_key(self, event: tk.Event) -> None:
        key = event.keysym.lower()

        if key in {"k", "q", "r", "b", "n", "p"}:
            self.selected_piece.set(key.upper())
            self.mode.set("setup")
            self.redraw()
        elif key == "m":
            self.mode.set("colour" if self.mode.get() == "setup" else "setup")
            self.redraw()

    @staticmethod
    def next_colour(colour: str) -> str:
        return {
            "grey": "white",
            "white": "black",
            "black": "grey",
        }[colour]

    # ---------- Actions ----------

    def cycle_selected_colour(self) -> None:
        if self.selected_square is None:
            return

        row, col = self.selected_square
        piece = self.board[row][col]
        if piece is None:
            self.status.set("No piece is selected.")
            return

        piece.colour = self.next_colour(piece.colour)
        self.redraw()

    def remove_selected(self) -> None:
        if self.selected_square is None:
            return

        row, col = self.selected_square
        self.board[row][col] = None
        self.redraw()

    def reset_colours(self) -> None:
        for row in self.board:
            for piece in row:
                if piece is not None:
                    piece.colour = "grey"
        self.redraw()

    def clear_board(self) -> None:
        if not messagebox.askyesno("Clear board", "Remove every piece from the board?"):
            return

        self.board = [
            [None for _ in range(BOARD_SIZE)] for _ in range(BOARD_SIZE)
        ]
        self.selected_square = None
        self.redraw()


def main() -> None:
    root = tk.Tk()
    GreyscaleGambitExplorer(root)
    root.mainloop()


if __name__ == "__main__":
    main()
