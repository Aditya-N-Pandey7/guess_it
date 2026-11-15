"""
gui_main.py - [Level 3 Agent] The UI/UX & Presentation Layer (Tkinter & PIL)
Project: "Who's That Animal?" – Heavy DSA & Automata Desktop Game

Responsibilities:
1. Dynamic Asset & Silhouette Generation (Pillow / PIL):
   - Procedural vector-style RGBA PNG sprite generator for 15+ animals in `assets/animals/`
     (creates detailed, recognizable transparent animal illustrations on first launch).
   - Runtime Alpha-Channel Silhouette Conversion (`create_silhouette` / `generate_silhouette_from_png`):
     Loads standard transparent PNGs at runtime, iterates over the RGBA pixels / alpha channel,
     and converts all non-transparent pixels (alpha > 0) to solid black `#000000` `(0, 0, 0, alpha)`
     while preserving transparent background `(0, 0, 0, 0)`. Never uses pre-made shadow files.
2. Event-Driven Tkinter GUI (`WhosThatAnimalGUI` / `WhosThatAnimalApp`):
   - Clean integration of `pack()` and `grid()` geometry managers.
   - Real-time DFA State & Transition status bar: delta(q, sigma) -> q'.
   - Main Menu with Max-Heap Leaderboard (O(1) top highlight + Top-K) and AVL Tree MMR Matchmaking rankings.
   - Single Player Survival Mode (3 Lives, 30s `.after()` non-blocking timer, DAG BFS hints,
     100/75/50/0 dynamic point schedule, single `<Return>`-bound Entry with Levenshtein NFA fuzzy match).
   - Multiplayer Split-Screen Competitive Mode (10 Rounds, 60s `.after()` non-blocking timer,
     3-column `grid()` split screen with independent P1 & P2 `<Return>`-bound Entry widgets and
     atomic race-condition lockout).
"""

from __future__ import annotations

import io
import json
import math
import os
import random
import secrets
import socket
import sys
import threading
import time
import tkinter as tk
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from tkinter import ttk, messagebox
from typing import Any, Callable, Dict, List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFilter, ImageTk

import dsa_engine
import game_logic
from game_logic import (
    DSAEngineBundle,
    GameDFA,
    GameEvent,
    GameState,
    MultiplayerController,
    SinglePlayerController,
    create_default_dsa_bundle,
)


# ============================================================================
# 1. DYNAMIC ASSET & RUNTIME ALPHA-CHANNEL SILHOUETTE GENERATOR (Pillow / PIL)
# ============================================================================

