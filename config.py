"""
Configuration settings for the Virtual Whiteboard application.
Contains color palettes, dimensions, thresholds, and operational modes.
"""

import os
from enum import Enum


class CanvasMode(Enum):
    """Background display modes."""
    CAMERA_OVERLAY = "AR Camera Overlay"
    WHITEBOARD = "Pure Whiteboard"
    BLACKBOARD = "Dark Blackboard"


class ToolType(Enum):
    """Available drawing tools."""
    PEN = "Pen"
    HIGHLIGHTER = "Highlighter"
    ERASER = "Eraser"
    LINE = "Line"
    RECTANGLE = "Rectangle"
    CIRCLE = "Circle"
    ARROW = "Arrow"
    LASER = "Laser"
    SPOTLIGHT = "Spotlight"
    ALIVE = "Alive"


# Window & Camera Settings
DEFAULT_WIDTH = 1280
DEFAULT_HEIGHT = 720
FPS_TARGET = 60

# Model Path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(BASE_DIR, "models", "hand_landmarker.task")
NOTES_DIR = os.path.join(BASE_DIR, "saved_notes")

# Designer-Grade Curated Color Palette (BGR format for OpenCV)
# Inspired by Procreate, Figma, and Apple Notes (Warm, refined, organic)
COLORS = {
    "Royal Indigo": (253, 91, 59),     # #3B5BFD (Ultramarine Blue)
    "Obsidian Black": (36, 31, 30),    # #1E1F24 (Midnight Charcoal)
    "Sage Forest": (104, 138, 45),     # #2D8A68 (Earthy Botanical Green)
    "Warm Terracotta": (68, 93, 224),  # #E05D44 (Tuscan Earth Coral)
    "Tuscan Gold": (0, 169, 242),      # #F2A900 (Warm Honey Amber)
    "Nordic Slate": (139, 116, 100),   # #64748B (Refined Muted Slate)
    "Berry Plum": (234, 51, 147),      # #9333EA (Rich Velvet Violet)
    "Chalk White": (252, 250, 248),    # #F8FAFC (Soft Natural Off-White)
}

DEFAULT_COLOR_NAME = "Royal Indigo"

# Brush Sizes (pixels)
BRUSH_SIZES = {
    "Fine": 4,
    "Medium": 8,
    "Bold": 15,
    "Marker": 26,
}
DEFAULT_BRUSH_SIZE_NAME = "Medium"

# Eraser Sizes (pixels radius)
ERASER_SIZES = {
    "Normal": 35,
    "Large": 70,
}
DEFAULT_ERASER_SIZE_NAME = "Normal"

# Gesture & Interaction Thresholds
SELECTION_DWELL_TIME = 0.50  # Seconds of hover required to activate button
PINCH_THRESHOLD = 40         # Pixel distance between index tip and thumb tip for pinch click
SMOOTHING_ALPHA_DRAW = 0.35  # Smoothing factor when drawing (lower = smoother, higher = more responsive)
SMOOTHING_ALPHA_HOVER = 0.60 # Smoothing factor when hovering/navigating
MAX_HISTORY_STATES = 25      # Maximum undo/redo history snapshots

# Ergonomics & Smart Features Configuration
PINCH_TO_DRAW_DEFAULT = False   # If True, draws by pinching thumb + index tip (Vision Pro style)
Z_DEPTH_TOUCH_ENABLED = True    # If True, pushes forward in Z-axis to touch digital glass
Z_TOUCH_DELTA_THRESHOLD = -0.04 # Forward depth threshold relative to wrist/MCP
AUTO_SHAPE_SNAP_DEFAULT = True  # Automatically snaps hand-drawn loops/boxes to clean geometry
LASER_DECAY_SECONDS = 1.3       # Ephemeral laser pointer trail duration
SPOTLIGHT_RADIUS = 145          # Radius of the presenter spotlight aperture

# UI Theme Colors (BGR)
UI_THEME = {
    "bg_glass": (22, 24, 28),
    "bg_glass_alpha": 0.88,
    "border_glow": (160, 140, 90),
    "text_primary": (250, 250, 252),
    "text_secondary": (165, 170, 180),
    "accent_blue": (253, 91, 59),
    "accent_green": (104, 138, 45),
    "accent_red": (68, 93, 224),
    "button_hover": (55, 60, 72),
    "button_active": (253, 91, 59),
    "card_bg": (28, 30, 36),
}