class SilhouetteGenerator:
    """
    Manages high-realism transparent animal PNG assets in `assets/animals/` (rendered
    with 2x supersampling 640x640 -> 320x320 LANCZOS anti-aliasing) and performs
    runtime pixel-by-pixel alpha-channel conversion to generate solid black
    (`#000000`) mystery silhouettes on the fly.
    """

    DEFAULT_CANVAS_SIZE: Tuple[int, int] = (320, 320)
    SUPERSAMPLE_SIZE: Tuple[int, int] = (640, 640)
    ASSET_VERSION_MARKER: str = ".version_v2_realistic"

    # Canonical slugs for all 17 supported animals across DAG & tests
    ANIMAL_SLUGS: List[str] = [
        "african_elephant",
        "bengal_tiger",
        "emperor_penguin",
        "bald_eagle",
        "king_cobra",
        "komodo_dragon",
        "red_eyed_tree_frog",
        "great_white_shark",
        "giant_panda",
        "platypus",
        "red_kangaroo",
        "bottlenose_dolphin",
        "snowy_owl",
        "panther_chameleon",
        "veiled_chameleon",
        "axolotl",
        "clownfish",
    ]

    def __init__(self, assets_dir: Optional[str] = None, force_regenerate: bool = False) -> None:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        self.assets_dir: str = assets_dir or os.path.join(base_dir, "assets", "animals")
        os.makedirs(self.assets_dir, exist_ok=True)
        self._photo_cache: Dict[Tuple[str, Tuple[int, int], bool], ImageTk.PhotoImage] = {}
        self._png_bytes_cache: Dict[Tuple[str, Tuple[int, int], bool], bytes] = {}
        self.ensure_all_assets(force_regenerate=force_regenerate)

    # ------------------------------------------------------------------
    # Runtime Alpha-Channel Silhouette Conversion (Core PIL Requirement)
    # ------------------------------------------------------------------
    @staticmethod
    def generate_silhouette_from_png(
        image_path: str,
        size: Tuple[int, int] = (260, 260),
    ) -> Image.Image:
        """
        Loads a standard transparent animal PNG (`RGBA`) at runtime and iterates
        through every pixel's `(r, g, b, a)` channels:
          - If `a > 0` (non-transparent animal pixel), converts RGB to solid black
            `#000000` -> `(0, 0, 0, a)`, preserving anti-aliased alpha intensity.
          - If `a == 0` (transparent background), preserves `(0, 0, 0, 0)`.

        No pre-made shadow files are ever saved or loaded from disk.
        """
        if not os.path.exists(image_path):
            os.makedirs(os.path.dirname(os.path.abspath(image_path)), exist_ok=True)
            slug = os.path.splitext(os.path.basename(image_path))[0].lower()
            SilhouetteGenerator._draw_animal_sprite(slug, image_path)

        rgba_image = Image.open(image_path).convert("RGBA")
        if rgba_image.size != size:
            rgba_image = rgba_image.resize(size, Image.Resampling.LANCZOS)

        width, height = rgba_image.size
        silhouette_img = Image.new("RGBA", (width, height), (0, 0, 0, 0))

        # Explicit runtime pixel-by-pixel iteration over RGBA channels (alpha-channel inspection)
        src_px = rgba_image.load()
        dst_px = silhouette_img.load()
        assert src_px is not None and dst_px is not None

        for y in range(height):
            for x in range(width):
                r, g, b, a = src_px[x, y]
                if a > 0:
                    # Non-transparent pixel -> solid black #000000 with original alpha
                    dst_px[x, y] = (0, 0, 0, a)
                else:
                    # Transparent pixel -> remains completely transparent
                    dst_px[x, y] = (0, 0, 0, 0)

        return silhouette_img

    def create_silhouette(
        self,
        png_path: str,
        size: Tuple[int, int] = (260, 260),
    ) -> Image.Image:
        """SSOT contract method for runtime RGBA -> #000000 silhouette conversion."""
        return self.generate_silhouette_from_png(png_path, size=size)

    def load_revealed(
        self,
        png_path: str,
        size: Tuple[int, int] = (260, 260),
    ) -> Image.Image:
        """Loads and resizes the full-color transparent RGBA animal sprite for reveal."""
        if not os.path.exists(png_path):
            os.makedirs(os.path.dirname(os.path.abspath(png_path)), exist_ok=True)
            slug = os.path.splitext(os.path.basename(png_path))[0].lower()
            self._draw_animal_sprite(slug, png_path)

        rgba_image = Image.open(png_path).convert("RGBA")
        if rgba_image.size != size:
            rgba_image = rgba_image.resize(size, Image.Resampling.LANCZOS)
        return rgba_image

    def render_card_image(
        self,
        png_path: str,
        revealed: bool = False,
        card_size: Tuple[int, int] = (280, 250),
        sprite_size: Tuple[int, int] = (230, 230),
    ) -> Image.Image:
        """
        Composites either the runtime-generated `#000000` silhouette (`revealed=False`)
        or the full-color realistic animal illustration (`revealed=True`) onto a sleek
        spotlight pedestal card and returns a `PIL.Image.Image`.
        """
        w, h = card_size
        bg_color = (26, 38, 57, 255) if not revealed else (20, 44, 40, 255)
        card = Image.new("RGBA", (w, h), bg_color)
        draw = ImageDraw.Draw(card)

        cx, cy = w // 2, h // 2
        max_r = min(w, h) // 2 - 10
        for step in range(max_r, 8, -6):
            ratio = 1.0 - (step / max_r)
            if not revealed:
                r_c = int(48 + 108 * ratio)
                g_c = int(76 + 135 * ratio)
                b_c = int(108 + 135 * ratio)
            else:
                r_c = int(38 + 98 * ratio)
                g_c = int(82 + 128 * ratio)
                b_c = int(72 + 95 * ratio)
            draw.ellipse(
                (cx - step, cy - step, cx + step, cy + step),
                fill=(r_c, g_c, b_c, 255),
            )

        # Subtle ground shadow under pedestal
        draw.ellipse(
            (cx - int(max_r * 0.72), cy + int(max_r * 0.62), cx + int(max_r * 0.72), cy + int(max_r * 0.85)),
            fill=(12, 20, 32, 95) if not revealed else (10, 26, 22, 110),
        )

        ring_col = (100, 185, 245, 150) if not revealed else (80, 235, 165, 200)
        draw.ellipse(
            (cx - max_r, cy - max_r, cx + max_r, cy + max_r),
            outline=ring_col,
            width=2 if not revealed else 3,
        )

        sprite = (
            self.load_revealed(png_path, size=sprite_size)
            if revealed
            else self.create_silhouette(png_path, size=sprite_size)
        )

        sx = (w - sprite.width) // 2
        sy = (h - sprite.height) // 2
        card.alpha_composite(sprite, dest=(sx, sy))

        border_col = (56, 189, 248, 220) if not revealed else (52, 211, 153, 240)
        draw.rounded_rectangle((2, 2, w - 3, h - 3), radius=16, outline=border_col, width=2)
        return card

    def render_card_photo(
        self,
        png_path: str,
        revealed: bool = False,
        card_size: Tuple[int, int] = (280, 250),
        sprite_size: Tuple[int, int] = (230, 230),
    ) -> ImageTk.PhotoImage:
        """Returns a Tkinter-ready `ImageTk.PhotoImage` for the card."""
        cache_key = (os.path.abspath(png_path), card_size, revealed)
        if cache_key in self._photo_cache:
            return self._photo_cache[cache_key]
        card = self.render_card_image(png_path, revealed=revealed, card_size=card_size, sprite_size=sprite_size)
        photo = ImageTk.PhotoImage(card)
        self._photo_cache[cache_key] = photo
        return photo

    def render_card_png_bytes(
        self,
        png_path: str,
        revealed: bool = False,
        card_size: Tuple[int, int] = (320, 270),
        sprite_size: Tuple[int, int] = (250, 250),
    ) -> bytes:
        """Returns PNG bytes of the rendered card (used by the Multiplayer Room HTTP Server)."""
        cache_key = (os.path.abspath(png_path), card_size, revealed)
        if cache_key in self._png_bytes_cache:
            return self._png_bytes_cache[cache_key]
        card = self.render_card_image(png_path, revealed=revealed, card_size=card_size, sprite_size=sprite_size)
        buf = io.BytesIO()
        card.save(buf, format="PNG")
        data = buf.getvalue()
        self._png_bytes_cache[cache_key] = data
        return data

    # ------------------------------------------------------------------
    # Realistic 2x Supersampled Animal Illustration Generator
    # ------------------------------------------------------------------
    def ensure_all_assets(self, force_regenerate: bool = False) -> List[str]:
        """
        Ensures all canonical animal PNGs exist in `assets/animals/` and match the
        v2 realistic supersampled artwork version. Automatically upgrades older v1
        sprites on first launch.
        """
        marker_path = os.path.join(self.assets_dir, self.ASSET_VERSION_MARKER)
        needs_upgrade = force_regenerate or (not os.path.exists(marker_path))

        created_paths: List[str] = []
        for slug in self.ANIMAL_SLUGS:
            out_path = os.path.join(self.assets_dir, f"{slug}.png")
            if needs_upgrade or not os.path.exists(out_path):
                self._draw_animal_sprite(slug, out_path)
            created_paths.append(out_path)

        if needs_upgrade:
            try:
                with open(marker_path, "w", encoding="utf-8") as f:
                    f.write("v2_realistic_640_supersampled\n")
            except OSError:
                pass
        return created_paths

    @staticmethod
    def _catmull_rom_spline(
        points: List[Tuple[float, float]],
        subdivisions: int = 10,
        closed: bool = False,
    ) -> List[Tuple[float, float]]:
        """Generates smooth anatomical curve points through control vertices."""
        if len(points) < 3:
            return [(float(x), float(y)) for x, y in points]
        pts = list(points)
        if closed:
            pts = [pts[-1]] + pts + [pts[0], pts[1]]
        else:
            pts = [pts[0]] + pts + [pts[-1]]

        out: List[Tuple[float, float]] = []
        for i in range(1, len(pts) - 2):
            p0, p1, p2, p3 = pts[i - 1], pts[i], pts[i + 1], pts[i + 2]
            for step in range(subdivisions):
                t = step / float(subdivisions)
                t2 = t * t
                t3 = t2 * t
                x = 0.5 * (
                    (2.0 * p1[0])
                    + (-p0[0] + p2[0]) * t
                    + (2.0 * p0[0] - 5.0 * p1[0] + 4.0 * p2[0] - p3[0]) * t2
                    + (-p0[0] + 3.0 * p1[0] - 3.0 * p2[0] + p3[0]) * t3
                )
                y = 0.5 * (
                    (2.0 * p1[1])
                    + (-p0[1] + p2[1]) * t
                    + (2.0 * p0[1] - 5.0 * p1[1] + 4.0 * p2[1] - p3[1]) * t2
                    + (-p0[1] + 3.0 * p1[1] - 3.0 * p2[1] + p3[1]) * t3
                )
                out.append((x, y))
        if not closed:
            out.append((float(points[-1][0]), float(points[-1][1])))
        return out

    @classmethod
    def _draw_smooth_polygon(
        cls,
        d: ImageDraw.ImageDraw,
        points: List[Tuple[float, float]],
        fill: Tuple[int, int, int, int],
        outline: Optional[Tuple[int, int, int, int]] = None,
        width: int = 1,
        closed: bool = True,
        subdivisions: int = 8,
    ) -> None:
        smooth_pts = cls._catmull_rom_spline(points, subdivisions=subdivisions, closed=closed)
        d.polygon(smooth_pts, fill=fill, outline=outline, width=width)

    @classmethod
    def _draw_tapered_stroke(
        cls,
        d: ImageDraw.ImageDraw,
        points: List[Tuple[float, float]],
        r_start: float,
        r_end: float,
        fill: Tuple[int, int, int, int],
        subdivisions: int = 12,
    ) -> None:
        """Draws a smooth organic tapered limb, tail, trunk, or tentacle."""
        curve = cls._catmull_rom_spline(points, subdivisions=subdivisions, closed=False)
        n = max(1, len(curve) - 1)
        for idx, (cx, cy) in enumerate(curve):
            t = idx / float(n)
            r = r_start + (r_end - r_start) * t
            if r > 0.5:
                d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=fill)

    @staticmethod
    def _draw_realistic_eye(
        d: ImageDraw.ImageDraw,
        cx: float,
        cy: float,
        r_outer: float,
        iris_col: Tuple[int, int, int, int],
        pupil_col: Tuple[int, int, int, int] = (12, 16, 24, 255),
        slit_pupil: bool = False,
    ) -> None:
        """Draws a realistic multi-layered wildlife eye with sclera, iris rim, pupil & dual specular catchlights."""
        d.ellipse(
            (cx - r_outer - 2, cy - r_outer - 2, cx + r_outer + 2, cy + r_outer + 2),
            fill=(20, 24, 30, 255),
        )
        d.ellipse((cx - r_outer, cy - r_outer, cx + r_outer, cy + r_outer), fill=iris_col)
        if slit_pupil:
            pw = max(2.5, r_outer * 0.28)
            ph = r_outer * 0.86
            d.ellipse((cx - pw, cy - ph, cx + pw, cy + ph), fill=pupil_col)
        else:
            pr = r_outer * 0.58
            d.ellipse((cx - pr, cy - pr, cx + pr, cy + pr), fill=pupil_col)
        # Primary and secondary corneal specular reflections
        hl1 = max(2.0, r_outer * 0.30)
        d.ellipse(
            (cx - r_outer * 0.45, cy - r_outer * 0.50, cx - r_outer * 0.45 + hl1, cy - r_outer * 0.50 + hl1),
            fill=(255, 255, 255, 245),
        )
        hl2 = max(1.2, r_outer * 0.16)
        d.ellipse(
            (cx + r_outer * 0.22, cy + r_outer * 0.20, cx + r_outer * 0.22 + hl2, cy + r_outer * 0.20 + hl2),
            fill=(255, 255, 255, 190),
        )

    @classmethod
    def _draw_animal_sprite(cls, slug: str, output_path: str) -> None:
        """
        Draws a high-detail, anatomically realistic RGBA wildlife illustration on a
        640x640 supersampled canvas and downsamples with LANCZOS to 320x320.
        """
        img = Image.new("RGBA", cls.SUPERSAMPLE_SIZE, (0, 0, 0, 0))
        d = ImageDraw.Draw(img)

        slug_key = slug.lower().replace(" ", "_").replace("-", "_")

        if "elephant" in slug_key:
            # AFRICAN ELEPHANT: Realistic savanna bull in side profile with knees/ankles,
            # sloped shoulder hump, temporal dome, large veined ear, ridged prehensile trunk & dual ivory tusks
            far_slate = (86, 94, 108, 255)
            mid_slate = (118, 127, 142, 255)
            light_slate = (146, 156, 170, 255)
            shadow_slate = (68, 76, 88, 255)
            wrinkle_col = (78, 86, 98, 210)
            ivory_base = (232, 222, 198, 255)
            ivory_tip = (252, 248, 236, 255)

            # Tail with realistic terminal hair tuft
            cls._draw_tapered_stroke(d, [(108, 285), (76, 355), (64, 425)], 11, 5, far_slate)
            cls._draw_smooth_polygon(
                d,
                [(64, 418), (50, 448), (58, 476), (72, 452), (70, 422)],
                fill=(42, 46, 54, 255),
            )

            # Far-side hind and fore legs (anatomical joints)
            cls._draw_smooth_polygon(
                d,
                [(152, 345), (206, 345), (200, 440), (206, 548), (154, 548), (146, 445)],
                fill=far_slate,
            )
            cls._draw_smooth_polygon(
                d,
                [(334, 345), (388, 345), (384, 445), (392, 548), (342, 548), (336, 442)],
                fill=far_slate,
            )

            # Massive barrel torso with spinal ridge, shoulder hump, and belly curve
            torso_pts = [
                (108, 272), (140, 206), (218, 184), (305, 192), (376, 174),
                (442, 205), (452, 336), (398, 392), (288, 404), (195, 386), (118, 342),
            ]
            cls._draw_smooth_polygon(d, torso_pts, fill=mid_slate)
            # Dorsal highlight & ventral underbelly shadow
            cls._draw_smooth_polygon(
                d,
                [(142, 212), (222, 188), (312, 196), (382, 180), (425, 212), (355, 258), (225, 256)],
                fill=light_slate,
            )
            cls._draw_smooth_polygon(
                d,
                [(155, 348), (275, 372), (395, 360), (428, 338), (395, 394), (285, 404), (188, 384)],
                fill=shadow_slate,
            )

            # Near-side hind leg (thigh, stifle joint, broad cushioned foot + toenails)
            hind_leg = [
                (118, 316), (204, 326), (194, 438), (188, 520), (198, 566),
                (122, 566), (128, 518), (122, 428),
            ]
            cls._draw_smooth_polygon(d, hind_leg, fill=mid_slate, outline=shadow_slate, width=2)
            for nx in (132, 152, 172):
                d.pieslice((nx, 548, nx + 18, 570), 180, 360, fill=(215, 212, 202, 255))

            # Near-side foreleg (muscular shoulder, wrist joint, broad foot + 4 toenails)
            fore_leg = [
                (362, 318), (438, 324), (428, 438), (428, 522), (442, 568),
                (362, 568), (368, 520), (364, 432),
            ]
            cls._draw_smooth_polygon(d, fore_leg, fill=mid_slate, outline=shadow_slate, width=2)
            for nx in (370, 390, 410, 426):
                d.pieslice((nx, 550, nx + 16, 572), 180, 360, fill=(215, 212, 202, 255))

            # Far tusk (slightly higher and darker ivory)
            cls._draw_tapered_stroke(
                d, [(492, 286), (548, 332), (596, 332), (624, 304)], 15, 4, ivory_base, subdivisions=14
            )

            # Cranium dome, cheek & lower jaw
            head_pts = [
                (412, 174), (468, 138), (528, 154), (554, 212),
                (538, 286), (484, 314), (432, 288),
            ]
            cls._draw_smooth_polygon(d, head_pts, fill=mid_slate)
            cls._draw_smooth_polygon(
                d, [(454, 146), (518, 156), (542, 204), (488, 218), (442, 188)], fill=light_slate
            )

            # Prehensile S-curved trunk with dual finger tips & transverse skin annulations
            trunk_spine = [
                (532, 216), (576, 265), (594, 345), (582, 438),
                (546, 496), (504, 492), (496, 452),
            ]
            cls._draw_tapered_stroke(d, trunk_spine, 34, 15, mid_slate, subdivisions=16)
            cls._draw_tapered_stroke(
                d, [(542, 218), (584, 268), (600, 345), (586, 432)], 14, 6, light_slate, subdivisions=12
            )
            # Trunk annular skin folds
            for wy in range(245, 455, 16):
                d.arc((548, wy, 598, wy + 18), 195, 345, fill=wrinkle_col, width=3)
            # Prehensile trunk tip fingers
            d.polygon([(484, 448), (498, 434), (512, 452), (496, 468)], fill=shadow_slate)

            # Iconic African map-shaped fan ear with acoustic veins & shaded inner fold
            ear_pts = [
                (434, 152), (358, 134), (302, 172), (288, 248),
                (312, 338), (356, 376), (402, 336), (444, 258),
            ]
            cls._draw_smooth_polygon(d, ear_pts, fill=shadow_slate, outline=(54, 62, 74, 255), width=3)
            cls._draw_smooth_polygon(
                d,
                [(424, 166), (364, 152), (318, 186), (306, 252), (326, 326), (360, 354), (404, 314), (432, 248)],
                fill=mid_slate,
            )
            # Ear vascular ridges
            for vx, vy in [(332, 206), (324, 262), (344, 318)]:
                d.line([(418, 232), (vx, vy)], fill=wrinkle_col, width=3)

            # Near-side sweeping ivory tusk with basal sheath
            cls._draw_tapered_stroke(
                d, [(484, 292), (542, 348), (594, 352), (628, 318)], 18, 4, ivory_tip, subdivisions=16
            )
            d.arc((476, 276, 518, 322), 20, 145, fill=shadow_slate, width=6)

            # Skin wrinkle lines across torso & joints
            for wx in (210, 245, 280, 315):
                d.arc((wx, 230, wx + 28, 345), 150, 210, fill=wrinkle_col, width=2)

            # Realistic Elephant Eye with brow fold
            d.arc((492, 194, 532, 224), 190, 350, fill=shadow_slate, width=4)
            cls._draw_realistic_eye(d, 512, 214, 11, (148, 98, 52, 255))

        elif "tiger" in slug_key:
            # BENGAL TIGER: Powerful prowling apex predator in lateral profile with shoulder scapula hump,
            # deep chest, white cheek ruff, anatomical paws, S-curved ringed tail & branched stripes
            deep_orange = (196, 88, 20, 255)
            mid_orange = (234, 122, 30, 255)
            bright_amber = (248, 156, 56, 255)
            cream_white = (250, 240, 222, 255)
            stripe_black = (22, 18, 16, 255)

            # Long S-curved counterbalance tail with black rings and black tip
            tail_pts = [(118, 286), (68, 258), (34, 202), (36, 142), (62, 112)]
            cls._draw_tapered_stroke(d, tail_pts, 20, 11, mid_orange, subdivisions=14)
            for tx, ty in [(84, 268), (52, 234), (36, 194), (38, 156)]:
                d.ellipse((tx - 14, ty - 8, tx + 14, ty + 8), fill=stripe_black)
            d.ellipse((48, 98, 76, 124), fill=stripe_black)

            # Far-side hind and fore legs (striding gait)
            cls._draw_smooth_polygon(
                d,
                [(158, 338), (208, 338), (226, 442), (248, 542), (282, 554), (214, 556), (186, 448)],
                fill=deep_orange,
            )
            cls._draw_smooth_polygon(
                d,
                [(378, 342), (424, 342), (402, 448), (384, 542), (416, 554), (352, 556), (366, 446)],
                fill=deep_orange,
            )

            # Lithe muscular torso (scapula hump, lumbar dip, deep ribcage)
            torso_pts = [
                (112, 274), (168, 224), (258, 232), (348, 218), (424, 198),
                (478, 236), (464, 354), (378, 384), (264, 368), (176, 362), (118, 326),
            ]
            cls._draw_smooth_polygon(d, torso_pts, fill=mid_orange)
            cls._draw_smooth_polygon(
                d,
                [(164, 230), (265, 238), (355, 224), (425, 206), (452, 244), (348, 282), (205, 276)],
                fill=bright_amber,
            )
            # Cream countershaded belly & chest
            cls._draw_smooth_polygon(
                d,
                [(188, 338), (285, 344), (386, 352), (456, 322), (446, 366), (368, 386), (258, 370)],
                fill=cream_white,
            )

            # Near-side muscular hind leg (thigh, hock joint, digitigrade paw)
            hind_near = [
                (114, 288), (202, 296), (188, 412), (152, 456), (164, 536),
                (198, 558), (124, 560), (118, 452), (136, 392),
            ]
            cls._draw_smooth_polygon(d, hind_near, fill=mid_orange)
            d.ellipse((128, 534, 202, 564), fill=cream_white)

            # Near-side muscular foreleg stepping forward
            fore_near = [
                (402, 312), (468, 318), (484, 428), (508, 534),
                (544, 556), (470, 560), (442, 438),
            ]
            cls._draw_smooth_polygon(d, fore_near, fill=mid_orange)
            d.ellipse((474, 532, 548, 564), fill=cream_white)

            # Neck, skull, ears, white cheek ruff, and powerful muzzle
            cls._draw_smooth_polygon(
                d,
                [(418, 202), (488, 152), (568, 168), (594, 234), (558, 298), (472, 314)],
                fill=mid_orange,
            )
            # Rounded tiger ears with black back and white ocelli spots
            d.ellipse((466, 114, 514, 166), fill=stripe_black)
            d.ellipse((480, 128, 502, 148), fill=cream_white)
            d.ellipse((526, 118, 572, 168), fill=stripe_black)
            d.ellipse((538, 132, 558, 150), fill=cream_white)

            # Fluffy white cheek ruff & chin
            cls._draw_smooth_polygon(
                d,
                [(482, 234), (532, 232), (588, 248), (596, 284), (546, 308), (478, 294)],
                fill=cream_white,
            )
            # Pink feline nose with black philtrum
            d.polygon([(582, 224), (608, 224), (596, 244)], fill=(228, 114, 124, 255), outline=stripe_black, width=2)

            # Branched vertical tiger stripes across flanks, thighs, and shoulders
            stripe_paths = [
                [(168, 234), (154, 298), (166, 362)],
                [(202, 232), (192, 294), (206, 348)],
                [(238, 234), (226, 288), (238, 344)],
                [(274, 230), (266, 296), (254, 342)],
                [(310, 226), (300, 288), (314, 346)],
                [(346, 222), (336, 286), (350, 352)],
                [(384, 212), (374, 278), (390, 346)],
                [(422, 206), (416, 272), (434, 336)],
                [(458, 202), (464, 266)],
                [(142, 388), (178, 398)],
                [(132, 432), (168, 442)],
                [(444, 388), (478, 394)],
                [(456, 434), (492, 440)],
            ]
            for sp in stripe_paths:
                cls._draw_tapered_stroke(d, sp, 7.5, 2.5, stripe_black, subdivisions=8)

            # Whisker lines
            for wy in (258, 268, 278):
                d.line([(566, wy), (618, wy + 12)], fill=(255, 255, 255, 220), width=2)

            # Fierce amber predator eye
            cls._draw_realistic_eye(d, 548, 198, 12, (250, 196, 28, 255))

        elif "penguin" in slug_key:
            # EMPEROR PENGUIN: Tall Antarctic seabird with sleek hydrodynamic torpedo body,
            # golden-orange auricular neck gradient, long decurved bill with lilac mandibular stripe & flippers
            obsidian = (18, 24, 36, 255)
            slate_back = (36, 48, 68, 255)
            snow_white = (246, 249, 254, 255)
            cream_chest = (252, 246, 215, 255)
            gold_patch = (250, 184, 28, 255)
            amber_glow = (245, 130, 18, 255)

            # Stiff wedge tail & webbed clawed feet
            d.polygon([(205, 515), (142, 568), (225, 558)], fill=obsidian)
            for fx in (238, 326):
                cls._draw_smooth_polygon(
                    d,
                    [(fx, 536), (fx - 26, 578), (fx + 48, 582), (fx + 56, 566), (fx + 22, 536)],
                    fill=(42, 46, 54, 255),
                )
                for cx in (fx - 18, fx + 12, fx + 42):
                    d.polygon([(cx, 574), (cx + 12, 574), (cx + 16, 590)], fill=(18, 20, 24, 255))

            # Far flipper wing
            cls._draw_smooth_polygon(
                d,
                [(368, 228), (478, 336), (508, 396), (484, 412), (382, 332)],
                fill=obsidian,
            )

            # Streamlined upright body contour
            body_pts = [
                (234, 138), (336, 138), (398, 226), (424, 368),
                (398, 518), (344, 556), (228, 556), (188, 496), (186, 342), (206, 214),
            ]
            cls._draw_smooth_polygon(d, body_pts, fill=obsidian)
            # Dorsal blue-slate sheen
            cls._draw_smooth_polygon(
                d,
                [(212, 198), (252, 198), (232, 348), (228, 512), (194, 488), (190, 342)],
                fill=slate_back,
            )

            # Crisp white plumage belly & golden-yellow upper breast gradient
            belly_pts = [
                (268, 218), (366, 218), (410, 356), (388, 512),
                (342, 548), (254, 548), (238, 442), (248, 312),
            ]
            cls._draw_smooth_polygon(d, belly_pts, fill=snow_white)
            cls._draw_smooth_polygon(
                d,
                [(266, 188), (364, 192), (392, 286), (328, 312), (254, 286)],
                fill=cream_chest,
            )

            # Head & iconic golden-amber auricular ear patch
            cls._draw_smooth_polygon(
                d,
                [(226, 76), (318, 68), (376, 108), (374, 194), (232, 194), (214, 132)],
                fill=obsidian,
            )
            cls._draw_smooth_polygon(
                d,
                [(256, 118), (312, 114), (334, 158), (318, 206), (264, 202), (248, 156)],
                fill=amber_glow,
            )
            cls._draw_smooth_polygon(
                d,
                [(264, 126), (308, 122), (326, 162), (312, 198), (270, 194)],
                fill=gold_patch,
            )

            # Sleek decurved Emperor Penguin bill with rose-lilac mandibular stripe
            beak_pts = [(364, 112), (446, 128), (484, 148), (478, 158), (428, 152), (364, 156)]
            cls._draw_smooth_polygon(d, beak_pts, fill=obsidian)
            cls._draw_tapered_stroke(
                d, [(374, 146), (432, 144), (472, 152)], 4.5, 2.0, (244, 114, 182, 255)
            )

            # Near flipper wing with pale underside edge
            near_wing = [
                (238, 224), (192, 298), (124, 398), (112, 434),
                (144, 442), (218, 368), (268, 268),
            ]
            cls._draw_smooth_polygon(d, near_wing, fill=obsidian, outline=slate_back, width=3)

            # Eye
            cls._draw_realistic_eye(d, 336, 108, 9, (92, 54, 32, 255))

        elif "eagle" in slug_key:
            # BALD EAGLE: Majestic soaring raptor with individually slotted primary wing feathers,
            # layered secondary coverts, snow-white head & fanned tail, fierce brow & hooked yellow beak
            dark_umber = (58, 36, 20, 255)
            mid_brown = (92, 58, 32, 255)
            warm_bronze = (128, 84, 48, 255)
            pure_white = (248, 250, 254, 255)
            shadow_white = (214, 224, 236, 255)
            raptor_gold = (250, 196, 24, 255)

            # Fanned white tail feathers with individual feather shafts
            for angle_deg in range(-32, 36, 11):
                rad = math.radians(angle_deg + 90)
                tx = 320 + math.cos(rad) * 185
                ty = 375 + math.sin(rad) * 185
                cls._draw_tapered_stroke(d, [(320, 365), (tx, ty)], 22, 14, shadow_white, subdivisions=8)
                cls._draw_tapered_stroke(d, [(320, 365), (tx * 0.98 + 6, ty * 0.98)], 18, 11, pure_white, subdivisions=8)

            # Left and Right soaring wings with slotted primary feather "fingers"
            for side in (-1, 1):
                cx = 320
                # Primary flight feathers (slotted outer tips)
                finger_tips = [
                    (cx + side * 296, 86),
                    (cx + side * 308, 128),
                    (cx + side * 302, 174),
                    (cx + side * 282, 218),
                    (cx + side * 252, 256),
                ]
                for idx, (fx, fy) in enumerate(finger_tips):
                    root_x = cx + side * (145 + idx * 14)
                    root_y = 215 + idx * 12
                    mid_x = (root_x + fx) * 0.5
                    mid_y = (root_y + fy) * 0.5 - 16
                    cls._draw_tapered_stroke(
                        d, [(root_x, root_y), (mid_x, mid_y), (fx, fy)], 16, 6, dark_umber, subdivisions=10
                    )

                # Secondary flight feathers (inner trailing edge)
                for sec_i in range(7):
                    sx0 = cx + side * (55 + sec_i * 22)
                    sy0 = 238
                    sx1 = cx + side * (62 + sec_i * 26)
                    sy1 = 348 - sec_i * 10
                    cls._draw_tapered_stroke(d, [(sx0, sy0), (sx1, sy1)], 18, 11, dark_umber, subdivisions=6)

                # Upper & median wing covert mantle
                wing_mantle = [
                    (cx + side * 42, 224),
                    (cx + side * 128, 146),
                    (cx + side * 228, 116),
                    (cx + side * 242, 198),
                    (cx + side * 156, 278),
                    (cx + side * 52, 296),
                ]
                cls._draw_smooth_polygon(d, wing_mantle, fill=mid_brown)
                cls._draw_smooth_polygon(
                    d,
                    [
                        (cx + side * 52, 220),
                        (cx + side * 130, 158),
                        (cx + side * 204, 142),
                        (cx + side * 184, 214),
                        (cx + side * 88, 252),
                    ],
                    fill=warm_bronze,
                )

            # Muscular torso & feathered tarsus legs with curved black talons
            cls._draw_smooth_polygon(
                d,
                [(256, 216), (384, 216), (396, 342), (356, 412), (284, 412), (244, 342)],
                fill=mid_brown,
            )
            for lx in (282, 358):
                cls._draw_tapered_stroke(d, [(lx, 392), (lx, 444)], 18, 10, warm_bronze)
                for dx in (-16, 0, 16):
                    cls._draw_tapered_stroke(d, [(lx, 444), (lx + dx, 474)], 6, 3, raptor_gold)
                    d.arc((lx + dx - 8, 468, lx + dx + 8, 492), 0, 220, fill=(20, 24, 30, 255), width=4)

            # Iconic snow-white Bald Eagle head with jagged neck-feather collar
            neck_collar = [
                (268, 224), (278, 152), (304, 118), (344, 118), (368, 152),
                (376, 224), (354, 248), (338, 226), (320, 252), (302, 226), (284, 246),
            ]
            cls._draw_smooth_polygon(d, neck_collar, fill=pure_white, outline=shadow_white, width=2)

            # Heavy hooked yellow raptor beak & cere
            beak_pts = [(356, 138), (416, 144), (444, 168), (434, 198), (416, 178), (356, 178)]
            cls._draw_smooth_polygon(d, beak_pts, fill=raptor_gold, outline=(180, 128, 12, 255), width=2)

            # Supraorbital ridge (fierce eagle brow) & golden eye
            d.line([(328, 142), (364, 148)], fill=shadow_white, width=6)
            cls._draw_realistic_eye(d, 346, 156, 9, raptor_gold)

        elif "cobra" in slug_key:
            # KING COBRA: Rear-up defensive strike posture, stacked muscular base coils with diamond
            # dorsal scales, wide ribbed spectacle hood, keeled ventral scutes, open fangs & forked tongue
            dark_olive = (46, 56, 30, 255)
            mid_olive = (84, 98, 50, 255)
            light_olive = (124, 138, 74, 255)
            ochre_belly = (216, 188, 116, 255)
            gold_rim = (238, 212, 142, 255)
            crimson = (218, 32, 48, 255)

            # Stacked lower body coils in figure-8 loop
            cls._draw_tapered_stroke(
                d,
                [(118, 520), (195, 564), (355, 568), (496, 532), (512, 476), (385, 456), (175, 464), (128, 512)],
                36,
                26,
                dark_olive,
                subdivisions=16,
            )
            cls._draw_tapered_stroke(
                d,
                [(158, 468), (285, 442), (438, 454), (468, 498), (345, 522), (185, 508)],
                30,
                22,
                mid_olive,
                subdivisions=14,
            )
            # Coil highlight and scale cross-hatching
            cls._draw_tapered_stroke(
                d, [(178, 466), (295, 444), (425, 458)], 12, 8, light_olive, subdivisions=10
            )

            # Flared cervical hood (iconic oval cobra silhouette)
            hood_pts = [
                (274, 448), (242, 348), (174, 242), (168, 146), (218, 86),
                (312, 74), (402, 92), (446, 158), (432, 254), (366, 356), (344, 452),
            ]
            cls._draw_smooth_polygon(d, hood_pts, fill=mid_olive, outline=dark_olive, width=5)

            # Lateral hood ribs & chevron markings
            for hy in range(135, 315, 32):
                d.arc((184, hy, 268, hy + 42), 190, 340, fill=dark_olive, width=4)
                d.arc((346, hy, 428, hy + 42), 200, 350, fill=dark_olive, width=4)
                d.arc((190, hy - 4, 264, hy + 36), 195, 335, fill=gold_rim, width=2)
                d.arc((350, hy - 4, 422, hy + 36), 205, 345, fill=gold_rim, width=2)

            # Central ventral scute column (segmented horizontal belly plates)
            ventral_pts = [
                (274, 128), (344, 128), (356, 268), (342, 458), (274, 458), (262, 268),
            ]
            cls._draw_smooth_polygon(d, ventral_pts, fill=ochre_belly, outline=dark_olive, width=3)
            for sy in range(145, 450, 20):
                d.arc((266, sy - 6, 350, sy + 12), 10, 170, fill=dark_olive, width=3)
                d.line([(272, sy - 2), (344, sy - 2)], fill=gold_rim, width=2)

            # Armored crown head with large parietal shields, fangs & long forked tongue
            head_pts = [
                (252, 96), (298, 58), (378, 64), (434, 96), (424, 134), (358, 144), (274, 136),
            ]
            cls._draw_smooth_polygon(d, head_pts, fill=light_olive, outline=dark_olive, width=4)

            # Forked flicking crimson tongue extending forward from snout
            cls._draw_tapered_stroke(d, [(426, 112), (496, 112)], 6, 4, crimson, subdivisions=8)
            cls._draw_tapered_stroke(d, [(494, 112), (546, 86)], 4, 1.5, crimson, subdivisions=8)
            cls._draw_tapered_stroke(d, [(494, 112), (548, 138)], 4, 1.5, crimson, subdivisions=8)

            # Fierce golden-bronze reptile eye with supraocular scale brow
            d.line([(356, 82), (402, 90)], fill=dark_olive, width=6)
            cls._draw_realistic_eye(d, 380, 96, 10, (245, 188, 28, 255), slit_pupil=True)

        elif "komodo" in slug_key or "dragon" in slug_key:
            # KOMODO DRAGON: Heavy-bodied Indonesian monitor lizard with sweeping muscular tail,
            # loose osteoderm neck folds, bowed reptilian legs, long curved claws & yellow forked tongue
            charcoal_olive = (54, 60, 44, 255)
            komodo_scale = (88, 96, 68, 255)
            tan_highlight = (126, 132, 96, 255)
            under_ochre = (154, 146, 108, 255)
            claw_ivory = (228, 220, 192, 255)

            # Long muscular sweeping tail curving from left to torso
            tail_spine = [(24, 214), (44, 278), (98, 336), (176, 356)]
            cls._draw_tapered_stroke(d, tail_spine, 10, 38, charcoal_olive, subdivisions=16)
            cls._draw_tapered_stroke(
                d, [(32, 224), (54, 282), (108, 334), (176, 352)], 6, 24, komodo_scale, subdivisions=14
            )

            # Far-side sprawling monitor legs
            cls._draw_smooth_polygon(
                d, [(212, 368), (254, 368), (242, 474), (204, 474)], fill=charcoal_olive
            )
            cls._draw_smooth_polygon(
                d, [(406, 368), (448, 368), (464, 474), (424, 474)], fill=charcoal_olive
            )

            # Heavy barrel torso with loose lateral skin fold & dorsal ridge
            torso_pts = [
                (152, 326), (224, 276), (336, 268), (442, 278), (506, 258),
                (526, 334), (452, 396), (324, 408), (206, 392),
            ]
            cls._draw_smooth_polygon(d, torso_pts, fill=komodo_scale, outline=charcoal_olive, width=3)
            cls._draw_smooth_polygon(
                d,
                [(218, 282), (338, 274), (442, 284), (484, 312), (344, 328), (218, 322)],
                fill=tan_highlight,
            )
            cls._draw_smooth_polygon(
                d,
                [(214, 362), (332, 376), (448, 364), (436, 398), (324, 408), (214, 390)],
                fill=under_ochre,
            )

            # Loose gular/cervical neck folds
            for fx in (448, 468, 488):
                d.arc((fx, 278, fx + 28, 368), 300, 75, fill=charcoal_olive, width=4)

            # Broad flat monitor head & heavy jaw
            head_pts = [
                (478, 264), (538, 238), (598, 256), (608, 288),
                (584, 318), (518, 332), (476, 316),
            ]
            cls._draw_smooth_polygon(d, head_pts, fill=komodo_scale, outline=charcoal_olive, width=3)
            cls._draw_smooth_polygon(
                d, [(502, 254), (562, 244), (596, 264), (554, 284), (498, 282)], fill=tan_highlight
            )

            # Iconic long yellow deeply forked Komodo tongue
            cls._draw_tapered_stroke(d, [(598, 292), (622, 286)], 5, 3, (250, 204, 21, 255))
            d.line([(618, 286), (636, 268)], fill=(250, 204, 21, 255), width=4)
            d.line([(618, 286), (638, 306)], fill=(250, 204, 21, 255), width=4)

            # Near-side muscular bowed hind & fore legs with 5 curved scythe claws
            for lx in (188, 386):
                leg_pts = [
                    (lx, 346), (lx + 68, 352), (lx + 58, 438),
                    (lx + 72, 496), (lx + 4, 498), (lx - 8, 432),
                ]
                cls._draw_smooth_polygon(d, leg_pts, fill=komodo_scale, outline=charcoal_olive, width=3)
                for c_i in range(5):
                    cx = lx + 4 + c_i * 15
                    d.polygon([(cx, 492), (cx + 10, 492), (cx + 18, 526), (cx + 6, 522)], fill=claw_ivory)

            # Osteoderm armored pebble scales texture
            for sy in range(295, 365, 18):
                for sx in range(215, 455, 22):
                    d.ellipse((sx, sy, sx + 12, sy + 8), fill=charcoal_olive)

            cls._draw_realistic_eye(d, 554, 266, 9, (180, 118, 36, 255))

        elif "frog" in slug_key:
            # RED-EYED TREE FROG: Vibrant Agalychnis callidryas perched on a tropical stem,
            # neon leaf-green dorsum, cobalt-blue & cream-striped flanks, splayed orange suction toes & huge ruby eyes
            neon_green = (58, 214, 96, 255)
            lime_highlight = (134, 239, 120, 255)
            deep_green = (22, 128, 60, 255)
            cobalt_blue = (37, 99, 235, 255)
            sky_flank = (56, 189, 248, 255)
            tangerine = (249, 115, 22, 255)
            ruby_red = (220, 24, 38, 255)

            # Folded hind leg (thigh + calf) with blue inner thigh & orange webbed suction toes
            cls._draw_tapered_stroke(d, [(186, 368), (104, 338), (118, 448)], 26, 18, cobalt_blue, subdivisions=10)
            cls._draw_tapered_stroke(d, [(112, 344), (128, 466), (176, 488)], 24, 16, neon_green, subdivisions=10)
            for tx, ty in [(92, 504), (126, 524), (166, 526), (202, 508)]:
                cls._draw_tapered_stroke(d, [(158, 478), (tx, ty)], 7, 5, tangerine)
                d.ellipse((tx - 15, ty - 15, tx + 15, ty + 15), fill=tangerine, outline=(194, 65, 12, 255), width=2)
                d.ellipse((tx - 7, ty - 9, tx + 3, ty - 1), fill=(254, 215, 170, 200))

            # Arched emerald body with cobalt-and-yellow striped lateral flanks
            body_pts = [
                (132, 346), (186, 226), (308, 198), (434, 222),
                (476, 314), (404, 412), (254, 422), (148, 388),
            ]
            cls._draw_smooth_polygon(d, body_pts, fill=neon_green, outline=deep_green, width=3)
            cls._draw_smooth_polygon(
                d, [(196, 232), (314, 206), (424, 232), (384, 294), (234, 292)], fill=lime_highlight
            )

            # Blue & cream vertical bars along the flank
            cls._draw_smooth_polygon(
                d,
                [(208, 312), (356, 308), (398, 368), (354, 412), (224, 408), (186, 364)],
                fill=cobalt_blue,
            )
            for bx in (232, 268, 304, 340, 372):
                cls._draw_tapered_stroke(d, [(bx, 314), (bx - 8, 402)], 6, 4, (254, 249, 195, 255))

            # Forelimb reaching down with large circular adhesive toe pads
            cls._draw_tapered_stroke(d, [(396, 348), (428, 444), (446, 496)], 20, 14, neon_green)
            for tx, ty in [(394, 534), (436, 548), (482, 542), (518, 514)]:
                cls._draw_tapered_stroke(d, [(446, 494), (tx, ty)], 7, 5, tangerine)
                d.ellipse((tx - 16, ty - 16, tx + 16, ty + 16), fill=tangerine, outline=(194, 65, 12, 255), width=2)
                d.ellipse((tx - 8, ty - 10, tx + 4, ty - 2), fill=(254, 215, 170, 200))

            # Broad frog head, smiling mouth line & bulging crimson vertical-slit eyes
            head_pts = [
                (356, 214), (448, 184), (548, 224), (576, 294),
                (534, 358), (434, 368), (364, 318),
            ]
            cls._draw_smooth_polygon(d, head_pts, fill=neon_green, outline=deep_green, width=3)
            d.arc((412, 274, 566, 348), 10, 165, fill=deep_green, width=4)

            # Iconic bulging crimson domes with vertical black pupils
            for ex, ey, er in [(418, 178, 42), (508, 188, 46)]:
                d.ellipse((ex - er - 4, ey - er - 4, ex + er + 4, ey + er + 4), fill=deep_green)
                cls._draw_realistic_eye(d, ex, ey, er, ruby_red, slit_pupil=True)

        elif "shark" in slug_key:
            # GREAT WHITE SHARK: Torpedo pelagic apex predator with crescent homocercal caudal fin,
            # tall falcate first dorsal fin, long swept pectoral fins, 5 gill slits & serrated teeth
            deep_navy = (44, 62, 84, 255)
            pelagic_slate = (82, 102, 128, 255)
            steel_blue = (122, 146, 174, 255)
            counter_white = (241, 245, 250, 255)
            gum_red = (168, 32, 42, 255)

            # Crescent caudal tail fin (upper & lower lobes + caudal keel notch)
            caudal_pts = [
                (128, 312), (48, 198), (18, 142), (36, 238), (74, 314),
                (42, 386), (26, 464), (62, 424), (128, 336),
            ]
            cls._draw_smooth_polygon(d, caudal_pts, fill=deep_navy, subdivisions=6)

            # Tall iconic triangular first dorsal fin & smaller pelvic/second dorsal fins
            dorsal_pts = [(274, 232), (318, 118), (344, 72), (358, 142), (388, 236)]
            cls._draw_smooth_polygon(d, dorsal_pts, fill=deep_navy)
            cls._draw_smooth_polygon(d, [(172, 282), (188, 244), (212, 286)], fill=pelagic_slate)
            cls._draw_smooth_polygon(d, [(178, 348), (194, 386), (218, 346)], fill=pelagic_slate)

            # Far pectoral fin
            cls._draw_smooth_polygon(
                d, [(412, 356), (382, 464), (446, 396)], fill=deep_navy
            )

            # Fusiform torpedo body (conical snout, muscular trunk, caudal peduncle)
            body_pts = [
                (98, 316), (196, 268), (318, 224), (448, 228), (566, 258),
                (622, 294), (584, 342), (528, 388), (402, 402), (248, 372), (104, 334),
            ]
            cls._draw_smooth_polygon(d, body_pts, fill=pelagic_slate)
            cls._draw_smooth_polygon(
                d, [(204, 272), (324, 230), (452, 234), (558, 262), (452, 292), (254, 298)], fill=steel_blue
            )

            # Irregular high-contrast countershading boundary along lateral line
            belly_pts = [
                (118, 326), (236, 328), (358, 338), (478, 332), (554, 328),
                (586, 338), (528, 390), (402, 404), (248, 374),
            ]
            cls._draw_smooth_polygon(d, belly_pts, fill=counter_white)

            # Open jaw cavity with upper & lower rows of triangular serrated Carcharodon teeth
            jaw_pts = [(504, 332), (578, 316), (594, 346), (554, 376), (506, 362)]
            cls._draw_smooth_polygon(d, jaw_pts, fill=gum_red, outline=deep_navy, width=3)
            for tx in range(516, 582, 11):
                d.polygon([(tx, 324), (tx + 5, 342), (tx + 10, 322)], fill=(255, 255, 255, 255))
                d.polygon([(tx + 2, 366), (tx + 6, 350), (tx + 10, 366)], fill=(255, 255, 255, 255))

            # Near-side long sickle pectoral fin
            pectoral_pts = [
                (348, 356), (304, 464), (274, 526), (328, 496), (408, 412), (434, 368),
            ]
            cls._draw_smooth_polygon(d, pectoral_pts, fill=pelagic_slate, outline=deep_navy, width=3)

            # 5 prominent branchial gill slits
            for gx in range(436, 488, 11):
                d.arc((gx, 286, gx + 12, 356), 145, 215, fill=deep_navy, width=4)

            # Cold black pelagic eye & Ampullae of Lorenzini snout pores
            cls._draw_realistic_eye(d, 548, 278, 9, (18, 24, 34, 255))

        elif "panda" in slug_key:
            # GIANT PANDA: Seated Sichuan bamboo bear with plush cream-white fur, black shoulder saddle,
            # furry round ears, teardrop eye patches, hind paw pads & segmented green bamboo culm
            fur_black = (22, 24, 30, 255)
            charcoal_highlight = (48, 52, 64, 255)
            plush_white = (246, 244, 238, 255)
            cream_shadow = (218, 214, 204, 255)
            bamboo_green = (34, 168, 76, 255)
            bamboo_light = (116, 222, 132, 255)

            # Plump seated body
            cls._draw_smooth_polygon(
                d,
                [(152, 256), (468, 256), (512, 412), (464, 548), (156, 548), (112, 412)],
                fill=plush_white,
                outline=fur_black,
                width=4,
            )
            cls._draw_smooth_polygon(
                d, [(196, 368), (424, 368), (448, 538), (172, 538)], fill=cream_shadow
            )

            # Iconic black shoulder saddle & forelimbs
            saddle_pts = [
                (148, 246), (472, 246), (508, 364), (424, 396),
                (310, 338), (196, 396), (112, 364),
            ]
            cls._draw_smooth_polygon(d, saddle_pts, fill=fur_black)

            # Seated hind legs & furry soles with pink/grey paw pads
            for lx, rx in [(104, 254), (366, 516)]:
                d.ellipse((lx, 424, rx, 566), fill=fur_black)
                cx = (lx + rx) // 2
                d.ellipse((cx - 32, 486, cx + 32, 538), fill=charcoal_highlight)
                for px in (-22, 0, 22):
                    d.ellipse((cx + px - 8, 464, cx + px + 8, 480), fill=charcoal_highlight)

            # Segmented green bamboo stalk & lance-shaped leaves held across chest
            cls._draw_tapered_stroke(d, [(428, 544), (512, 286), (576, 96)], 14, 10, bamboo_green, subdivisions=10)
            cls._draw_tapered_stroke(d, [(432, 540), (516, 286), (578, 98)], 6, 4, bamboo_light, subdivisions=10)
            for bx, by in [(462, 438), (496, 334), (532, 226), (558, 146)]:
                d.line([(bx - 14, by - 4), (bx + 14, by + 4)], fill=(20, 83, 45, 255), width=4)
            for lx, ly, ang in [(532, 226, -25), (558, 146, 20), (496, 334, 30)]:
                cls._draw_smooth_polygon(
                    d,
                    [(lx, ly), (lx + 54, ly - 28 + ang), (lx + 96, ly - 12 + ang), (lx + 46, ly + 14 + ang)],
                    fill=bamboo_green,
                )

            # Forearm gripping the bamboo stalk
            cls._draw_tapered_stroke(d, [(448, 298), (508, 346), (488, 368)], 38, 30, fur_black)

            # Round furry ears & broad bear head
            d.ellipse((166, 66, 256, 156), fill=fur_black)
            d.ellipse((364, 66, 454, 156), fill=fur_black)
            cls._draw_smooth_polygon(
                d,
                [(188, 104), (310, 86), (432, 104), (464, 214), (424, 314), (310, 332), (196, 314), (156, 214)],
                fill=plush_white,
                outline=fur_black,
                width=4,
            )

            # Iconic tilted oval black eye patches & expressive eyes
            cls._draw_smooth_polygon(
                d, [(216, 174), (276, 168), (284, 236), (226, 254), (202, 214)], fill=fur_black
            )
            cls._draw_smooth_polygon(
                d, [(344, 168), (404, 174), (418, 214), (394, 254), (336, 236)], fill=fur_black
            )
            cls._draw_realistic_eye(d, 252, 204, 11, (92, 58, 32, 255))
            cls._draw_realistic_eye(d, 368, 204, 11, (92, 58, 32, 255))

            # Muzzle, nose & gentle mouth
            d.ellipse((272, 232, 348, 296), fill=cream_shadow)
            d.polygon([(290, 244), (330, 244), (310, 268)], fill=fur_black)
            d.arc((282, 262, 310, 286), 0, 180, fill=fur_black, width=3)
            d.arc((310, 262, 338, 286), 0, 180, fill=fur_black, width=3)

        elif "platypus" in slug_key:
            # PLATYPUS: Semi-aquatic monotreme with broad leathery electroreceptive duck bill,
            #frontal shield, dense waterproof umber fur, cross-hatched beaver paddle tail & webbed feet
            dark_umber = (78, 48, 28, 255)
            rich_fur = (118, 76, 44, 255)
            golden_belly = (186, 138, 88, 255)
            slate_bill = (48, 60, 76, 255)
            bill_highlight = (78, 94, 116, 255)

            # Broad flat beaver-like paddle tail with texture cross-hatching
            tail_pts = [
                (26, 338), (64, 282), (146, 288), (192, 326),
                (186, 376), (124, 404), (44, 388),
            ]
            cls._draw_smooth_polygon(d, tail_pts, fill=slate_bill, outline=(30, 38, 48, 255), width=3)
            for tx in range(52, 168, 20):
                d.line([(tx, 294), (tx + 18, 392)], fill=(34, 42, 54, 220), width=3)
                d.line([(tx + 18, 294), (tx, 392)], fill=(34, 42, 54, 180), width=2)

            # Streamlined low-slung otter-like body
            body_pts = [
                (166, 296), (254, 248), (376, 246), (468, 268),
                (486, 356), (402, 412), (264, 414), (174, 376),
            ]
            cls._draw_smooth_polygon(d, body_pts, fill=rich_fur, outline=dark_umber, width=3)
            cls._draw_smooth_polygon(
                d, [(212, 354), (348, 358), (446, 348), (402, 410), (264, 412)], fill=golden_belly
            )

            # Webbed swimming paddles with scalloped toe membranes & knuckles
            for lx in (228, 396):
                web_pts = [
                    (lx, 384), (lx - 38, 466), (lx - 14, 456), (lx + 12, 474),
                    (lx + 36, 458), (lx + 62, 468), (lx + 42, 386),
                ]
                cls._draw_smooth_polygon(d, web_pts, fill=slate_bill, outline=(28, 36, 46, 255), width=2)
                for rx in (-24, 4, 32):
                    d.line([(lx + 18, 394), (lx + rx, 462)], fill=bill_highlight, width=3)

            # Head with white eye-groove patch
            cls._draw_smooth_polygon(
                d, [(416, 248), (488, 242), (528, 296), (496, 364), (416, 358)], fill=rich_fur
            )
            d.ellipse((464, 266, 496, 294), fill=(228, 222, 206, 255))
            cls._draw_realistic_eye(d, 478, 280, 8, (24, 20, 18, 255))

            # Broad leathery duck-like bill with dorsal frontal shield, nostrils & lower mandible
            bill_pts = [
                (504, 268), (514, 246), (532, 278), (608, 292),
                (626, 328), (602, 362), (512, 358), (498, 324),
            ]
            cls._draw_smooth_polygon(d, bill_pts, fill=slate_bill, outline=(28, 36, 46, 255), width=3)
            cls._draw_smooth_polygon(
                d, [(526, 286), (598, 298), (612, 324), (534, 326)], fill=bill_highlight
            )
            d.ellipse((578, 304, 594, 314), fill=(20, 26, 34, 255))

        elif "kangaroo" in slug_key:
            # RED KANGAROO: Muscular bipedal marsupial with thick tripod counterbalance tail,
            # Z-articulated spring hind legs, long syndactylous pes foot, pouch with joey & tall ears
            deep_rust = (154, 62, 26, 255)
            red_ochre = (202, 92, 44, 255)
            warm_buff = (242, 212, 174, 255)
            dark_muzzle = (58, 44, 38, 255)

            # Heavy muscular counterbalance tail resting on the ground
            tail_pts = [(224, 378), (136, 468), (58, 536), (22, 548)]
            cls._draw_tapered_stroke(d, tail_pts, 38, 12, red_ochre, subdivisions=16)
            cls._draw_tapered_stroke(
                d, [(224, 392), (138, 480), (58, 544)], 18, 6, warm_buff, subdivisions=12
            )

            # Far-side Z-shaped hind leg & long foot
            cls._draw_tapered_stroke(d, [(268, 396), (298, 518), (412, 536)], 18, 10, deep_rust, subdivisions=10)

            # Upright pear-shaped torso & cream chest/pouch
            torso_pts = [
                (212, 368), (242, 246), (294, 178), (348, 188),
                (378, 286), (366, 408), (274, 428),
            ]
            cls._draw_smooth_polygon(d, torso_pts, fill=red_ochre)
            cls._draw_smooth_polygon(
                d, [(318, 206), (358, 224), (378, 314), (362, 406), (314, 396)], fill=warm_buff
            )

            # Joey peeking out of mother's marsupial pouch
            d.arc((324, 336, 382, 384), 0, 180, fill=deep_rust, width=4)
            d.ellipse((342, 298, 396, 348), fill=red_ochre)
            d.polygon([(348, 304), (336, 268), (364, 296)], fill=red_ochre)
            d.polygon([(366, 300), (366, 264), (382, 298)], fill=red_ochre)
            cls._draw_realistic_eye(d, 376, 318, 5, (28, 22, 18, 255))

            # Near-side muscular thigh, tibia, Achilles hock & long hopping foot
            d.ellipse((196, 318, 338, 456), fill=red_ochre, outline=deep_rust, width=3)
            cls._draw_tapered_stroke(d, [(276, 434), (242, 544)], 22, 14, red_ochre, subdivisions=10)
            cls._draw_tapered_stroke(d, [(238, 544), (394, 558)], 15, 9, red_ochre, subdivisions=10)
            d.polygon([(392, 548), (424, 558), (392, 566)], fill=dark_muzzle)

            # Forelimbs with five-clawed paws held at chest
            cls._draw_tapered_stroke(d, [(338, 228), (408, 268), (396, 308)], 14, 8, red_ochre, subdivisions=10)

            # Neck, deer-like head, tall oval ears & dark velvet nose
            cls._draw_tapered_stroke(d, [(308, 198), (348, 118)], 28, 20, red_ochre)
            # Large upright oval ears with pale inner pinnae
            cls._draw_smooth_polygon(
                d, [(318, 106), (284, 28), (314, 24), (344, 96)], fill=deep_rust
            )
            cls._draw_smooth_polygon(
                d, [(346, 102), (342, 20), (374, 24), (376, 98)], fill=red_ochre
            )
            cls._draw_smooth_polygon(
                d, [(352, 92), (350, 36), (366, 38), (368, 92)], fill=warm_buff
            )
            # Head & elongated muzzle
            cls._draw_smooth_polygon(
                d, [(316, 94), (384, 88), (446, 118), (442, 148), (378, 154), (322, 138)], fill=red_ochre
            )
            d.ellipse((426, 116, 452, 142), fill=dark_muzzle)
            cls._draw_realistic_eye(d, 378, 112, 8, (42, 24, 16, 255))

        elif "dolphin" in slug_key:
            # BOTTLENOSE DOLPHIN: Dynamic arc-leaping cetacean with falcate dorsal fin,
            # bulbous melon forehead, bottle-shaped rostrum with gentle smile, flippers & horizontal flukes
            deep_marine = (28, 78, 128, 255)
            dolphin_slate = (58, 126, 184, 255)
            cerulean_sheen = (112, 178, 228, 255)
            pearl_belly = (232, 244, 252, 255)

            # Falcate (sickle-curved) dorsal fin at apex of back
            dorsal_pts = [(268, 146), (294, 58), (324, 34), (318, 96), (356, 152)]
            cls._draw_smooth_polygon(d, dorsal_pts, fill=deep_marine, subdivisions=8)

            # Far pectoral flipper
            cls._draw_smooth_polygon(
                d, [(434, 294), (424, 396), (478, 326)], fill=deep_marine
            )

            # Sweeping hydrodynamic arched body from tail peduncle to melon head
            upper_arc = [
                (86, 398), (118, 268), (206, 162), (334, 134),
                (466, 166), (558, 246), (574, 286), (622, 316),
                (614, 338), (546, 328), (452, 284), (336, 236),
                (224, 258), (146, 342), (108, 418),
            ]
            cls._draw_smooth_polygon(d, upper_arc, fill=dolphin_slate, subdivisions=10)

            # Specular wet skin highlight along dorsal ridge
            cls._draw_tapered_stroke(
                d,
                [(152, 244), (242, 166), (356, 148), (468, 182), (542, 246)],
                12,
                6,
                cerulean_sheen,
                subdivisions=14,
            )

            # Pearl-white underbelly countershading
            belly_arc = [
                (146, 342), (224, 258), (336, 236), (452, 284),
                (546, 328), (596, 336), (534, 356), (428, 328),
                (324, 288), (222, 312),
            ]
            cls._draw_smooth_polygon(d, belly_arc, fill=pearl_belly, subdivisions=10)

            # Iconic horizontal tail flukes with median notch
            fluke_pts = [
                (96, 388), (24, 424), (16, 456), (82, 438),
                (98, 448), (124, 498), (156, 488), (116, 408),
            ]
            cls._draw_smooth_polygon(d, fluke_pts, fill=deep_marine, subdivisions=8)

            # Near-side curved pectoral flipper
            flipper_pts = [
                (386, 274), (344, 368), (322, 418), (368, 392), (432, 308),
            ]
            cls._draw_smooth_polygon(d, flipper_pts, fill=dolphin_slate, outline=deep_marine, width=3)

            # Bottlenose rostrum crease, smile line & eye
            d.arc((546, 286, 618, 336), 175, 345, fill=deep_marine, width=3)
            cls._draw_realistic_eye(d, 524, 268, 8, (18, 28, 42, 255))

        elif "owl" in slug_key:
            # SNOWY OWL: Regally perched Arctic raptor with spread wings, layered primary feathers,
            # concentric facial disc, dusky charcoal scalloped barring, feathered talons & golden eyes
            arctic_white = (248, 250, 254, 255)
            frost_shadow = (214, 224, 238, 255)
            slate_bar = (64, 76, 96, 255)
            bark_brown = (102, 64, 36, 255)
            owl_amber = (245, 168, 18, 255)

            # Spread left & right wings with rounded primary feather tips & dark Arctic barring
            for side in (-1, 1):
                cx = 320
                wing_pts = [
                    (cx + side * 68, 214),
                    (cx + side * 196, 118),
                    (cx + side * 296, 108),
                    (cx + side * 304, 178),
                    (cx + side * 276, 256),
                    (cx + side * 218, 324),
                    (cx + side * 92, 368),
                ]
                cls._draw_smooth_polygon(d, wing_pts, fill=arctic_white, outline=slate_bar, width=3)
                # Scalloped dark charcoal bars across wing coverts & primaries
                for row_y in (168, 212, 256, 298):
                    for col_i in range(3):
                        bx = cx + side * (128 + col_i * 48)
                        x0, x1 = min(bx, bx + side * 32), max(bx, bx + side * 32)
                        d.arc((x0, row_y, x1, row_y + 22), 0, 180, fill=slate_bar, width=4)

            # Fanned tail & plump body with horizontal dusky barring
            cls._draw_smooth_polygon(
                d, [(254, 446), (224, 568), (416, 568), (386, 446)], fill=frost_shadow, outline=slate_bar, width=3
            )
            cls._draw_smooth_polygon(
                d,
                [(212, 198), (428, 198), (446, 356), (402, 488), (238, 488), (194, 356)],
                fill=arctic_white,
                outline=slate_bar,
                width=3,
            )
            for by in range(256, 464, 28):
                for bx in (236, 296, 356):
                    d.arc((bx, by, bx + 44, by + 20), 0, 180, fill=slate_bar, width=4)

            # Driftwood perch branch & heavily feathered snowy talons with black claws
            cls._draw_tapered_stroke(d, [(108, 496), (320, 488), (532, 502)], 18, 14, bark_brown, subdivisions=10)
            for tx in (268, 372):
                d.ellipse((tx - 26, 464, tx + 26, 504), fill=arctic_white, outline=slate_bar, width=2)
                for dx in (-12, 0, 12):
                    d.polygon([(tx + dx - 4, 496), (tx + dx + 4, 496), (tx + dx, 522)], fill=(20, 24, 32, 255))

            # Round dome head & dual facial discs around hypnotic golden eyes
            cls._draw_smooth_polygon(
                d,
                [(224, 96), (320, 74), (416, 96), (434, 186), (398, 246), (242, 246), (206, 186)],
                fill=arctic_white,
                outline=slate_bar,
                width=3,
            )
            d.ellipse((238, 124, 316, 202), fill=frost_shadow)
            d.ellipse((324, 124, 402, 202), fill=frost_shadow)
            cls._draw_realistic_eye(d, 278, 162, 22, owl_amber)
            cls._draw_realistic_eye(d, 362, 162, 22, owl_amber)

            # Hooked black beak nestled in white rictal bristles
            d.polygon([(308, 174), (332, 174), (320, 212)], fill=(24, 30, 40, 255))

        elif "chameleon" in slug_key:
            # VEILED / PANTHER CHAMELEON: High laterally-compressed leaf body, tall conical casque helmet,
            # dorsal spine crest, logarithmic spiraled prehensile tail, zygodactyl pincer feet & turret eye
            emerald_teal = (16, 185, 129, 255)
            vivid_lime = (132, 204, 22, 255)
            turquoise_band = (6, 182, 212, 255)
            coral_orange = (244, 63, 94, 255)
            sun_yellow = (250, 204, 21, 255)
            branch_wood = (112, 68, 36, 255)

            # Angled tropical tree branch
            cls._draw_tapered_stroke(d, [(36, 476), (312, 452), (596, 428)], 16, 12, branch_wood, subdivisions=12)

            # Tightly coiled logarithmic spiral prehensile tail
            spiral_pts: List[Tuple[float, float]] = []
            cx_sp, cy_sp = 136.0, 364.0
            for step in range(46):
                theta = step * 0.28
                rad = max(8.0, 92.0 - step * 1.85)
                spiral_pts.append((cx_sp + math.cos(theta) * rad, cy_sp + math.sin(theta) * rad))
            cls._draw_tapered_stroke(d, spiral_pts, 22, 5, emerald_teal, subdivisions=6)
            cls._draw_tapered_stroke(d, spiral_pts[4:], 10, 3, vivid_lime, subdivisions=4)

            # High arched laterally-compressed body with vertical turquoise/coral/gold bands
            body_pts = [
                (176, 356), (196, 232), (288, 168), (398, 178),
                (456, 246), (446, 356), (344, 376), (228, 378),
            ]
            cls._draw_smooth_polygon(d, body_pts, fill=emerald_teal, outline=(12, 108, 78, 255), width=3)

            for bx in (232, 286, 342, 396):
                cls._draw_tapered_stroke(d, [(bx, 188), (bx - 12, 358)], 14, 8, turquoise_band, subdivisions=8)
                cls._draw_tapered_stroke(d, [(bx + 10, 198), (bx - 2, 348)], 8, 5, sun_yellow, subdivisions=8)

            # Serrated dorsal crest spines along the spine
            for sx in range(206, 434, 18):
                sy = int(174 + abs(sx - 315) * 0.25)
                d.polygon([(sx, sy + 12), (sx + 8, sy - 18), (sx + 16, sy + 12)], fill=coral_orange)

            # Zygodactyl mitten-like pincer feet gripping the branch
            for lx, bx_foot in [(238, 224), (398, 416)]:
                cls._draw_tapered_stroke(
                    d, [(lx, 348), (lx - 18, 404), (bx_foot, 444)], 14, 10, vivid_lime, subdivisions=8
                )
                d.polygon(
                    [(bx_foot - 18, 442), (bx_foot + 22, 440), (bx_foot + 14, 468), (bx_foot - 12, 468)],
                    fill=emerald_teal,
                )

            # Tall veiled casque helmet, labial ridge & conical turret eye
            head_pts = [
                (438, 214), (456, 98), (496, 86), (524, 174),
                (594, 248), (586, 312), (508, 336), (444, 322),
            ]
            cls._draw_smooth_polygon(d, head_pts, fill=vivid_lime, outline=(12, 108, 78, 255), width=3)
            cls._draw_smooth_polygon(
                d, [(454, 114), (488, 98), (512, 178), (466, 208)], fill=turquoise_band
            )

            # Conical scaly turret eye with tiny central aperture
            d.ellipse((492, 212, 556, 276), fill=coral_orange, outline=(12, 108, 78, 255), width=3)
            d.ellipse((506, 226, 542, 262), fill=sun_yellow)
            cls._draw_realistic_eye(d, 524, 244, 10, (24, 28, 36, 255))

        elif "axolotl" in slug_key:
            # AXOLOTL: Leucistic pink Mexican salamander (Ambystoma mexicanum) with translucent
            # dorsal/caudal fin crest, 6 sweeping rami with delicate crimson gill filaments & 4-toed limbs
            soft_pink = (252, 205, 228, 255)
            blush_pink = (244, 158, 198, 255)
            fin_translucent = (249, 168, 212, 175)
            crimson_gill = (225, 29, 72, 255)
            ruby_filament = (244, 63, 94, 255)

            # Tadpole-like laterally compressed tail with translucent dorsal/ventral fin membrane
            fin_pts = [
                (288, 286), (168, 274), (58, 334), (16, 404),
                (54, 456), (176, 444), (296, 396),
            ]
            cls._draw_smooth_polygon(d, fin_pts, fill=fin_translucent, outline=blush_pink, width=2)
            cls._draw_tapered_stroke(
                d, [(296, 344), (168, 364), (42, 404)], 28, 6, soft_pink, subdivisions=14
            )

            # Smooth salamander body & delicate 4-toed limbs
            cls._draw_smooth_polygon(
                d,
                [(224, 284), (356, 268), (456, 294), (446, 408), (336, 424), (224, 398)],
                fill=soft_pink,
                outline=blush_pink,
                width=3,
            )
            for lx0, ly0, lx1, ly1 in [(256, 386, 224, 488), (396, 388, 434, 492)]:
                cls._draw_tapered_stroke(d, [(lx0, ly0), (lx1, ly1)], 18, 11, soft_pink)
                for dx in (-18, -6, 6, 18):
                    cls._draw_tapered_stroke(d, [(lx1, ly1), (lx1 + dx, ly1 + 26)], 5, 2.5, blush_pink)

            # 6 iconic feathery external gill stalks (3 per side) with fine fimbriae filaments
            gill_stalks = [
                # Left 3 gills
                [(318, 188), (236, 128), (156, 92)],
                [(308, 222), (212, 198), (128, 186)],
                [(316, 256), (226, 268), (154, 288)],
                # Right 3 gills
                [(482, 188), (554, 128), (618, 92)],
                [(492, 222), (572, 198), (628, 186)],
                [(484, 256), (562, 268), (616, 288)],
            ]
            for stalk in gill_stalks:
                curve = cls._catmull_rom_spline(stalk, subdivisions=8)
                # Fine feathery filaments along each gill stalk
                for cx, cy in curve[2:]:
                    for f_ang in (-0.8, -0.3, 0.3, 0.8):
                        fx = cx + math.cos(f_ang) * 18
                        fy = cy + math.sin(f_ang) * 22
                        d.line([(cx, cy), (fx, fy)], fill=ruby_filament, width=4)
                cls._draw_tapered_stroke(d, stalk, 11, 4, crimson_gill, subdivisions=10)

            # Wide rounded neotenic salamander head with gentle smile & dark glossy eyes
            cls._draw_smooth_polygon(
                d,
                [(296, 168), (400, 148), (504, 168), (528, 246), (496, 314), (400, 328), (304, 314), (272, 246)],
                fill=soft_pink,
                outline=blush_pink,
                width=3,
            )
            cls._draw_realistic_eye(d, 348, 226, 14, (24, 24, 36, 255))
            cls._draw_realistic_eye(d, 452, 226, 14, (24, 24, 36, 255))
            d.arc((356, 252, 444, 292), 15, 165, fill=crimson_gill, width=5)

        else:
            # CLOWNFISH (Amphiprion ocellaris): Vibrant reef anemonefish with rounded caudal,
            # pectoral, pelvic, and dual dorsal fins, 3 wavy white vertical bars & bold black margins
            reef_orange = (249, 104, 22, 255)
            bright_tangerine = (254, 146, 48, 255)
            pure_white = (248, 250, 254, 255)
            jet_black = (18, 22, 28, 255)

            # Rounded paddle caudal tail fin with thick black margin
            caudal_pts = [
                (148, 312), (54, 224), (28, 268), (24, 336), (34, 404), (62, 436), (148, 356),
            ]
            cls._draw_smooth_polygon(d, caudal_pts, fill=reef_orange, outline=jet_black, width=10)

            # Spiny anterior dorsal fin, soft posterior dorsal fin, pelvic & anal fins
            cls._draw_smooth_polygon(
                d,
                [(248, 224), (274, 146), (348, 138), (402, 186), (412, 228)],
                fill=reef_orange,
                outline=jet_black,
                width=9,
            )
            cls._draw_smooth_polygon(
                d,
                [(168, 254), (196, 158), (254, 168), (268, 236)],
                fill=reef_orange,
                outline=jet_black,
                width=9,
            )
            cls._draw_smooth_polygon(
                d,
                [(296, 412), (268, 504), (338, 508), (368, 424)],
                fill=reef_orange,
                outline=jet_black,
                width=9,
            )
            cls._draw_smooth_polygon(
                d,
                [(176, 396), (196, 478), (258, 466), (268, 408)],
                fill=reef_orange,
                outline=jet_black,
                width=8,
            )

            # Plump oval reef-fish body
            body_pts = [
                (132, 318), (206, 224), (348, 198), (488, 224),
                (588, 296), (596, 344), (506, 422), (348, 438), (204, 404), (132, 354),
            ]
            cls._draw_smooth_polygon(d, body_pts, fill=reef_orange, outline=jet_black, width=7)
            cls._draw_smooth_polygon(
                d, [(224, 238), (356, 214), (478, 238), (456, 312), (246, 312)], fill=bright_tangerine
            )

            # Three iconic wavy white vertical bars bordered in black
            # 1. Peduncle tail bar
            bar1 = [(146, 282), (182, 282), (186, 386), (146, 382)]
            cls._draw_smooth_polygon(d, bar1, fill=pure_white, outline=jet_black, width=6)
            # 2. Central saddle bar with anterior bulge
            bar2 = [
                (296, 202), (348, 202), (354, 294), (382, 326),
                (348, 434), (294, 432), (288, 324),
            ]
            cls._draw_smooth_polygon(d, bar2, fill=pure_white, outline=jet_black, width=6)
            # 3. Opercular head bar behind eye
            bar3 = [
                (456, 218), (502, 232), (496, 324), (508, 416),
                (464, 422), (448, 326),
            ]
            cls._draw_smooth_polygon(d, bar3, fill=pure_white, outline=jet_black, width=6)

            # Large rounded pectoral fin in center of body
            pectoral_pts = [
                (406, 312), (332, 286), (298, 336), (324, 396), (406, 368),
            ]
            cls._draw_smooth_polygon(d, pectoral_pts, fill=bright_tangerine, outline=jet_black, width=8)
            for ry in (316, 338, 360):
                d.line([(396, 340), (318, ry)], fill=jet_black, width=2)

            # Eye & reef-fish lips
            cls._draw_realistic_eye(d, 534, 288, 14, (234, 88, 12, 255))
            d.arc((564, 316, 602, 348), 140, 250, fill=jet_black, width=4)

        # Downsample 2x supersampled 640x640 canvas to crisp 320x320 PNG via LANCZOS
        final_img = img.resize(cls.DEFAULT_CANVAS_SIZE, Image.Resampling.LANCZOS)
        final_img.save(output_path, format="PNG")


# Provide alias so callers importing either `AssetManager` or `SilhouetteGenerator` succeed
AssetManager = SilhouetteGenerator


# ============================================================================
# 1B. MULTIPLAYER ROOM SERVER & SHAREABLE LINK ENGINE (`ThreadingHTTPServer`)
# ============================================================================

class MultiplayerRoomServer:
    """
    Zero-dependency Multiplayer Room HTTP & Web Client Server built on Python's
    `http.server.ThreadingHTTPServer` + `socket` + `json`.

    Flow:
      1. Host clicks "CREATE MULTIPLAYER ROOM & GET LINK" in the Tkinter app.
      2. Server binds to `0.0.0.0:<port>`, detects the machine's LAN IP, generates a
         6-character room code (e.g. `ANM482`), and creates shareable URLs:
           - `http://<LAN_IP>:<PORT>/room/<ROOM_CODE>`
           - `http://localhost:<PORT>/room/<ROOM_CODE>`
      3. Friend opens the link in ANY browser (PC, phone, tablet, another laptop) OR
         pastes the link into "JOIN ROOM VIA LINK" in another Tkinter app instance.
      4. Endpoints:
           - `GET  /room/<code>`           -> Responsive HTML5/JS Live Multiplayer Web Client
           - `POST /api/room/<code>/join`  -> Joins as Player 2 (`{"player_name": ...}`)
           - `GET  /api/room/<code>/state` -> Full JSON room & DFA state + image URL
           - `GET  /api/room/<code>/image.png?round=...&revealed=...` -> Live PIL card PNG
           - `POST /api/room/<code>/guess` -> Submits Player 2 guess into atomic `_race_lock`
           - `POST /api/room/<code>/hint`  -> Reveals next shared DAG BFS hint
    """

    def __init__(self, gui_app: "WhosThatAnimalGUI") -> None:
        self.gui_app = gui_app
        self.httpd: Optional[ThreadingHTTPServer] = None
        self.server_thread: Optional[threading.Thread] = None
        self.port: int = 0
        self.lan_ip: str = "127.0.0.1"
        self.room_code: str = ""
        self.friend_connected: bool = False
        self.friend_name: str = ""
        self.last_message: str = "Waiting for opponent to join via Shareable Room Link..."
        self._lock = threading.Lock()
        self._ui_events: List[Any] = []

    def pop_ui_events(self) -> List[Any]:
        """Thread-safely pops pending UI update callbacks to run on the Tkinter main thread."""
        with self._lock:
            evts = list(self._ui_events)
            self._ui_events.clear()
            return evts

    @staticmethod
    def detect_lan_ip() -> str:
        """Detects the host machine's primary LAN IPv4 address with fallback to 127.0.0.1."""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.settimeout(0.4)
                s.connect(("8.8.8.8", 80))
                ip = s.getsockname()[0]
                if ip and not ip.startswith("127."):
                    return ip
        except Exception:
            pass
        try:
            hostname_ip = socket.gethostbyname(socket.gethostname())
            if hostname_ip and not hostname_ip.startswith("127."):
                return hostname_ip
        except Exception:
            pass
        return "127.0.0.1"

    @property
    def share_url(self) -> str:
        if not self.port or not self.room_code:
            return ""
        return f"http://{self.lan_ip}:{self.port}/room/{self.room_code}"

    @property
    def localhost_url(self) -> str:
        if not self.port or not self.room_code:
            return ""
        return f"http://127.0.0.1:{self.port}/room/{self.room_code}"

    def start_room(self, preferred_port: int = 0) -> str:
        """Starts the background ThreadingHTTPServer and returns the Shareable Room Link."""
        self.stop_room()
        self.lan_ip = self.detect_lan_ip()
        digits = "".join(secrets.choice("23456789") for _ in range(3))
        letters = "".join(secrets.choice("ABCDEFGHJKLMNPQRSTUVWXYZ") for _ in range(3))
        self.room_code = f"ANM{digits}" if random.random() < 0.5 else f"{letters}{digits}"
        self.friend_connected = False
        self.friend_name = ""
        self.last_message = "⏳ Waiting for friend to open the room link & join..."

        parent_server = self

        class RoomRequestHandler(BaseHTTPRequestHandler):
            def log_message(self, format: str, *args: Any) -> None:
                return  # Keep console clean

            def _send_json(self, payload: Dict[str, Any], status: int = 200) -> None:
                raw = json.dumps(payload, default=str).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(raw)))
                self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(raw)

            def _send_html(self, html_str: str, status: int = 200) -> None:
                raw = html_str.encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            def do_OPTIONS(self) -> None:
                self.send_response(204)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
                self.send_header("Access-Control-Allow-Headers", "Content-Type")
                self.end_headers()

            def do_GET(self) -> None:
                parsed = urllib.parse.urlparse(self.path)
                path = parsed.path.rstrip("/")
                code = parent_server.room_code

                if path in ("", "/", f"/room/{code}", "/room"):
                    self._send_html(parent_server.build_web_client_html())
                    return

                if path == f"/api/room/{code}/state":
                    self._send_json(parent_server.get_room_state_dict())
                    return

                if path == f"/api/room/{code}/image.png":
                    qs = urllib.parse.parse_qs(parsed.query)
                    rev = qs.get("revealed", ["0"])[0] == "1"
                    png_bytes = parent_server.get_current_card_png(revealed=rev)
                    self.send_response(200)
                    self.send_header("Content-Type", "image/png")
                    self.send_header("Content-Length", str(len(png_bytes)))
                    self.send_header("Cache-Control", "no-cache")
                    self.end_headers()
                    self.wfile.write(png_bytes)
                    return

                self._send_json({"error": "Not found", "path": path}, status=404)

            def do_POST(self) -> None:
                parsed = urllib.parse.urlparse(self.path)
                path = parsed.path.rstrip("/")
                code = parent_server.room_code
                length = int(self.headers.get("Content-Length", "0") or "0")
                raw_body = self.rfile.read(length) if length > 0 else b"{}"
                try:
                    body = json.loads(raw_body.decode("utf-8"))
                except Exception:
                    body = {}

                if path == f"/api/room/{code}/join":
                    p_name = str(body.get("player_name", "")).strip() or "Remote_P2"
                    res = parent_server.handle_remote_join(p_name)
                    self._send_json(res)
                    return

                if path == f"/api/room/{code}/guess":
                    guess_str = str(body.get("guess", "")).strip()
                    p_num = int(body.get("player_num", 2))
                    res = parent_server.handle_remote_guess(p_num, guess_str)
                    self._send_json(res)
                    return

                if path == f"/api/room/{code}/hint":
                    res = parent_server.handle_remote_hint()
                    self._send_json(res)
                    return

                self._send_json({"error": "Unknown endpoint"}, status=404)

        try:
            self.httpd = ThreadingHTTPServer(("0.0.0.0", preferred_port), RoomRequestHandler)
        except OSError:
            self.httpd = ThreadingHTTPServer(("0.0.0.0", 0), RoomRequestHandler)

        self.port = int(self.httpd.server_address[1])
        self.server_thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.server_thread.start()
        return self.share_url

    def stop_room(self) -> None:
        if self.httpd is not None:
            try:
                self.httpd.shutdown()
                self.httpd.server_close()
            except Exception:
                pass
            self.httpd = None
        self.server_thread = None

    def get_current_card_png(self, revealed: bool = False) -> bytes:
        mp = self.gui_app.mp_controller
        info = self.gui_app._extract_animal_fields(mp.current_animal)
        is_rev = bool(revealed or mp.round_locked or self.gui_app._get_current_dfa_state() == GameState.GAME_OVER.value)
        return self.gui_app.silhouette_gen.render_card_png_bytes(info["image_path"], revealed=is_rev)

    def get_room_state_dict(self) -> Dict[str, Any]:
        mp = self.gui_app.mp_controller
        dfa_state = self.gui_app._get_current_dfa_state()
        revealed_flag = 1 if (mp.round_locked or dfa_state == GameState.GAME_OVER.value) else 0
        animal_name = (
            mp.current_animal.display_name
            if (mp.current_animal and revealed_flag)
            else "???"
        )
        return {
            "room_code": self.room_code,
            "dfa_state": dfa_state,
            "difficulty": getattr(mp, "difficulty", "MEDIUM"),
            "friend_connected": self.friend_connected,
            "friend_name": self.friend_name,
            "p1_name": mp.p1_name,
            "p2_name": mp.p2_name,
            "p1_score": mp.p1_score,
            "p2_score": mp.p2_score,
            "current_round": mp.current_round,
            "total_rounds": mp.TOTAL_ROUNDS,
            "time_remaining": mp.time_remaining,
            "potential_points": mp.current_potential_points,
            "hints_revealed": mp.hints_revealed,
            "revealed_hints": list(mp.current_hints[: mp.hints_revealed]),
            "round_locked": mp.round_locked,
            "round_winner": mp.round_winner,
            "revealed": bool(revealed_flag),
            "revealed_animal": animal_name,
            "match_over": dfa_state == GameState.GAME_OVER.value,
            "last_message": self.last_message,
            "image_url": f"/api/room/{self.room_code}/image.png?round={mp.current_round}&revealed={revealed_flag}",
        }

    def handle_remote_join(self, player_name: str) -> Dict[str, Any]:
        clean_name = player_name.strip()[:22] or "Remote_P2"
        with self._lock:
            self.friend_connected = True
            self.friend_name = clean_name
            self.last_message = f"🟢 {clean_name} joined Room {self.room_code} via Shareable Link!"
            self.gui_app.mp_controller.p2_name = clean_name
            self._ui_events.append(lambda n=clean_name: self.gui_app._on_remote_player_joined(n))
        return {"joined": True, "player_name": clean_name, "room_code": self.room_code, "state": self.get_room_state_dict()}

    def handle_remote_guess(self, player_num: int, guess_str: str) -> Dict[str, Any]:
        if not guess_str:
            return {"valid_submission": False, "correct": False, "message": "Empty guess."}
        res = dict(self.gui_app.mp_controller.submit_guess(player_num, guess_str))
        res.pop("animal", None)
        res["message"] = self.gui_app._clean_ui_message(res.get("message", ""))
        with self._lock:
            self.last_message = res["message"]
            self._ui_events.append(lambda p=player_num, r=dict(res): self.gui_app._apply_mp_guess_result_to_ui(p, r))
        res["state"] = self.get_room_state_dict()
        return res

    def handle_remote_hint(self) -> Dict[str, Any]:
        with self._lock:
            if not self.gui_app.mp_controller.round_locked:
                self.gui_app.mp_controller.reveal_shared_hint()
                self.last_message = f"💡 Shared Clue #{self.gui_app.mp_controller.hints_revealed} revealed!"
                self._ui_events.append(self.gui_app._apply_mp_hint_to_ui)
        return {"ok": True, "state": self.get_room_state_dict()}

    def build_web_client_html(self) -> str:
        """Returns a responsive HTML5/JS live multiplayer web client for the friend's browser."""
        code = self.room_code
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Who's That Animal? — Live Multiplayer Room {code}</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; font-family: 'Segoe UI', system-ui, sans-serif; }}
  body {{ background: #0f172a; color: #f8fafc; min-height: 100vh; display: flex; flex-direction: column; align-items: center; padding: 14px; }}
  .container {{ width: 100%; max-width: 780px; background: #1e293b; border: 1px solid #334155; border-radius: 14px; padding: 18px; box-shadow: 0 12px 32px rgba(0,0,0,0.45); }}
  .header {{ display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #334155; padding-bottom: 10px; margin-bottom: 12px; flex-wrap: wrap; gap: 8px; }}
  .badge {{ background: #38bdf8; color: #090d16; font-weight: 800; padding: 4px 10px; border-radius: 6px; font-family: Consolas, monospace; font-size: 13px; }}
  .scores {{ display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 12px; }}
  .score-card {{ background: #26354d; padding: 10px 14px; border-radius: 10px; border-left: 4px solid #38bdf8; }}
  .score-card.p2 {{ border-left-color: #fbbf24; }}
  .score-val {{ font-size: 24px; font-weight: 800; color: #34d399; font-family: Consolas, monospace; }}
  .arena {{ display: flex; flex-direction: column; align-items: center; background: #0f172a; border-radius: 12px; padding: 14px; margin-bottom: 12px; border: 1px solid #334155; }}
  .arena img {{ width: 290px; height: 245px; object-fit: contain; border-radius: 12px; margin: 8px 0; }}
  .hints {{ width: 100%; background: #26354d; padding: 10px 12px; border-radius: 8px; font-family: Consolas, monospace; font-size: 13px; color: #fbbf24; margin-top: 6px; white-space: pre-line; }}
  .controls {{ display: flex; gap: 8px; width: 100%; margin-top: 10px; }}
  input[type=text] {{ flex: 1; padding: 12px; border-radius: 8px; border: 2px solid #38bdf8; background: #0f172a; color: #f8fafc; font-size: 16px; font-weight: 700; outline: none; }}
  button {{ padding: 12px 18px; border: none; border-radius: 8px; font-weight: 800; cursor: pointer; font-size: 14px; }}
  .btn-join {{ background: #34d399; color: #090d16; }}
  .btn-guess {{ background: #fbbf24; color: #090d16; }}
  .btn-hint {{ background: #c084fc; color: #090d16; }}
  .status-banner {{ margin-top: 10px; padding: 10px; border-radius: 8px; background: #26354d; font-weight: 700; text-align: center; font-size: 14px; }}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <div>
      <h2 style="color:#38bdf8;">🐾 Who's That Animal? — Room <span style="color:#fbbf24;">{code}</span></h2>
      <div style="font-size:12px;color:#94a3b8;" id="roomSubtitle">Live 1v1 Multiplayer Match</div>
    </div>
    <div class="badge" id="roundTimer">ROUND 1/10 • ⏱ 60s</div>
  </div>

  <div id="joinBox" style="background:#26354d;padding:14px;border-radius:10px;margin-bottom:12px;">
    <div style="font-weight:700;margin-bottom:8px;color:#fbbf24;">🔗 Join this Live 1v1 Multiplayer Match as Player 2:</div>
    <div class="controls">
      <input type="text" id="playerNameInput" placeholder="Enter your player name (e.g. Wallace_P2)" value="Wallace_P2"/>
      <button class="btn-join" onclick="joinRoom()">JOIN ROOM ▶</button>
    </div>
  </div>

  <div class="scores">
    <div class="score-card">
      <div style="font-size:12px;color:#38bdf8;font-weight:700;">⚡ HOST (PLAYER 1)</div>
      <div id="p1Name" style="font-weight:700;font-size:16px;">Player 1</div>
      <div class="score-val" id="p1Score">0 PTS</div>
    </div>
    <div class="score-card p2">
      <div style="font-size:12px;color:#fbbf24;font-weight:700;">🔥 YOU (PLAYER 2)</div>
      <div id="p2Name" style="font-weight:700;font-size:16px;">Waiting...</div>
      <div class="score-val" id="p2Score">0 PTS</div>
    </div>
  </div>

  <div class="arena">
    <div id="rewardText" style="font-family:Consolas,monospace;color:#34d399;font-weight:700;">ROUND REWARD: 100 PTS</div>
    <img id="animalCardImg" src="/api/room/{code}/image.png?round=1&revealed=0" alt="Mystery Animal Shadow"/>
    <div class="hints" id="hintsBox">🧭 Clues:\n🔒 Clue 1: [Locked]\n🔒 Clue 2: [Locked]\n🔒 Clue 3: [Locked]</div>
  </div>

  <div class="controls">
    <input type="text" id="guessInput" placeholder="Type animal name & press Enter..." onkeydown="if(event.key==='Enter')submitGuess()"/>
    <button class="btn-guess" id="guessBtn" onclick="submitGuess()">GUESS ↵</button>
    <button class="btn-hint" id="hintBtn" onclick="requestHint()">💡 CLUE</button>
  </div>

  <div class="status-banner" id="statusBanner">⏳ Enter your name above and click JOIN ROOM!</div>
</div>

<script>
const ROOM_CODE = "{code}";
let lastImgKey = "";

async function joinRoom() {{
  const name = document.getElementById('playerNameInput').value.trim() || 'Wallace_P2';
  const res = await fetch(`/api/room/${{ROOM_CODE}}/join`, {{
    method: 'POST',
    headers: {{'Content-Type': 'application/json'}},
    body: JSON.stringify({{player_name: name}})
  }});
  const data = await res.json();
  if (data.joined) {{
    document.getElementById('joinBox').style.display = 'none';
    document.getElementById('statusBanner').textContent = '🟢 Joined as ' + data.player_name + '! Guess the animal before Player 1!';
    document.getElementById('guessInput').focus();
    if (data.state) renderState(data.state);
  }}
}}

async function submitGuess() {{
  const inp = document.getElementById('guessInput');
  const guess = inp.value.trim();
  if (!guess) return;
  inp.value = '';
  const res = await fetch(`/api/room/${{ROOM_CODE}}/guess`, {{
    method: 'POST',
    headers: {{'Content-Type': 'application/json'}},
    body: JSON.stringify({{player_num: 2, guess: guess}})
  }});
  const data = await res.json();
  if (data.message) {{
    const sb = document.getElementById('statusBanner');
    sb.textContent = (data.correct ? '🏆 ' : (data.locked_out ? '🔒 ' : '❌ ')) + data.message;
    sb.style.color = data.correct ? '#34d399' : '#f87171';
  }}
  if (data.state) renderState(data.state);
}}

async function requestHint() {{
  const res = await fetch(`/api/room/${{ROOM_CODE}}/hint`, {{ method: 'POST', body: '{{}}' }});
  const data = await res.json();
  if (data.state) renderState(data.state);
}}

function renderState(st) {{
  const diffLabel = st.difficulty ? ` • Level: ${{st.difficulty}}` : '';
  document.getElementById('roomSubtitle').textContent = `Room Code: ${{st.room_code}}${{diffLabel}} • Live 1v1 Match`;
  document.getElementById('roundTimer').textContent = `ROUND ${{st.current_round}}/${{st.total_rounds}} • ⏱ ${{st.time_remaining}}s`;
  document.getElementById('p1Name').textContent = st.p1_name;
  document.getElementById('p2Name').textContent = st.p2_name;
  document.getElementById('p1Score').textContent = st.p1_score + ' PTS';
  document.getElementById('p2Score').textContent = st.p2_score + ' PTS';
  document.getElementById('rewardText').textContent = st.revealed
    ? `✅ IT'S A ${{st.revealed_animal.toUpperCase()}}!`
    : `ROUND REWARD: ${{st.potential_points}} PTS`;

  const imgKey = `${{st.current_round}}_${{st.revealed ? 1 : 0}}`;
  if (imgKey !== lastImgKey) {{
    lastImgKey = imgKey;
    document.getElementById('animalCardImg').src = st.image_url + '&t=' + Date.now();
  }}

  let hLines = ['🧭 Clues:'];
  for (let i = 0; i < 3; i++) {{
    if (i < st.revealed_hints.length) hLines.push(`🔓 Clue ${{i+1}}: ${{st.revealed_hints[i]}}`);
    else hLines.push(`🔒 Clue ${{i+1}}: [Locked]`);
  }}
  document.getElementById('hintsBox').textContent = hLines.join('\\n');
  document.getElementById('guessInput').disabled = st.round_locked || st.match_over;
  document.getElementById('guessBtn').disabled = st.round_locked || st.match_over;
}}

async function pollState() {{
  try {{
    const res = await fetch(`/api/room/${{ROOM_CODE}}/state`);
    if (res.ok) {{
      const st = await res.json();
      renderState(st);
    }}
  }} catch (e) {{}}
}}
setInterval(pollState, 650);
pollState();
</script>
</body>
</html>"""


# ============================================================================
# 2. TKINTER EVENT-DRIVEN GUI (WhosThatAnimalGUI / WhosThatAnimalApp)
# ============================================================================

class WhosThatAnimalGUI:
    """
    Event-Driven Tkinter Desktop Application for "Who's That Animal?".

    Geometry Manager Architecture:
      - `pack()` is used for top-level structural stacks (main container, cards,
        and action button bars).
      - `grid()` is used for structured multi-column dashboards (Main Menu
        High Scores vs. Player Rankings tables, Single Player HUD metrics bar,
        and the 3-column Vertically Split Multiplayer Competitive Arena).
    """

    # Modern Dark Nature-Research / Arcade Palette
    BG_DARK = "#0f172a"       # Slate 900
    BG_PANEL = "#1e293b"      # Slate 800
    BG_CARD = "#26354d"       # Slate 750
    ACCENT_CYAN = "#38bdf8"   # Sky 400
    ACCENT_GREEN = "#34d399"  # Emerald 400
    ACCENT_AMBER = "#fbbf24"  # Amber 400
    ACCENT_RED = "#f87171"    # Red 400
    ACCENT_PURPLE = "#c084fc" # Purple 400
    TEXT_MAIN = "#f8fafc"     # Slate 50
    TEXT_MUTED = "#94a3b8"    # Slate 400

    def __init__(self, root: Optional[tk.Tk] = None) -> None:
        self.owns_root = root is None
        self.root: tk.Tk = root or tk.Tk()
        self.root.title("Who's That Animal?")
        self.root.geometry("1220x820")
        self.root.minsize(1080, 740)
        self.root.configure(bg=self.BG_DARK)

        # Initialize PIL Silhouette & Asset Manager
        self.silhouette_gen = SilhouetteGenerator()

        # Initialize shared DSA Engine Bundle & Game Logic Controllers
        self.bundle: DSAEngineBundle = create_default_dsa_bundle(self.silhouette_gen.assets_dir)
        self.dag = self.bundle.dag
        self.trie = self.bundle.trie
        self.lev_automaton = self.bundle.levenshtein
        self.leaderboard = self.bundle.leaderboard
        self.mmr_tree = self.bundle.mmr_tree

        self._sync_animal_asset_paths()

        self.dfa = GameDFA(on_transition=self._on_dfa_transition)
        self.sp_controller = SinglePlayerController(bundle=self.bundle, dfa=self.dfa)
        self.mp_controller = MultiplayerController(bundle=self.bundle, dfa=self.dfa)
        self.last_transition_text = "Ready"

        # Non-blocking `.after()` timer handles (strictly managed to avoid timer stacking)
        self._timer_after_id: Optional[str] = None
        self._transition_after_id: Optional[str] = None
        self._client_poll_after_id: Optional[str] = None

        # Multiplayer Room Server (Host) & Remote Link Client state
        self.room_server = MultiplayerRoomServer(self)
        self.hosting_room: bool = False
        self.remote_client_base_url: Optional[str] = None
        self.remote_room_code: Optional[str] = None
        self.join_link_var = tk.StringVar(value="")

        # Active UI state references
        self.active_mode: Optional[str] = None  # "SINGLE", "MULTI", or "MULTI_CLIENT"
        self.difficulty_var = tk.StringVar(value="MEDIUM")
        self.p1_name_var = tk.StringVar(value="Darwin_P1")
        self.p2_name_var = tk.StringVar(value="Wallace_P2")
        self.mmr_search_var = tk.StringVar(value="1225")

        # Build main container (`pack`)
        self._build_shell()

        # Render Main Menu on startup
        self.show_main_menu()

    def _sync_animal_asset_paths(self) -> None:
        """Ensures every AnimalRecord in the DAG points to a generated transparent PNG."""
        animals = self.dag.get_all_animals()
        for rec in animals:
            slug = rec.name.lower().strip().replace(" ", "_").replace("-", "_")
            expected_path = os.path.join(self.silhouette_gen.assets_dir, f"{slug}.png")
            if not os.path.exists(expected_path):
                self.silhouette_gen._draw_animal_sprite(slug, expected_path)
            rec.image_path = expected_path

    @staticmethod
    def _clean_ui_message(msg: str) -> str:
        """Strips internal technical/algorithmic annotations so GUI messages stay clean for players."""
        if not msg:
            return ""
        cleaned = msg
        # Remove parenthetical edit-distance notes such as "(fuzzy match via Levenshtein NFA, edit dist=1)"
        import re
        cleaned = re.sub(r"\s*\([^)]*(?:Levenshtein|edit dist|NFA|DFA|BFS|DAG|Heap|AVL)[^)]*\)", "", cleaned, flags=re.IGNORECASE)
        cleaned = cleaned.replace("race condition", "round").replace("Race Condition", "Round")
        return cleaned.strip()

    # ------------------------------------------------------------------
    # Top-Level Shell (Clean Container without technical jargon bar)
    # ------------------------------------------------------------------
    def _build_shell(self) -> None:
        """Builds the main dynamic content container (`pack`)."""
        self.main_container = tk.Frame(self.root, bg=self.BG_DARK)
        self.main_container.pack(side="top", fill="both", expand=True, padx=16, pady=12)

    def _on_dfa_transition(self, old_state: str, event: str, new_state: str) -> None:
        """Internal callback invoked whenever `GameDFA.trigger(event)` transitions state."""
        self.last_transition_text = f"{old_state} -> {new_state}"

    def _get_current_dfa_state(self) -> str:
        return self.dfa.current_state

    def _refresh_dfa_banner(self, explicit_transition: Optional[str] = None) -> None:
        if explicit_transition:
            self.last_transition_text = explicit_transition

    # ------------------------------------------------------------------
    # Timer Management (`.after()` Non-Blocking Requirement)
    # ------------------------------------------------------------------
    def _cancel_all_timers(self) -> None:
        """Cancels any scheduled `.after()` countdown or reveal transition callbacks."""
        if self._timer_after_id is not None:
            try:
                self.root.after_cancel(self._timer_after_id)
            except Exception:
                pass
            self._timer_after_id = None

        if self._transition_after_id is not None:
            try:
                self.root.after_cancel(self._transition_after_id)
            except Exception:
                pass
            self._transition_after_id = None

        if self._client_poll_after_id is not None:
            try:
                self.root.after_cancel(self._client_poll_after_id)
            except Exception:
                pass
            self._client_poll_after_id = None

    def _clear_container(self) -> None:
        self._cancel_all_timers()
        for child in self.main_container.winfo_children():
            child.destroy()

    # ==================================================================
    # VIEW 1: MAIN MENU (`MAIN_MENU`)
    # ==================================================================
    def show_main_menu(self) -> None:
        """Renders the Main Menu view with mode selectors, Room Link Hub, High Scores, and Player Rankings."""
        self._clear_container()
        if self.hosting_room:
            self.room_server.stop_room()
            self.hosting_room = False
        self.remote_client_base_url = None
        self.remote_room_code = None
        self.active_mode = None

        if self.dfa.current_state != GameState.MAIN_MENU.value:
            self.dfa.reset()
        self._refresh_dfa_banner()

        # Title Header (`pack`)
        header = tk.Frame(self.main_container, bg=self.BG_DARK, pady=4)
        header.pack(side="top", fill="x")

        tk.Label(
            header,
            text="🐾 WHO'S THAT ANIMAL? 🐾",
            font=("Segoe UI", 26, "bold"),
            fg=self.ACCENT_CYAN,
            bg=self.BG_DARK,
        ).pack(side="top")

        tk.Label(
            header,
            text="Guess the mystery animal from its shadow and clues!",
            font=("Segoe UI", 11),
            fg=self.TEXT_MUTED,
            bg=self.BG_DARK,
        ).pack(side="top", pady=(2, 8))

        # Mode Selection & Player Profile Bar (`pack` + `grid`)
        launch_card = tk.Frame(
            self.main_container,
            bg=self.BG_PANEL,
            padx=18,
            pady=12,
            highlightthickness=1,
            highlightbackground="#334155",
        )
        launch_card.pack(side="top", fill="x", pady=(0, 12))
        launch_card.grid_columnconfigure(0, weight=2)
        launch_card.grid_columnconfigure(1, weight=3)
        launch_card.grid_columnconfigure(2, weight=4)

        # Player Names Setup
        profile_frame = tk.Frame(launch_card, bg=self.BG_PANEL)
        profile_frame.grid(row=0, column=0, padx=8, sticky="nsew")

        tk.Label(
            profile_frame,
            text="PLAYER NAMES",
            font=("Segoe UI", 10, "bold"),
            fg=self.ACCENT_AMBER,
            bg=self.BG_PANEL,
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 6))

        tk.Label(profile_frame, text="Player 1 (Host):", font=("Segoe UI", 9), fg=self.TEXT_MAIN, bg=self.BG_PANEL).grid(
            row=1, column=0, sticky="w", pady=2
        )
        tk.Entry(
            profile_frame,
            textvariable=self.p1_name_var,
            font=("Consolas", 11, "bold"),
            bg=self.BG_CARD,
            fg=self.TEXT_MAIN,
            insertbackground=self.TEXT_MAIN,
            relief="flat",
            width=16,
        ).grid(row=1, column=1, padx=6, pady=2, sticky="w")

        tk.Label(profile_frame, text="Player 2 (Guest):", font=("Segoe UI", 9), fg=self.TEXT_MAIN, bg=self.BG_PANEL).grid(
            row=2, column=0, sticky="w", pady=2
        )
        tk.Entry(
            profile_frame,
            textvariable=self.p2_name_var,
            font=("Consolas", 11, "bold"),
            bg=self.BG_CARD,
            fg=self.TEXT_MAIN,
            insertbackground=self.TEXT_MAIN,
            relief="flat",
            width=16,
        ).grid(row=2, column=1, padx=6, pady=2, sticky="w")

        # Difficulty Level Selector (Easy / Medium / Hard)
        tk.Label(
            profile_frame,
            text="DIFFICULTY LEVEL",
            font=("Segoe UI", 9, "bold"),
            fg=self.ACCENT_CYAN,
            bg=self.BG_PANEL,
        ).grid(row=3, column=0, columnspan=2, sticky="w", pady=(8, 2))

        diff_bar = tk.Frame(profile_frame, bg=self.BG_PANEL)
        diff_bar.grid(row=4, column=0, columnspan=2, sticky="w")
        self._diff_buttons: Dict[str, tk.Button] = {}

        def _select_diff(level_name: str) -> None:
            self.difficulty_var.set(level_name)
            colors = {
                "EASY": self.ACCENT_GREEN,
                "MEDIUM": self.ACCENT_AMBER,
                "HARD": self.ACCENT_RED,
            }
            for lvl, btn in self._diff_buttons.items():
                if lvl == level_name:
                    btn.configure(bg=colors[lvl], fg="#090d16")
                else:
                    btn.configure(bg=self.BG_CARD, fg=self.TEXT_MUTED)

        for lvl_key, lvl_label in [("EASY", "🟢 Easy"), ("MEDIUM", "🟡 Medium"), ("HARD", "🔴 Difficult")]:
            b = tk.Button(
                diff_bar,
                text=lvl_label,
                command=lambda k=lvl_key: _select_diff(k),
                font=("Segoe UI", 8, "bold"),
                relief="flat",
                padx=8,
                pady=3,
                cursor="hand2",
            )
            b.pack(side="left", padx=(0, 4))
            self._diff_buttons[lvl_key] = b
        _select_diff(self.difficulty_var.get())

        # Single Player Button Card
        sp_frame = tk.Frame(
            launch_card,
            bg=self.BG_CARD,
            padx=14,
            pady=10,
            highlightthickness=1,
            highlightbackground=self.ACCENT_GREEN,
        )
        sp_frame.grid(row=0, column=1, padx=8, sticky="nsew")

        tk.Label(
            sp_frame,
            text="SINGLE PLAYER",
            font=("Segoe UI", 12, "bold"),
            fg=self.ACCENT_GREEN,
            bg=self.BG_CARD,
        ).pack(anchor="w")
        tk.Label(
            sp_frame,
            text="• 3 Lives (❤ ❤ ❤) & 30s Timer per animal\n• Up to 3 Clues (100 → 75 → 50 → 0 pts)\n• Type the animal name and press Enter",
            font=("Segoe UI", 9),
            fg=self.TEXT_MUTED,
            bg=self.BG_CARD,
            justify="left",
        ).pack(anchor="w", pady=4)
        tk.Button(
            sp_frame,
            text="▶ PLAY SINGLE PLAYER",
            command=self.start_single_player,
            font=("Segoe UI", 10, "bold"),
            bg=self.ACCENT_GREEN,
            fg="#090d16",
            activebackground="#10b981",
            relief="flat",
            cursor="hand2",
            padx=12,
            pady=6,
        ).pack(fill="x", pady=(4, 0))

        # Multiplayer & Shareable Room Link Card
        mp_frame = tk.Frame(
            launch_card,
            bg=self.BG_CARD,
            padx=14,
            pady=10,
            highlightthickness=1,
            highlightbackground=self.ACCENT_CYAN,
        )
        mp_frame.grid(row=0, column=2, padx=8, sticky="nsew")

        tk.Label(
            mp_frame,
            text="MULTIPLAYER (1v1)",
            font=("Segoe UI", 12, "bold"),
            fg=self.ACCENT_CYAN,
            bg=self.BG_CARD,
        ).pack(anchor="w")

        tk.Label(
            mp_frame,
            text="• Create a Room & send the invite link to a friend, or play on 1 screen!",
            font=("Segoe UI", 9),
            fg=self.TEXT_MUTED,
            bg=self.BG_CARD,
            justify="left",
        ).pack(anchor="w", pady=(2, 4))

        btn_row_mp = tk.Frame(mp_frame, bg=self.BG_CARD)
        btn_row_mp.pack(fill="x", pady=(2, 6))

        tk.Button(
            btn_row_mp,
            text="🌐 CREATE ROOM & GET LINK",
            command=self.create_multiplayer_room_and_start,
            font=("Segoe UI", 9, "bold"),
            bg=self.ACCENT_AMBER,
            fg="#090d16",
            activebackground="#f59e0b",
            relief="flat",
            cursor="hand2",
            padx=10,
            pady=6,
        ).pack(side="left", fill="x", expand=True, padx=(0, 4))

        tk.Button(
            btn_row_mp,
            text="⚔ PLAY ON THIS SCREEN",
            command=self.start_multiplayer,
            font=("Segoe UI", 9, "bold"),
            bg=self.ACCENT_CYAN,
            fg="#090d16",
            activebackground="#0284c7",
            relief="flat",
            cursor="hand2",
            padx=10,
            pady=6,
        ).pack(side="left", fill="x", expand=True, padx=(4, 0))

        # Join Room via Pasted Link Row
        join_row = tk.Frame(mp_frame, bg=self.BG_CARD)
        join_row.pack(fill="x", pady=(2, 0))

        tk.Label(
            join_row,
            text="🔗 Room Link:",
            font=("Segoe UI", 9, "bold"),
            fg=self.TEXT_MUTED,
            bg=self.BG_CARD,
        ).pack(side="left")

        join_entry = tk.Entry(
            join_row,
            textvariable=self.join_link_var,
            font=("Consolas", 9),
            bg=self.BG_DARK,
            fg=self.ACCENT_GREEN,
            insertbackground=self.TEXT_MAIN,
            relief="flat",
        )
        join_entry.pack(side="left", fill="x", expand=True, padx=6, ipady=3)
        join_entry.bind("<Return>", lambda _e: self.join_multiplayer_via_link())

        tk.Button(
            join_row,
            text="JOIN ROOM ▶",
            command=self.join_multiplayer_via_link,
            font=("Segoe UI", 8, "bold"),
            bg=self.ACCENT_PURPLE,
            fg="#090d16",
            relief="flat",
            cursor="hand2",
            padx=8,
            pady=3,
        ).pack(side="right")

        # Lower 2-Column Dashboard (`grid`): Left = High Scores, Right = Player Rankings
        dashboard = tk.Frame(self.main_container, bg=self.BG_DARK)
        dashboard.pack(side="top", fill="both", expand=True)
        dashboard.grid_columnconfigure(0, weight=1)
        dashboard.grid_columnconfigure(1, weight=1)
        dashboard.grid_rowconfigure(0, weight=1)

        self._build_leaderboard_panel(dashboard)
        self._build_avl_mmr_panel(dashboard)

    def _build_leaderboard_panel(self, parent: tk.Frame) -> None:
        """Renders the High Score Leaderboard panel."""
        panel = tk.Frame(
            parent,
            bg=self.BG_PANEL,
            padx=16,
            pady=14,
            highlightthickness=1,
            highlightbackground="#334155",
        )
        panel.grid(row=0, column=0, padx=(0, 8), sticky="nsew")

        tk.Label(
            panel,
            text="🏆 HIGH SCORES",
            font=("Segoe UI", 13, "bold"),
            fg=self.ACCENT_AMBER,
            bg=self.BG_PANEL,
        ).pack(anchor="w")

        tk.Label(
            panel,
            text="Top animal spotters and highest survival & match scores",
            font=("Segoe UI", 9),
            fg=self.TEXT_MUTED,
            bg=self.BG_PANEL,
        ).pack(anchor="w", pady=(0, 8))

        # Top Champion Callout
        top_entry = self.leaderboard.get_top()
        champ_text = (
            f"👑 Top Champion: {top_entry[0]} — {top_entry[1]} pts"
            if top_entry
            else "👑 No scores recorded yet"
        )
        tk.Label(
            panel,
            text=champ_text,
            font=("Segoe UI", 11, "bold"),
            fg="#090d16",
            bg=self.ACCENT_AMBER,
            padx=10,
            pady=5,
        ).pack(fill="x", pady=(0, 10))

        # Top-K Table using `grid()`
        table = tk.Frame(panel, bg=self.BG_CARD, padx=10, pady=8)
        table.pack(fill="both", expand=True)
        table.grid_columnconfigure(1, weight=1)

        headers = ["Rank", "Player", "Score"]
        for c_idx, h_text in enumerate(headers):
            tk.Label(
                table,
                text=h_text,
                font=("Segoe UI", 9, "bold"),
                fg=self.ACCENT_CYAN,
                bg=self.BG_CARD,
            ).grid(row=0, column=c_idx, sticky="w" if c_idx < 2 else "e", padx=6, pady=4)

        top_k = self.leaderboard.get_top_k(8)
        for idx, item in enumerate(top_k, start=1):
            p_name, p_score = item[0], item[1]
            fg_col = self.ACCENT_AMBER if idx == 1 else self.TEXT_MAIN
            tk.Label(table, text=f"#{idx}", font=("Consolas", 10, "bold"), fg=fg_col, bg=self.BG_CARD).grid(
                row=idx, column=0, sticky="w", padx=6, pady=3
            )
            tk.Label(table, text=str(p_name), font=("Segoe UI", 10), fg=fg_col, bg=self.BG_CARD).grid(
                row=idx, column=1, sticky="w", padx=6, pady=3
            )
            tk.Label(table, text=f"{p_score} pts", font=("Consolas", 10, "bold"), fg=self.ACCENT_GREEN, bg=self.BG_CARD).grid(
                row=idx, column=2, sticky="e", padx=6, pady=3
            )

    def _build_avl_mmr_panel(self, parent: tk.Frame) -> None:
        """Renders the Player Skill Rankings & Opponent Finder panel."""
        panel = tk.Frame(
            parent,
            bg=self.BG_PANEL,
            padx=16,
            pady=14,
            highlightthickness=1,
            highlightbackground="#334155",
        )
        panel.grid(row=0, column=1, padx=(8, 0), sticky="nsew")

        tk.Label(
            panel,
            text="🎖 PLAYER RANKINGS",
            font=("Segoe UI", 13, "bold"),
            fg=self.ACCENT_PURPLE,
            bg=self.BG_PANEL,
        ).pack(anchor="w")

        tk.Label(
            panel,
            text="Skill ratings and win records across Single Player & Multiplayer matches",
            font=("Segoe UI", 9),
            fg=self.TEXT_MUTED,
            bg=self.BG_PANEL,
        ).pack(anchor="w", pady=(0, 8))

        # Closest Rating Match Finder bar
        finder_bar = tk.Frame(panel, bg=self.BG_CARD, padx=10, pady=6)
        finder_bar.pack(fill="x", pady=(0, 10))

        tk.Label(
            finder_bar,
            text="Find Opponent by Rating:",
            font=("Segoe UI", 9, "bold"),
            fg=self.TEXT_MAIN,
            bg=self.BG_CARD,
        ).pack(side="left")

        tk.Entry(
            finder_bar,
            textvariable=self.mmr_search_var,
            font=("Consolas", 10, "bold"),
            width=7,
            bg=self.BG_DARK,
            fg=self.ACCENT_CYAN,
            insertbackground=self.TEXT_MAIN,
            relief="flat",
        ).pack(side="left", padx=6)

        self.mmr_match_result_lbl = tk.Label(
            finder_bar,
            text="",
            font=("Consolas", 9, "bold"),
            fg=self.ACCENT_GREEN,
            bg=self.BG_CARD,
        )

        def _run_mmr_query() -> None:
            try:
                target_val = int(self.mmr_search_var.get().strip())
            except ValueError:
                target_val = 1200
            match = self.mmr_tree.find_closest_match(target_val)
            if match:
                pid = match.get("player_id", match.get("name", "?"))
                mmr_v = match.get("mmr", 0)
                self.mmr_match_result_lbl.configure(text=f"→ Closest Match: {pid} ({mmr_v})")
            else:
                self.mmr_match_result_lbl.configure(text="→ No opponent found")

        tk.Button(
            finder_bar,
            text="Find Opponent",
            command=_run_mmr_query,
            font=("Segoe UI", 8, "bold"),
            bg=self.ACCENT_PURPLE,
            fg="#090d16",
            relief="flat",
            padx=8,
            pady=2,
            cursor="hand2",
        ).pack(side="left", padx=4)
        self.mmr_match_result_lbl.pack(side="left", padx=6)
        _run_mmr_query()

        # Rankings Table (`grid`)
        table = tk.Frame(panel, bg=self.BG_CARD, padx=10, pady=8)
        table.pack(fill="both", expand=True)
        table.grid_columnconfigure(1, weight=1)

        cols = ["Rank", "Player", "Rating", "Wins / Games"]
        for c_i, col_title in enumerate(cols):
            tk.Label(
                table,
                text=col_title,
                font=("Segoe UI", 9, "bold"),
                fg=self.ACCENT_CYAN,
                bg=self.BG_CARD,
            ).grid(row=0, column=c_i, sticky="w" if c_i < 2 else "e", padx=6, pady=4)

        rankings = self.mmr_tree.inorder_rankings()
        sorted_rankings = (
            list(reversed(rankings))
            if rankings and rankings[0].get("mmr", 0) < rankings[-1].get("mmr", 0)
            else rankings
        )
        for idx, r_item in enumerate(sorted_rankings[:8], start=1):
            pid = r_item.get("player_id", r_item.get("name", f"Player_{idx}"))
            mmr_val = r_item.get("mmr", 1200)
            wins = r_item.get("wins", 0)
            games = r_item.get("games", 0)
            tk.Label(table, text=f"#{idx}", font=("Consolas", 10, "bold"), fg=self.ACCENT_PURPLE, bg=self.BG_CARD).grid(
                row=idx, column=0, sticky="w", padx=6, pady=3
            )
            tk.Label(table, text=str(pid), font=("Segoe UI", 10), fg=self.TEXT_MAIN, bg=self.BG_CARD).grid(
                row=idx, column=1, sticky="w", padx=6, pady=3
            )
            tk.Label(table, text=f"{mmr_val}", font=("Consolas", 10, "bold"), fg=self.ACCENT_AMBER, bg=self.BG_CARD).grid(
                row=idx, column=2, sticky="e", padx=6, pady=3
            )
            tk.Label(table, text=f"{wins}W / {games}G", font=("Consolas", 9), fg=self.TEXT_MUTED, bg=self.BG_CARD).grid(
                row=idx, column=3, sticky="e", padx=6, pady=3
            )

    # ==================================================================
    # VIEW 2: SINGLE PLAYER SURVIVAL MODE
    # ==================================================================
    def start_single_player(self) -> None:
        """Initializes Single Player Survival mode."""
        self._clear_container()
        self.active_mode = "SINGLE"

        player_name = self.p1_name_var.get().strip() or "Darwin_P1"
        diff = self.difficulty_var.get().strip().upper() or "MEDIUM"
        self.sp_controller.start_game(player_name=player_name, difficulty=diff)

        self._build_single_player_ui()
        self._load_single_player_round_view(revealed=False)
        self._start_sp_timer()

    def _build_single_player_ui(self) -> None:
        """Constructs the Single Player HUD (`grid`), Animal Shadow Canvas, Clues Panel, and Input Entry."""
        hud = tk.Frame(
            self.main_container,
            bg=self.BG_PANEL,
            padx=16,
            pady=10,
            highlightthickness=1,
            highlightbackground="#334155",
        )
        hud.pack(side="top", fill="x", pady=(0, 10))
        for col_i in range(6):
            hud.grid_columnconfigure(col_i, weight=1)

        diff_label = {"EASY": "Easy", "MEDIUM": "Medium", "HARD": "Difficult"}.get(
            getattr(self.sp_controller, "difficulty", "MEDIUM"), "Medium"
        )
        self.sp_player_lbl = tk.Label(
            hud,
            text=f"👤 {self.sp_controller.player_name} ({diff_label})",
            font=("Segoe UI", 12, "bold"),
            fg=self.ACCENT_CYAN,
            bg=self.BG_PANEL,
        )
        self.sp_player_lbl.grid(row=0, column=0, sticky="w")

        self.sp_score_lbl = tk.Label(
            hud,
            text="SCORE: 0",
            font=("Consolas", 14, "bold"),
            fg=self.ACCENT_GREEN,
            bg=self.BG_PANEL,
        )
        self.sp_score_lbl.grid(row=0, column=1)

        self.sp_lives_lbl = tk.Label(
            hud,
            text="LIVES: ❤ ❤ ❤ (3)",
            font=("Segoe UI", 13, "bold"),
            fg=self.ACCENT_RED,
            bg=self.BG_PANEL,
        )
        self.sp_lives_lbl.grid(row=0, column=2)

        self.sp_reward_lbl = tk.Label(
            hud,
            text="REWARD: 100 PTS",
            font=("Consolas", 12, "bold"),
            fg=self.ACCENT_AMBER,
            bg=self.BG_PANEL,
        )
        self.sp_reward_lbl.grid(row=0, column=3)

        self.sp_strikes_lbl = tk.Label(
            hud,
            text="MISTAKES: 0 / 3",
            font=("Consolas", 11, "bold"),
            fg=self.TEXT_MUTED,
            bg=self.BG_PANEL,
        )
        self.sp_strikes_lbl.grid(row=0, column=4)

        self.sp_timer_lbl = tk.Label(
            hud,
            text="⏱ 30s",
            font=("Consolas", 15, "bold"),
            fg=self.ACCENT_CYAN,
            bg=self.BG_PANEL,
        )
        self.sp_timer_lbl.grid(row=0, column=5, sticky="e")

        # Main Split Content Area (`grid`: Left = Shadow Card, Right = Clues Panel)
        body = tk.Frame(self.main_container, bg=self.BG_DARK)
        body.pack(side="top", fill="both", expand=True, pady=(0, 10))
        body.grid_columnconfigure(0, weight=5)
        body.grid_columnconfigure(1, weight=6)
        body.grid_rowconfigure(0, weight=1)

        # Left Column: Animal Shadow Display Card
        canvas_card = tk.Frame(
            body,
            bg=self.BG_PANEL,
            padx=16,
            pady=14,
            highlightthickness=1,
            highlightbackground="#334155",
        )
        canvas_card.grid(row=0, column=0, padx=(0, 8), sticky="nsew")

        self.sp_card_title = tk.Label(
            canvas_card,
            text="🔍 WHO'S THAT ANIMAL?",
            font=("Segoe UI", 12, "bold"),
            fg=self.ACCENT_CYAN,
            bg=self.BG_PANEL,
        )
        self.sp_card_title.pack(side="top", pady=(0, 8))

        self.sp_image_lbl = tk.Label(canvas_card, bg=self.BG_PANEL)
        self.sp_image_lbl.pack(side="top", expand=True)

        self.sp_taxonomy_lbl = tk.Label(
            canvas_card,
            text="Guess the animal from its shadow or reveal a clue!",
            font=("Segoe UI", 9),
            fg=self.TEXT_MUTED,
            bg=self.BG_PANEL,
            wraplength=360,
            justify="center",
        )
        self.sp_taxonomy_lbl.pack(side="bottom", pady=(6, 0))

        # Right Column: Clues Panel & Controls
        hint_card = tk.Frame(
            body,
            bg=self.BG_PANEL,
            padx=18,
            pady=14,
            highlightthickness=1,
            highlightbackground="#334155",
        )
        hint_card.grid(row=0, column=1, padx=(8, 0), sticky="nsew")

        tk.Label(
            hint_card,
            text="🧭 CLUES & HINTS",
            font=("Segoe UI", 12, "bold"),
            fg=self.ACCENT_AMBER,
            bg=self.BG_PANEL,
        ).pack(anchor="w")

        tk.Label(
            hint_card,
            text="Need help? Reveal up to 3 clues about the mystery animal.",
            font=("Segoe UI", 9),
            fg=self.TEXT_MUTED,
            bg=self.BG_PANEL,
        ).pack(anchor="w", pady=(2, 10))

        self.sp_hint_boxes: List[tk.Label] = []
        hint_titles = [
            "Clue 1 (75 pts) — Animal Group:",
            "Clue 2 (50 pts) — Habitat & Region:",
            "Clue 3 (0 pts)  — Key Trait:",
        ]
        for h_title in hint_titles:
            tk.Label(
                hint_card,
                text=h_title,
                font=("Segoe UI", 9, "bold"),
                fg=self.ACCENT_CYAN,
                bg=self.BG_PANEL,
            ).pack(anchor="w", pady=(4, 2))
            lbl = tk.Label(
                hint_card,
                text="🔒 [Locked — Click 'Reveal Next Clue' below]",
                font=("Consolas", 10),
                fg=self.TEXT_MUTED,
                bg=self.BG_CARD,
                anchor="w",
                justify="left",
                wraplength=520,
                padx=12,
                pady=8,
            )
            lbl.pack(fill="x", pady=(0, 6))
            self.sp_hint_boxes.append(lbl)

        # Clue Action Buttons
        btn_row = tk.Frame(hint_card, bg=self.BG_PANEL)
        btn_row.pack(fill="x", pady=(8, 4))

        self.sp_hint_btn = tk.Button(
            btn_row,
            text="💡 REVEAL NEXT CLUE",
            command=self._on_sp_request_hint,
            font=("Segoe UI", 10, "bold"),
            bg=self.ACCENT_PURPLE,
            fg="#090d16",
            activebackground="#a855f7",
            relief="flat",
            padx=14,
            pady=6,
            cursor="hand2",
        )
        self.sp_hint_btn.pack(side="left", padx=(0, 8))

        self.sp_skip_btn = tk.Button(
            btn_row,
            text="⏭ NEXT ANIMAL (0 PTS)",
            command=self._on_sp_skip_after_all_hints,
            font=("Segoe UI", 10, "bold"),
            bg=self.BG_CARD,
            fg=self.TEXT_MUTED,
            relief="flat",
            padx=12,
            pady=6,
            state="disabled",
        )
        self.sp_skip_btn.pack(side="left")

        tk.Button(
            btn_row,
            text="⬅ MAIN MENU",
            command=self.show_main_menu,
            font=("Segoe UI", 9, "bold"),
            bg="#334155",
            fg=self.TEXT_MAIN,
            relief="flat",
            padx=10,
            pady=6,
            cursor="hand2",
        ).pack(side="right")

        # Bottom Input Bar (`pack`)
        input_card = tk.Frame(
            self.main_container,
            bg=self.BG_PANEL,
            padx=18,
            pady=12,
            highlightthickness=2,
            highlightbackground=self.ACCENT_CYAN,
        )
        input_card.pack(side="bottom", fill="x")

        entry_row = tk.Frame(input_card, bg=self.BG_PANEL)
        entry_row.pack(fill="x")

        tk.Label(
            entry_row,
            text="YOUR GUESS (Press Enter):",
            font=("Segoe UI", 11, "bold"),
            fg=self.TEXT_MAIN,
            bg=self.BG_PANEL,
        ).pack(side="left", padx=(0, 10))

        self.sp_guess_var = tk.StringVar()
        self.sp_entry = tk.Entry(
            entry_row,
            textvariable=self.sp_guess_var,
            font=("Consolas", 14, "bold"),
            bg=self.BG_CARD,
            fg=self.ACCENT_GREEN,
            insertbackground=self.TEXT_MAIN,
            relief="flat",
        )
        self.sp_entry.pack(side="left", fill="x", expand=True, ipady=6, padx=(0, 10))
        self.sp_entry.bind("<Return>", lambda _e: self._on_sp_submit_guess())

        self.sp_submit_btn = tk.Button(
            entry_row,
            text="GUESS ↵",
            command=self._on_sp_submit_guess,
            font=("Segoe UI", 11, "bold"),
            bg=self.ACCENT_GREEN,
            fg="#090d16",
            relief="flat",
            padx=18,
            pady=6,
            cursor="hand2",
        )
        self.sp_submit_btn.pack(side="right")

        self.sp_feedback_lbl = tk.Label(
            input_card,
            text="Type the animal's name and press Enter (small spelling mistakes are forgiven!).",
            font=("Segoe UI", 10, "bold"),
            fg=self.TEXT_MUTED,
            bg=self.BG_PANEL,
            anchor="w",
        )
        self.sp_feedback_lbl.pack(fill="x", pady=(6, 0))

    def _extract_animal_fields(self, animal: Optional[dsa_engine.AnimalRecord]) -> Dict[str, str]:
        if animal is None:
            return {
                "name": "african elephant",
                "display_name": "African Elephant",
                "kingdom": "Animalia",
                "animal_class": "Mammalia",
                "order": "Proboscidea",
                "region": "Sub-Saharan Africa",
                "trait": "Largest land mammal with trunk and tusks",
                "image_path": os.path.join(self.silhouette_gen.assets_dir, "african_elephant.png"),
            }
        slug = animal.name.lower().replace(" ", "_").replace("-", "_")
        img_path = animal.image_path or os.path.join(self.silhouette_gen.assets_dir, f"{slug}.png")
        if not os.path.isabs(img_path):
            img_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), img_path)
        return {
            "name": animal.name,
            "display_name": animal.display_name,
            "kingdom": animal.kingdom,
            "animal_class": animal.animal_class,
            "order": animal.order,
            "region": animal.region,
            "trait": animal.trait,
            "image_path": img_path,
        }

    def _load_single_player_round_view(self, revealed: bool = False) -> None:
        """Refreshes the Single Player HUD, Animal Card, and revealed clues."""
        if self._get_current_dfa_state() == GameState.GAME_OVER.value:
            self._show_game_over_modal("SINGLE")
            return

        info = self._extract_animal_fields(self.sp_controller.current_animal)

        photo = self.silhouette_gen.render_card_photo(
            info["image_path"],
            revealed=revealed,
            card_size=(310, 265),
            sprite_size=(245, 245),
        )
        self.sp_image_lbl.configure(image=photo)
        self.sp_image_lbl.image = photo

        if revealed:
            self.sp_card_title.configure(
                text=f"✅ IT'S A {info['display_name'].upper()}!",
                fg=self.ACCENT_GREEN,
            )
            self.sp_taxonomy_lbl.configure(
                text=f"{info['animal_class']} • {info['order']} • {info['display_name']}",
                fg=self.ACCENT_GREEN,
            )
        else:
            self.sp_card_title.configure(
                text=f"🔍 ANIMAL #{self.sp_controller.round_number}: WHO'S THAT ANIMAL?",
                fg=self.ACCENT_CYAN,
            )
            self.sp_taxonomy_lbl.configure(
                text="Identify the animal from its shadow or unlock a clue!",
                fg=self.TEXT_MUTED,
            )

        self._refresh_sp_hud_metrics()
        self._refresh_sp_hints_ui()
        if not revealed:
            self.sp_entry.configure(state="normal")
            self.sp_submit_btn.configure(state="normal")
            self.sp_guess_var.set("")
            self.sp_entry.focus_set()

    def _refresh_sp_hud_metrics(self) -> None:
        score = self.sp_controller.score
        lives = self.sp_controller.lives
        max_lives = getattr(self.sp_controller, "max_lives", 3)
        strikes = self.sp_controller.wrong_guesses
        timer_val = self.sp_controller.time_remaining
        potential = self.sp_controller.current_potential_points

        hearts = " ".join(["❤"] * max(0, lives)) + (
            " " + " ".join(["♡"] * max(0, max_lives - lives)) if lives < max_lives else ""
        )
        self.sp_score_lbl.configure(text=f"SCORE: {score}")
        self.sp_lives_lbl.configure(text=f"LIVES: {hearts} ({lives})")
        self.sp_reward_lbl.configure(text=f"REWARD: {potential} PTS")
        self.sp_strikes_lbl.configure(text=f"MISTAKES: {strikes} / 3")
        self.sp_timer_lbl.configure(
            text=f"⏱ {timer_val:02d}s",
            fg=self.ACCENT_RED if timer_val <= 8 else self.ACCENT_CYAN,
        )

    def _refresh_sp_hints_ui(self) -> None:
        hints_used = self.sp_controller.hints_revealed
        bfs_hints = self.sp_controller.current_hints

        for idx, box in enumerate(self.sp_hint_boxes):
            if idx < hints_used and idx < len(bfs_hints):
                box.configure(
                    text=f"🔓 {bfs_hints[idx]}",
                    fg=self.ACCENT_AMBER if idx < 2 else self.ACCENT_RED,
                    bg="#1e293b",
                )
            else:
                box.configure(
                    text="🔒 [Locked — Click 'Reveal Next Clue' below]",
                    fg=self.TEXT_MUTED,
                    bg=self.BG_CARD,
                )

        if hints_used >= 3:
            self.sp_hint_btn.configure(state="disabled", text="ALL 3 CLUES REVEALED (0 PTS)")
            self.sp_skip_btn.configure(state="normal", bg=self.ACCENT_AMBER, fg="#090d16")
        else:
            next_cost = {0: "75 pts", 1: "50 pts", 2: "0 pts"}[hints_used]
            self.sp_hint_btn.configure(state="normal", text=f"💡 REVEAL CLUE #{hints_used + 1} (Reward → {next_cost})")
            self.sp_skip_btn.configure(state="disabled", bg=self.BG_CARD, fg=self.TEXT_MUTED)

    def _start_sp_timer(self) -> None:
        """Starts the non-blocking 30-second Single Player countdown using `self.root.after(1000, ...)`."""
        self._cancel_all_timers()
        self._timer_after_id = self.root.after(1000, self._tick_sp_timer)

    def _tick_sp_timer(self) -> None:
        self._timer_after_id = None
        if self.active_mode != "SINGLE" or self._get_current_dfa_state() == GameState.GAME_OVER.value:
            return

        res = self.sp_controller.tick_timer(1)
        self._refresh_sp_hud_metrics()
        self._refresh_dfa_banner()

        if res.get("timed_out"):
            self._load_single_player_round_view(revealed=True)
            self.sp_entry.configure(state="disabled")
            self.sp_submit_btn.configure(state="disabled")
            self.sp_feedback_lbl.configure(
                text=f"⏰ {self._clean_ui_message(res.get('message', 'Time is up! -1 Life.'))}",
                fg=self.ACCENT_RED,
            )

            def _after_sp_timeout() -> None:
                if res.get("game_over") or self._get_current_dfa_state() == GameState.GAME_OVER.value:
                    self._show_game_over_modal("SINGLE")
                else:
                    next_anim = self.sp_controller.start_next_animal()
                    if next_anim is None or self._get_current_dfa_state() == GameState.GAME_OVER.value:
                        self._show_game_over_modal("SINGLE")
                    else:
                        self._load_single_player_round_view(revealed=False)
                        self._start_sp_timer()

            self._transition_after_id = self.root.after(1400, _after_sp_timeout)
            return

        self._timer_after_id = self.root.after(1000, self._tick_sp_timer)

    def _on_sp_request_hint(self) -> None:
        """Handles `"Reveal Next Clue"` button click."""
        if self.active_mode != "SINGLE" or not self.sp_controller.round_active:
            return

        res = self.sp_controller.reveal_hint()
        self._refresh_dfa_banner()
        self._refresh_sp_hud_metrics()
        self._refresh_sp_hints_ui()
        self.sp_feedback_lbl.configure(
            text=f"💡 {self._clean_ui_message(res.get('message', 'Clue revealed!'))}",
            fg=self.ACCENT_AMBER,
        )
        self.sp_entry.focus_set()

    def _on_sp_skip_after_all_hints(self) -> None:
        """Allows advancing for 0 points once all 3 clues have been revealed."""
        if self.active_mode != "SINGLE":
            return
        self._cancel_all_timers()
        res = self.sp_controller.skip_after_all_hints()
        self._load_single_player_round_view(revealed=True)
        self.sp_entry.configure(state="disabled")
        self.sp_submit_btn.configure(state="disabled")
        self.sp_feedback_lbl.configure(
            text=f"⏭ {self._clean_ui_message(res.get('message', 'Skipped for 0 pts.'))} Loading next animal...",
            fg=self.ACCENT_AMBER,
        )

        def _advance() -> None:
            next_anim = self.sp_controller.start_next_animal()
            if next_anim is None or self._get_current_dfa_state() == GameState.GAME_OVER.value:
                self._show_game_over_modal("SINGLE")
            else:
                self._load_single_player_round_view(revealed=False)
                self._start_sp_timer()

        self._transition_after_id = self.root.after(1300, _advance)

    def _on_sp_submit_guess(self) -> None:
        """Processes `<Return>` or Submit button in Single Player mode."""
        if self.active_mode != "SINGLE" or not self.sp_controller.round_active:
            return
        raw_guess = self.sp_guess_var.get().strip()
        if not raw_guess:
            return

        result = self.sp_controller.submit_guess(raw_guess)
        self.sp_guess_var.set("")

        self._refresh_dfa_banner()
        self._refresh_sp_hud_metrics()

        if result.get("correct"):
            self._cancel_all_timers()
            self._load_single_player_round_view(revealed=True)
            self.sp_entry.configure(state="disabled")
            self.sp_submit_btn.configure(state="disabled")
            self.sp_feedback_lbl.configure(
                text=f"🎉 {self._clean_ui_message(result.get('message', 'Correct!'))}",
                fg=self.ACCENT_GREEN,
            )

            def _next_sp() -> None:
                next_anim = self.sp_controller.start_next_animal()
                if next_anim is None or self._get_current_dfa_state() == GameState.GAME_OVER.value:
                    self._show_game_over_modal("SINGLE")
                else:
                    self._load_single_player_round_view(revealed=False)
                    self._start_sp_timer()

            self._transition_after_id = self.root.after(1350, _next_sp)
        else:
            if result.get("round_over"):
                self._cancel_all_timers()
                self._load_single_player_round_view(revealed=True)
                self.sp_entry.configure(state="disabled")
                self.sp_submit_btn.configure(state="disabled")
                self.sp_feedback_lbl.configure(
                    text=f"❌ {self._clean_ui_message(result.get('message', '3 wrong guesses! -1 Life.'))}",
                    fg=self.ACCENT_RED,
                )

                def _after_strike_out() -> None:
                    if result.get("game_over") or self._get_current_dfa_state() == GameState.GAME_OVER.value:
                        self._show_game_over_modal("SINGLE")
                    else:
                        next_anim = self.sp_controller.start_next_animal()
                        if next_anim is None or self._get_current_dfa_state() == GameState.GAME_OVER.value:
                            self._show_game_over_modal("SINGLE")
                        else:
                            self._load_single_player_round_view(revealed=False)
                            self._start_sp_timer()

                self._transition_after_id = self.root.after(1450, _after_strike_out)
            else:
                self.sp_feedback_lbl.configure(
                    text=f"❌ {self._clean_ui_message(result.get('message', 'Incorrect guess.'))}",
                    fg=self.ACCENT_RED,
                )

    # ==================================================================
    # VIEW 3: MULTIPLAYER ARENA (ROOM LINK & SPLIT-SCREEN)
    # ==================================================================
    def create_multiplayer_room_and_start(self) -> str:
        """
        Starts the Multiplayer HTTP Room Server, generates a Shareable Room Link,
        copies it to clipboard, and opens the Multiplayer Arena with the Room Link Bar.
        """
        self._clear_container()
        self.active_mode = "MULTI"
        self.hosting_room = True
        self.remote_client_base_url = None

        p1_name = self.p1_name_var.get().strip() or "Darwin_P1"
        p2_name = self.p2_name_var.get().strip() or "Waiting for Friend..."
        diff = self.difficulty_var.get().strip().upper() or "MEDIUM"
        self.mp_controller.start_match(p1_name=p1_name, p2_name=p2_name, difficulty=diff)

        share_url = self.room_server.start_room()
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(share_url)
        except Exception:
            pass

        self._build_multiplayer_ui(self.mp_controller.p1_name, self.mp_controller.p2_name)
        self._load_multiplayer_round_view(revealed=False)
        self._start_mp_timer()
        return share_url

    def join_multiplayer_via_link(self, explicit_url: Optional[str] = None) -> bool:
        """
        Connects this Tkinter app instance to a friend's Multiplayer Room Link (`http://.../room/<code>`).
        """
        raw_link = (explicit_url if explicit_url is not None else self.join_link_var.get()).strip()
        if not raw_link:
            messagebox.showwarning("Join Room", "Please paste a valid Room Link (e.g. http://192.168.1.5:54321/room/ANM123).")
            return False

        if not raw_link.startswith("http://") and not raw_link.startswith("https://"):
            raw_link = "http://" + raw_link

        parsed = urllib.parse.urlparse(raw_link)
        path_parts = [p for p in parsed.path.split("/") if p]
        room_code = path_parts[-1] if path_parts else ""
        base_url = f"{parsed.scheme}://{parsed.netloc}"

        guest_name = self.p2_name_var.get().strip() or "Wallace_P2"
        join_endpoint = f"{base_url}/api/room/{room_code}/join"
        try:
            req = urllib.request.Request(
                join_endpoint,
                data=json.dumps({"player_name": guest_name}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=2.5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception as exc:
            messagebox.showerror("Could Not Join Room", f"Could not connect to room link:\n{raw_link}\n\n({exc})")
            return False

        if not data.get("joined"):
            return False

        self._clear_container()
        self.active_mode = "MULTI_CLIENT"
        self.hosting_room = False
        self.remote_client_base_url = base_url
        self.remote_room_code = room_code

        st = data.get("state", {})
        p1_n = st.get("p1_name", "Host_P1")
        p2_n = st.get("p2_name", guest_name)
        self._build_multiplayer_ui(p1_n, p2_n)
        self._poll_remote_room_state()
        return True

    def _on_remote_player_joined(self, friend_name: str) -> None:
        """Invoked on the Host GUI when a friend joins via the Shareable Room Link."""
        self.p2_name_var.set(friend_name)
        self.mp_controller.p2_name = friend_name
        if hasattr(self, "mp_p2_name_lbl") and self.mp_p2_name_lbl.winfo_exists():
            self.mp_p2_name_lbl.configure(text=friend_name)
        if hasattr(self, "mp_room_status_lbl") and self.mp_room_status_lbl.winfo_exists():
            self.mp_room_status_lbl.configure(
                text=f"🟢 Connected! {friend_name} joined via link!",
                fg=self.ACCENT_GREEN,
            )
        if hasattr(self, "mp_banner_lbl") and self.mp_banner_lbl.winfo_exists():
            self.mp_banner_lbl.configure(
                text=f"🟢 {friend_name} joined the room! First right answer wins the round!",
                fg=self.ACCENT_GREEN,
            )

    def start_multiplayer(self) -> None:
        """Initializes 10-Round Multiplayer mode on the current screen (plus background room link)."""
        self._clear_container()
        self.active_mode = "MULTI"
        self.hosting_room = True
        self.remote_client_base_url = None

        p1_name = self.p1_name_var.get().strip() or "Darwin_P1"
        p2_name = self.p2_name_var.get().strip() or "Wallace_P2"
        diff = self.difficulty_var.get().strip().upper() or "MEDIUM"
        self.mp_controller.start_match(p1_name=p1_name, p2_name=p2_name, difficulty=diff)
        self.room_server.start_room()

        self._build_multiplayer_ui(self.mp_controller.p1_name, self.mp_controller.p2_name)
        self._load_multiplayer_round_view(revealed=False)
        self._start_mp_timer()

    def _copy_room_link_to_clipboard(self) -> None:
        url = self.room_server.share_url
        if not url:
            return
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(url)
            if hasattr(self, "mp_room_status_lbl") and self.mp_room_status_lbl.winfo_exists():
                self.mp_room_status_lbl.configure(
                    text="✅ Room Link copied! Send it to your friend to join!",
                    fg=self.ACCENT_GREEN,
                )
        except Exception:
            pass

    def _open_room_link_in_browser(self) -> None:
        url = self.room_server.localhost_url or self.room_server.share_url
        if url:
            webbrowser.open(url)

    def _build_multiplayer_ui(self, p1_name: str, p2_name: str) -> None:
        """
        Builds the Multiplayer Arena with the Shareable Room Link bar on top and the
        3-Column Split Arena below (`grid()`).
        """
        # Top Shareable Room Link Bar (`pack`)
        if self.hosting_room and self.room_server.share_url:
            room_bar = tk.Frame(
                self.main_container,
                bg=self.BG_PANEL,
                padx=14,
                pady=8,
                highlightthickness=1,
                highlightbackground=self.ACCENT_AMBER,
            )
            room_bar.pack(side="top", fill="x", pady=(0, 8))

            tk.Label(
                room_bar,
                text=f"🌐 ROOM {self.room_server.room_code} INVITE LINK:",
                font=("Segoe UI", 9, "bold"),
                fg=self.ACCENT_AMBER,
                bg=self.BG_PANEL,
            ).pack(side="left", padx=(0, 6))

            link_entry = tk.Entry(
                room_bar,
                font=("Consolas", 10, "bold"),
                bg=self.BG_DARK,
                fg=self.ACCENT_CYAN,
                relief="flat",
                width=38,
                readonlybackground=self.BG_DARK,
            )
            link_entry.insert(0, self.room_server.share_url)
            link_entry.configure(state="readonly")
            link_entry.pack(side="left", padx=4, ipady=3)

            tk.Button(
                room_bar,
                text="📋 Copy Invite Link",
                command=self._copy_room_link_to_clipboard,
                font=("Segoe UI", 9, "bold"),
                bg=self.ACCENT_GREEN,
                fg="#090d16",
                relief="flat",
                padx=10,
                pady=3,
                cursor="hand2",
            ).pack(side="left", padx=4)

            tk.Button(
                room_bar,
                text="🌐 Open Link in Browser",
                command=self._open_room_link_in_browser,
                font=("Segoe UI", 9, "bold"),
                bg=self.ACCENT_CYAN,
                fg="#090d16",
                relief="flat",
                padx=10,
                pady=3,
                cursor="hand2",
            ).pack(side="left", padx=4)

            self.mp_room_status_lbl = tk.Label(
                room_bar,
                text="⏳ Share this link with a friend to play from their browser or app!",
                font=("Segoe UI", 9, "bold"),
                fg=self.TEXT_MUTED,
                bg=self.BG_PANEL,
            )
            self.mp_room_status_lbl.pack(side="right", padx=6)

        arena = tk.Frame(self.main_container, bg=self.BG_DARK)
        arena.pack(side="top", fill="both", expand=True)
        arena.grid_columnconfigure(0, weight=3, uniform="player_col")
        arena.grid_columnconfigure(1, weight=5)
        arena.grid_columnconfigure(2, weight=3, uniform="player_col")
        arena.grid_rowconfigure(0, weight=1)

        # --------------------------------------------------------------
        # LEFT PANE: PLAYER 1 STATION (`grid` column 0)
        # --------------------------------------------------------------
        self.p1_pane = tk.Frame(
            arena,
            bg=self.BG_PANEL,
            padx=16,
            pady=16,
            highlightthickness=2,
            highlightbackground=self.ACCENT_CYAN,
        )
        self.p1_pane.grid(row=0, column=0, padx=(0, 8), sticky="nsew")

        tk.Label(
            self.p1_pane,
            text="⚡ PLAYER 1 (HOST)",
            font=("Segoe UI", 11, "bold"),
            fg=self.ACCENT_CYAN,
            bg=self.BG_PANEL,
        ).pack(anchor="w")

        self.mp_p1_name_lbl = tk.Label(
            self.p1_pane,
            text=p1_name,
            font=("Segoe UI", 18, "bold"),
            fg=self.TEXT_MAIN,
            bg=self.BG_PANEL,
        )
        self.mp_p1_name_lbl.pack(anchor="w", pady=(2, 8))

        self.mp_p1_score_lbl = tk.Label(
            self.p1_pane,
            text="0 PTS",
            font=("Consolas", 26, "bold"),
            fg=self.ACCENT_GREEN,
            bg=self.BG_CARD,
            pady=12,
        )
        self.mp_p1_score_lbl.pack(fill="x", pady=(0, 14))

        tk.Label(
            self.p1_pane,
            text="PLAYER 1 GUESS (Press Enter):",
            font=("Segoe UI", 9, "bold"),
            fg=self.ACCENT_CYAN,
            bg=self.BG_PANEL,
        ).pack(anchor="w", pady=(6, 4))

        self.mp_p1_var = tk.StringVar()
        self.mp_p1_entry = tk.Entry(
            self.p1_pane,
            textvariable=self.mp_p1_var,
            font=("Consolas", 14, "bold"),
            bg=self.BG_CARD,
            fg=self.ACCENT_CYAN,
            disabledbackground="#111827",
            disabledforeground=self.ACCENT_RED,
            insertbackground=self.TEXT_MAIN,
            relief="flat",
        )
        self.mp_p1_entry.pack(fill="x", ipady=8, pady=(0, 8))
        self.mp_p1_entry.bind("<Return>", lambda _e: self._on_mp_submit_guess(1))

        self.mp_p1_btn = tk.Button(
            self.p1_pane,
            text="PLAYER 1 GUESS ↵",
            command=lambda: self._on_mp_submit_guess(1),
            font=("Segoe UI", 10, "bold"),
            bg=self.ACCENT_CYAN,
            fg="#090d16",
            relief="flat",
            pady=8,
            cursor="hand2",
        )
        self.mp_p1_btn.pack(fill="x", pady=(0, 12))

        self.mp_p1_status = tk.Label(
            self.p1_pane,
            text="🟢 Ready! Type the animal name & press Enter!",
            font=("Segoe UI", 10, "bold"),
            fg=self.ACCENT_GREEN,
            bg=self.BG_CARD,
            wraplength=240,
            justify="left",
            padx=10,
            pady=12,
        )
        self.mp_p1_status.pack(fill="x", pady=(4, 0))

        # --------------------------------------------------------------
        # CENTER PANE: SHARED SILHOUETTE + 60s TIMER + CLUES (`grid` col 1)
        # --------------------------------------------------------------
        center_pane = tk.Frame(
            arena,
            bg=self.BG_PANEL,
            padx=16,
            pady=12,
            highlightthickness=1,
            highlightbackground="#334155",
        )
        center_pane.grid(row=0, column=1, padx=4, sticky="nsew")

        top_bar = tk.Frame(center_pane, bg=self.BG_PANEL)
        top_bar.pack(fill="x", pady=(0, 6))

        self.mp_round_lbl = tk.Label(
            top_bar,
            text="ROUND 1 / 10",
            font=("Consolas", 14, "bold"),
            fg=self.ACCENT_AMBER,
            bg=self.BG_PANEL,
        )
        self.mp_round_lbl.pack(side="left")

        self.mp_reward_lbl = tk.Label(
            top_bar,
            text="REWARD: 100 PTS",
            font=("Consolas", 11, "bold"),
            fg=self.ACCENT_GREEN,
            bg=self.BG_PANEL,
        )
        self.mp_reward_lbl.pack(side="left", padx=16)

        self.mp_timer_lbl = tk.Label(
            top_bar,
            text="⏱ 60s",
            font=("Consolas", 15, "bold"),
            fg=self.ACCENT_CYAN,
            bg=self.BG_PANEL,
        )
        self.mp_timer_lbl.pack(side="right")

        self.mp_banner_lbl = tk.Label(
            center_pane,
            text="⚡ First player to guess the animal wins the round's points!",
            font=("Segoe UI", 9, "bold"),
            fg=self.TEXT_MAIN,
            bg=self.BG_CARD,
            pady=5,
        )
        self.mp_banner_lbl.pack(fill="x", pady=(0, 8))

        self.mp_image_lbl = tk.Label(center_pane, bg=self.BG_PANEL)
        self.mp_image_lbl.pack(pady=4)

        # Shared Clues Box
        self.mp_hint_box = tk.Label(
            center_pane,
            text="🧭 Clues:\n• Click 'Reveal Clue' below if both players need a hint.",
            font=("Consolas", 9),
            fg=self.ACCENT_AMBER,
            bg=self.BG_CARD,
            justify="left",
            anchor="w",
            wraplength=420,
            padx=12,
            pady=8,
        )
        self.mp_hint_box.pack(fill="x", pady=6)

        ctrl_row = tk.Frame(center_pane, bg=self.BG_PANEL)
        ctrl_row.pack(fill="x", pady=(4, 0))

        self.mp_hint_btn = tk.Button(
            ctrl_row,
            text="💡 REVEAL CLUE",
            command=self._on_mp_request_hint,
            font=("Segoe UI", 9, "bold"),
            bg=self.ACCENT_PURPLE,
            fg="#090d16",
            relief="flat",
            padx=10,
            pady=5,
            cursor="hand2",
        )
        self.mp_hint_btn.pack(side="left")

        tk.Button(
            ctrl_row,
            text="⬅ EXIT TO MENU",
            command=self.show_main_menu,
            font=("Segoe UI", 9, "bold"),
            bg="#334155",
            fg=self.TEXT_MAIN,
            relief="flat",
            padx=10,
            pady=5,
            cursor="hand2",
        ).pack(side="right")

        # --------------------------------------------------------------
        # RIGHT PANE: PLAYER 2 STATION (`grid` column 2)
        # --------------------------------------------------------------
        self.p2_pane = tk.Frame(
            arena,
            bg=self.BG_PANEL,
            padx=16,
            pady=16,
            highlightthickness=2,
            highlightbackground=self.ACCENT_AMBER,
        )
        self.p2_pane.grid(row=0, column=2, padx=(8, 0), sticky="nsew")

        tk.Label(
            self.p2_pane,
            text="🔥 PLAYER 2 (FRIEND / GUEST)",
            font=("Segoe UI", 11, "bold"),
            fg=self.ACCENT_AMBER,
            bg=self.BG_PANEL,
        ).pack(anchor="w")

        self.mp_p2_name_lbl = tk.Label(
            self.p2_pane,
            text=p2_name,
            font=("Segoe UI", 18, "bold"),
            fg=self.TEXT_MAIN,
            bg=self.BG_PANEL,
        )
        self.mp_p2_name_lbl.pack(anchor="w", pady=(2, 8))

        self.mp_p2_score_lbl = tk.Label(
            self.p2_pane,
            text="0 PTS",
            font=("Consolas", 26, "bold"),
            fg=self.ACCENT_GREEN,
            bg=self.BG_CARD,
            pady=12,
        )
        self.mp_p2_score_lbl.pack(fill="x", pady=(0, 14))

        tk.Label(
            self.p2_pane,
            text="PLAYER 2 GUESS (Press Enter or via Room Link):",
            font=("Segoe UI", 9, "bold"),
            fg=self.ACCENT_AMBER,
            bg=self.BG_PANEL,
        ).pack(anchor="w", pady=(6, 4))

        self.mp_p2_var = tk.StringVar()
        self.mp_p2_entry = tk.Entry(
            self.p2_pane,
            textvariable=self.mp_p2_var,
            font=("Consolas", 14, "bold"),
            bg=self.BG_CARD,
            fg=self.ACCENT_AMBER,
            disabledbackground="#111827",
            disabledforeground=self.ACCENT_RED,
            insertbackground=self.TEXT_MAIN,
            relief="flat",
        )
        self.mp_p2_entry.pack(fill="x", ipady=8, pady=(0, 8))
        self.mp_p2_entry.bind("<Return>", lambda _e: self._on_mp_submit_guess(2))

        self.mp_p2_btn = tk.Button(
            self.p2_pane,
            text="PLAYER 2 GUESS ↵",
            command=lambda: self._on_mp_submit_guess(2),
            font=("Segoe UI", 10, "bold"),
            bg=self.ACCENT_AMBER,
            fg="#090d16",
            relief="flat",
            pady=8,
            cursor="hand2",
        )
        self.mp_p2_btn.pack(fill="x", pady=(0, 12))

        self.mp_p2_status = tk.Label(
            self.p2_pane,
            text="🟢 Ready! Type here or play via the Room Invite Link!",
            font=("Segoe UI", 10, "bold"),
            fg=self.ACCENT_GREEN,
            bg=self.BG_CARD,
            wraplength=240,
            justify="left",
            padx=10,
            pady=12,
        )
        self.mp_p2_status.pack(fill="x", pady=(4, 0))

    def _poll_remote_room_state(self) -> None:
        """Polls the host room server when this app joined a room via link (`MULTI_CLIENT`)."""
        self._client_poll_after_id = None
        if self.active_mode != "MULTI_CLIENT" or not self.remote_client_base_url or not self.remote_room_code:
            return
        url = f"{self.remote_client_base_url}/api/room/{self.remote_room_code}/state"
        try:
            with urllib.request.urlopen(url, timeout=1.2) as resp:
                st = json.loads(resp.read().decode("utf-8"))
            self.mp_p1_name_lbl.configure(text=st.get("p1_name", "Player 1"))
            self.mp_p2_name_lbl.configure(text=st.get("p2_name", "Player 2"))
            self.mp_p1_score_lbl.configure(text=f"{st.get('p1_score', 0)} PTS")
            self.mp_p2_score_lbl.configure(text=f"{st.get('p2_score', 0)} PTS")
            self.mp_round_lbl.configure(text=f"ROUND {st.get('current_round', 1)} / {st.get('total_rounds', 10)}")
            self.mp_reward_lbl.configure(text=f"REWARD: {st.get('potential_points', 100)} PTS")
            self.mp_timer_lbl.configure(text=f"⏱ {int(st.get('time_remaining', 60)):02d}s")
            rev_hints = st.get("revealed_hints", [])
            lines = ["🧭 Clues:"]
            for i in range(3):
                if i < len(rev_hints):
                    lines.append(f"  🔓 Clue {i + 1}: {rev_hints[i]}")
                else:
                    lines.append(f"  🔒 Clue {i + 1}: [Locked]")
            self.mp_hint_box.configure(text="\n".join(lines))

            img_key = f"{st.get('current_round', 1)}_{1 if st.get('revealed') else 0}"
            if img_key != getattr(self, "_last_remote_img_key", None):
                self._last_remote_img_key = img_key
                img_rel = st.get("image_url", f"/api/room/{self.remote_room_code}/image.png?round=1&revealed=0")
                with urllib.request.urlopen(f"{self.remote_client_base_url}{img_rel}", timeout=1.5) as img_resp:
                    pil_img = Image.open(io.BytesIO(img_resp.read())).convert("RGBA")
                    photo = ImageTk.PhotoImage(pil_img)
                    self.mp_image_lbl.configure(image=photo)
                    self.mp_image_lbl.image = photo
        except Exception:
            pass
        self._client_poll_after_id = self.root.after(700, self._poll_remote_room_state)

    def _load_multiplayer_round_view(self, revealed: bool = False) -> None:
        if self._get_current_dfa_state() == GameState.GAME_OVER.value:
            self._show_game_over_modal("MULTI")
            return

        info = self._extract_animal_fields(self.mp_controller.current_animal)

        photo = self.silhouette_gen.render_card_photo(
            info["image_path"],
            revealed=revealed,
            card_size=(290, 240),
            sprite_size=(225, 225),
        )
        self.mp_image_lbl.configure(image=photo)
        self.mp_image_lbl.image = photo

        self._refresh_mp_hud_metrics()
        self._refresh_mp_hints_ui()

        if not revealed:
            self.mp_p1_entry.configure(state="normal")
            self.mp_p2_entry.configure(state="normal")
            self.mp_p1_btn.configure(state="normal")
            self.mp_p2_btn.configure(state="normal")
            self.mp_p1_var.set("")
            self.mp_p2_var.set("")
            self.mp_p1_status.configure(text="🟢 Type animal name & press Enter!", fg=self.ACCENT_GREEN)
            self.mp_p2_status.configure(text="🟢 Type animal name & press Enter!", fg=self.ACCENT_GREEN)
            self.mp_banner_lbl.configure(
                text="⚡ First player to submit the right animal wins the round!",
                fg=self.TEXT_MAIN,
                bg=self.BG_CARD,
            )
            self.mp_p1_entry.focus_set()

    def _refresh_mp_hud_metrics(self) -> None:
        p1_sc = self.mp_controller.p1_score
        p2_sc = self.mp_controller.p2_score
        cur_r = self.mp_controller.current_round
        max_r = self.mp_controller.TOTAL_ROUNDS
        t_left = self.mp_controller.time_remaining
        pot = self.mp_controller.current_potential_points
        diff_label = {"EASY": "Easy", "MEDIUM": "Medium", "HARD": "Difficult"}.get(
            getattr(self.mp_controller, "difficulty", "MEDIUM"), "Medium"
        )

        self.mp_p1_score_lbl.configure(text=f"{p1_sc} PTS")
        self.mp_p2_score_lbl.configure(text=f"{p2_sc} PTS")
        self.mp_round_lbl.configure(text=f"ROUND {cur_r} / {max_r} ({diff_label})")
        self.mp_reward_lbl.configure(text=f"REWARD: {pot} PTS")
        self.mp_timer_lbl.configure(
            text=f"⏱ {t_left:02d}s",
            fg=self.ACCENT_RED if t_left <= 10 else self.ACCENT_CYAN,
        )

    def _refresh_mp_hints_ui(self) -> None:
        hints_used = self.mp_controller.hints_revealed
        bfs_hints = self.mp_controller.current_hints

        lines = ["🧭 Clues:"]
        for i in range(3):
            if i < hints_used and i < len(bfs_hints):
                lines.append(f"  🔓 Clue {i + 1}: {bfs_hints[i]}")
            else:
                lines.append(f"  🔒 Clue {i + 1}: [Locked]")
        self.mp_hint_box.configure(text="\n".join(lines))

        if hints_used >= 3 or self.mp_controller.round_locked:
            self.mp_hint_btn.configure(state="disabled", text="ALL CLUES REVEALED")
        else:
            self.mp_hint_btn.configure(state="normal", text=f"💡 REVEAL CLUE #{hints_used + 1}")

    def _pump_room_ui_events(self) -> None:
        """Drains pending remote HTTP room events on the Tkinter main thread."""
        if self.active_mode != "MULTI":
            return
        for cb in self.room_server.pop_ui_events():
            try:
                cb()
            except Exception:
                pass
        if self.active_mode == "MULTI":
            self.root.after(150, self._pump_room_ui_events)

    def _start_mp_timer(self) -> None:
        """Starts the non-blocking 60-second Multiplayer countdown using `self.root.after(1000, ...)`."""
        self._cancel_all_timers()
        self._timer_after_id = self.root.after(1000, self._tick_mp_timer)
        self.root.after(150, self._pump_room_ui_events)

    def _tick_mp_timer(self) -> None:
        self._timer_after_id = None
        if self.active_mode != "MULTI" or self._get_current_dfa_state() == GameState.GAME_OVER.value:
            return

        res = self.mp_controller.tick_timer(1)
        self._refresh_mp_hud_metrics()
        self._refresh_dfa_banner()

        if res.get("timed_out"):
            self._load_multiplayer_round_view(revealed=True)
            self.mp_p1_entry.configure(state="disabled")
            self.mp_p2_entry.configure(state="disabled")
            self.mp_p1_btn.configure(state="disabled")
            self.mp_p2_btn.configure(state="disabled")
            self.mp_banner_lbl.configure(
                text=f"⏰ {self._clean_ui_message(res.get('message', 'Time is up for this round!'))}",
                fg="#090d16",
                bg=self.ACCENT_AMBER,
            )

            def _after_mp_timeout() -> None:
                if res.get("match_over") or self._get_current_dfa_state() == GameState.GAME_OVER.value:
                    self._show_game_over_modal("MULTI")
                else:
                    next_anim = self.mp_controller.start_next_round()
                    if next_anim is None or self._get_current_dfa_state() == GameState.GAME_OVER.value:
                        self._show_game_over_modal("MULTI")
                    else:
                        self._load_multiplayer_round_view(revealed=False)
                        self._start_mp_timer()

            self._transition_after_id = self.root.after(1450, _after_mp_timeout)
            return

        self._timer_after_id = self.root.after(1000, self._tick_mp_timer)

    def _apply_mp_hint_to_ui(self) -> None:
        """Refreshes the Multiplayer hint box and HUD on the Tkinter main thread."""
        if not hasattr(self, "mp_hint_box") or not self.mp_hint_box.winfo_exists():
            return
        self._refresh_dfa_banner()
        self._refresh_mp_hud_metrics()
        self._refresh_mp_hints_ui()

    def _on_mp_request_hint(self) -> None:
        if self.active_mode == "MULTI_CLIENT" and self.remote_client_base_url and self.remote_room_code:
            try:
                req = urllib.request.Request(
                    f"{self.remote_client_base_url}/api/room/{self.remote_room_code}/hint",
                    data=b"{}",
                    method="POST",
                )
                urllib.request.urlopen(req, timeout=1.5)
            except Exception:
                pass
            return

        if self.active_mode != "MULTI" or self.mp_controller.round_locked:
            return
        self.mp_controller.reveal_shared_hint()
        self._apply_mp_hint_to_ui()

    def _on_mp_submit_guess(self, player_num: int) -> None:
        """Handles guess submission from Player 1 (`player_num=1`) or Player 2 (`player_num=2`)."""
        raw_guess = (self.mp_p1_var.get() if player_num == 1 else self.mp_p2_var.get()).strip()
        if not raw_guess:
            return

        if player_num == 1:
            self.mp_p1_var.set("")
        else:
            self.mp_p2_var.set("")

        if self.active_mode == "MULTI_CLIENT" and self.remote_client_base_url and self.remote_room_code:
            try:
                req = urllib.request.Request(
                    f"{self.remote_client_base_url}/api/room/{self.remote_room_code}/guess",
                    data=json.dumps({"player_num": player_num, "guess": raw_guess}).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=2.0) as resp:
                    res = json.loads(resp.read().decode("utf-8"))
                status_lbl = self.mp_p1_status if player_num == 1 else self.mp_p2_status
                status_lbl.configure(
                    text=self._clean_ui_message(res.get("message", "")),
                    fg=self.ACCENT_GREEN if res.get("correct") else self.ACCENT_RED,
                )
            except Exception:
                pass
            return

        if self.active_mode != "MULTI":
            return
        self._process_mp_guess_internal(player_num, raw_guess, from_remote=False)

    def _process_mp_guess_internal(
        self,
        player_num: int,
        raw_guess: str,
        from_remote: bool = False,
    ) -> Dict[str, Any]:
        """Evaluates a Multiplayer guess (from local keyboard OR remote room link) and updates the UI."""
        result = dict(self.mp_controller.submit_guess(player_num, raw_guess))
        result["message"] = self._clean_ui_message(result.get("message", ""))
        self.room_server.last_message = result["message"]
        self._apply_mp_guess_result_to_ui(player_num, result)
        return result

    def _apply_mp_guess_result_to_ui(self, player_num: int, result: Dict[str, Any]) -> None:
        """Applies a processed Multiplayer guess result to the Tkinter GUI widgets on the main thread."""
        if not hasattr(self, "mp_p1_status") or not self.mp_p1_status.winfo_exists():
            return

        self._refresh_dfa_banner()
        self._refresh_mp_hud_metrics()

        if result.get("locked_out"):
            status_lbl = self.mp_p1_status if player_num == 1 else self.mp_p2_status
            status_lbl.configure(
                text=f"🔒 {result.get('message', 'Round already claimed!')}",
                fg=self.ACCENT_RED,
            )
            return

        if result.get("correct"):
            self._cancel_all_timers()
            self.mp_p1_entry.configure(state="disabled")
            self.mp_p2_entry.configure(state="disabled")
            self.mp_p1_btn.configure(state="disabled")
            self.mp_p2_btn.configure(state="disabled")

            self._load_multiplayer_round_view(revealed=True)

            pts = result.get("points_awarded", 0)
            disp_name = result.get("display_name", "")

            if player_num == 1:
                self.mp_p1_status.configure(
                    text=f"🏆 WINNER! +{pts} pts! It's {disp_name}!",
                    fg=self.ACCENT_GREEN,
                )
                self.mp_p2_status.configure(
                    text=f"🔒 {self.mp_controller.p1_name} answered first!",
                    fg=self.ACCENT_RED,
                )
            else:
                self.mp_p2_status.configure(
                    text=f"🏆 WINNER! +{pts} pts! It's {disp_name}!",
                    fg=self.ACCENT_GREEN,
                )
                self.mp_p1_status.configure(
                    text=f"🔒 {self.mp_controller.p2_name} answered first!",
                    fg=self.ACCENT_RED,
                )

            self.mp_banner_lbl.configure(
                text=f"🏆 {result.get('message', 'Round won!')}",
                fg="#090d16",
                bg=self.ACCENT_GREEN,
            )

            def _advance_mp() -> None:
                if result.get("match_over") or self._get_current_dfa_state() == GameState.GAME_OVER.value:
                    self._show_game_over_modal("MULTI")
                else:
                    next_anim = self.mp_controller.start_next_round()
                    if next_anim is None or self._get_current_dfa_state() == GameState.GAME_OVER.value:
                        self._show_game_over_modal("MULTI")
                    else:
                        self._load_multiplayer_round_view(revealed=False)
                        self._start_mp_timer()

            self._transition_after_id = self.root.after(1450, _advance_mp)
        else:
            status_lbl = self.mp_p1_status if player_num == 1 else self.mp_p2_status
            status_lbl.configure(
                text=f"❌ {result.get('message', 'Incorrect guess! Keep trying!')}",
                fg=self.ACCENT_RED,
            )

    # ==================================================================
    # VIEW 4: GAME OVER SUMMARY (`GAME_OVER`)
    # ==================================================================
    def _show_game_over_modal(self, mode: str) -> None:
        """Renders the `GAME_OVER` screen with final scores and player ratings."""
        self._clear_container()
        self._refresh_dfa_banner()

        card = tk.Frame(
            self.main_container,
            bg=self.BG_PANEL,
            padx=32,
            pady=28,
            highlightthickness=2,
            highlightbackground=self.ACCENT_AMBER,
        )
        card.pack(expand=True)

        tk.Label(
            card,
            text="🏁 GAME OVER",
            font=("Segoe UI", 22, "bold"),
            fg=self.ACCENT_AMBER,
            bg=self.BG_PANEL,
        ).pack(pady=(0, 12))

        if mode == "SINGLE":
            p_name = self.sp_controller.player_name
            final_score = self.sp_controller.score
            lives_rem = self.sp_controller.lives
            solved = self.sp_controller.animals_solved
            summary_txt = (
                f"Single Player Run Complete!\n\n"
                f"Player: {p_name}\n"
                f"Final Score: {final_score} pts   •   Animals Guessed: {solved}\n"
                f"Lives Remaining: {lives_rem} / 3\n\n"
                f"✔ High Score & Player Rating Saved!"
            )
        else:
            summary = self.mp_controller.get_match_summary()
            p1_n = summary["p1_name"]
            p2_n = summary["p2_name"]
            s1 = summary["p1_score"]
            s2 = summary["p2_score"]
            if s1 > s2:
                verdict = f"🏆 {p1_n} WINS THE MATCH!"
            elif s2 > s1:
                verdict = f"🏆 {p2_n} WINS THE MATCH!"
            else:
                verdict = "🤝 IT'S A DRAW!"
            summary_txt = (
                f"{verdict}\n\n"
                f"{p1_n}: {s1} pts ({summary['p1_rounds_won']} rounds won, Rating: {summary['p1_mmr']})\n"
                f"{p2_n}: {s2} pts ({summary['p2_rounds_won']} rounds won, Rating: {summary['p2_mmr']})\n\n"
                f"✔ Match Scores & Player Ratings Updated!"
            )

        tk.Label(
            card,
            text=summary_txt,
            font=("Segoe UI", 12),
            fg=self.TEXT_MAIN,
            bg=self.BG_CARD,
            padx=24,
            pady=18,
            justify="center",
        ).pack(fill="x", pady=12)

        btn_bar = tk.Frame(card, bg=self.BG_PANEL)
        btn_bar.pack(pady=(12, 0))

        tk.Button(
            btn_bar,
            text="🔄 PLAY AGAIN",
            command=self.start_single_player if mode == "SINGLE" else self.start_multiplayer,
            font=("Segoe UI", 11, "bold"),
            bg=self.ACCENT_GREEN,
            fg="#090d16",
            relief="flat",
            padx=18,
            pady=8,
            cursor="hand2",
        ).pack(side="left", padx=8)

        tk.Button(
            btn_bar,
            text="🏠 MAIN MENU",
            command=self.show_main_menu,
            font=("Segoe UI", 11, "bold"),
            bg=self.ACCENT_CYAN,
            fg="#090d16",
            relief="flat",
            padx=18,
            pady=8,
            cursor="hand2",
        ).pack(side="left", padx=8)

    def run(self) -> None:
        """Starts the Tkinter main event loop."""
        try:
            self.root.mainloop()
        finally:
            self.room_server.stop_room()


# Provide SSOT alias `WhosThatAnimalApp`
WhosThatAnimalApp = WhosThatAnimalGUI


def run_self_test() -> int:
    """Verifies realistic animal asset generation, runtime silhouette conversion, and Multiplayer Room Link HTTP flow."""
    print("[Self-Test] Initializing SilhouetteGenerator (2x supersampled realistic sprites)...")
    gen = SilhouetteGenerator(force_regenerate=True)
    paths = gen.ensure_all_assets(force_regenerate=True)
    assert len(paths) >= 16, f"Expected >=16 animal PNGs, got {len(paths)}"

    sample_sil = gen.create_silhouette(paths[0], size=(120, 120))
    px = sample_sil.load()
    assert px is not None
    non_transparent = 0
    for y in range(sample_sil.height):
        for x in range(sample_sil.width):
            r, g, b, a = px[x, y]
            if a > 0:
                assert (r, g, b) == (0, 0, 0), f"Non-black silhouette pixel {(r, g, b, a)}"
                non_transparent += 1
    assert non_transparent > 500, "Silhouette has too few opaque pixels"
    print(f"[Self-Test] Verified {len(paths)} realistic animal PNGs & runtime RGBA->#000000 conversion.")

    root = tk.Tk()
    root.withdraw()
    app = WhosThatAnimalGUI(root=root)

    banned_terms = ("DFA", "Levenshtein", "Max-Heap", "AVL Tree", "DAG BFS", "Prefix Trie", "Sift-Up", "RGBA->#000000", "Race Condition")

    def _assert_no_jargon_in_widgets(widget: tk.Misc) -> None:
        try:
            txt = str(widget.cget("text"))
            for term in banned_terms:
                assert term.lower() not in txt.lower(), f"Found technical term '{term}' in widget text: {txt!r}"
        except Exception:
            pass
        for child in widget.winfo_children():
            _assert_no_jargon_in_widgets(child)

    assert app.root.title() == "Who's That Animal?"
    _assert_no_jargon_in_widgets(app.root)
    app.start_single_player()
    _assert_no_jargon_in_widgets(app.root)

    share_link = app.create_multiplayer_room_and_start()
    _assert_no_jargon_in_widgets(app.root)
    print(f"[Self-Test] Created Multiplayer Room Link: {share_link}")
    local_link = app.room_server.localhost_url
    code = app.room_server.room_code

    # Test GET /room/<code> HTML page
    with urllib.request.urlopen(local_link, timeout=2.0) as resp:
        html = resp.read().decode("utf-8")
        assert code in html and "JOIN ROOM" in html
        for banned in banned_terms:
            assert banned.lower() not in html.lower(), f"Found technical jargon '{banned}' in web UI!"

    # Test GET /api/room/<code>/image.png
    with urllib.request.urlopen(f"http://127.0.0.1:{app.room_server.port}/api/room/{code}/image.png?round=1&revealed=0", timeout=2.0) as resp:
        png_raw = resp.read()
        assert png_raw.startswith(b"\x89PNG"), "Invalid PNG response from /image.png"

    # Test POST /api/room/<code>/join
    join_req = urllib.request.Request(
        f"http://127.0.0.1:{app.room_server.port}/api/room/{code}/join",
        data=json.dumps({"player_name": "Friend_Browser"}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(join_req, timeout=2.0) as resp:
        join_data = json.loads(resp.read().decode("utf-8"))
        assert join_data.get("joined") is True

    # Test POST /api/room/<code>/hint
    hint_req = urllib.request.Request(
        f"http://127.0.0.1:{app.room_server.port}/api/room/{code}/hint",
        data=b"{}",
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(hint_req, timeout=2.0) as resp:
        hint_data = json.loads(resp.read().decode("utf-8"))
        assert hint_data.get("ok") is True
        assert hint_data["state"]["hints_revealed"] == 1

    # Test POST /api/room/<code>/guess with current animal
    target_name = app.mp_controller.current_animal.name if app.mp_controller.current_animal else "elephant"
    guess_req = urllib.request.Request(
        f"http://127.0.0.1:{app.room_server.port}/api/room/{code}/guess",
        data=json.dumps({"player_num": 2, "guess": target_name}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(guess_req, timeout=2.0) as resp:
        guess_data = json.loads(resp.read().decode("utf-8"))
        assert guess_data.get("correct") is True
        assert app.mp_controller.p2_score == 75  # 1 hint revealed -> 75 pts
        for banned in banned_terms:
            assert banned.lower() not in guess_data.get("message", "").lower()

    app.room_server.stop_room()
    root.destroy()
    print("[Self-Test] All Realistic Asset, Clean UI & Multiplayer Room Link checks PASSED!")
    return 0


def main() -> None:
    if "--self-test" in sys.argv:
        sys.exit(run_self_test())
    app = WhosThatAnimalGUI()
    app.run()


if __name__ == "__main__":
    main()
