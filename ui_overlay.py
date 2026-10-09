"""
UI and HUD overlay module for the Virtual Whiteboard.
Renders glassmorphic toolbars, designer color palette, interactive buttons with dwell/pinch selection,
status cards, cursors, toast notifications, and Picture-in-Picture (PiP) feed.
"""

import math
import time
import cv2
import numpy as np

import config
from config import CanvasMode, ToolType

try:
    import winsound
    HAS_WINSOUND = True
except ImportError:
    HAS_WINSOUND = False


class Button:
    """Represents an interactive UI button with bounding box and click state."""

    def __init__(self, btn_id, label, x, y, w, h, group="action", data=None, icon=None, color_bgr=None):
        self.btn_id = btn_id
        self.label = label
        self.x = x
        self.y = y
        self.w = w
        self.h = h
        self.group = group      # 'tool', 'color', 'size', 'action'
        self.data = data
        self.icon = icon or label[:2]
        self.color_bgr = color_bgr

    @property
    def rect(self):
        return (self.x, self.y, self.x + self.w, self.y + self.h)

    def contains(self, px, py):
        return self.x <= px <= self.x + self.w and self.y <= py <= self.y + self.h


class UIOverlay:
    """Manages UI layout, rendering, button hit-testing, and toast banners."""

    def __init__(self, width=config.DEFAULT_WIDTH, height=config.DEFAULT_HEIGHT):
        self.width = width
        self.height = height

        # Button layout
        self.buttons = []
        self._build_toolbar()

        # Hover & Dwell selection state
        self.hovered_btn_id = None
        self.hover_start_time = None
        self.dwell_progress = 0.0

        # Toast notification system
        self.toast_message = None
        self.toast_start_time = 0
        self.toast_duration = 2.5

    def _build_toolbar(self):
        """Constructs responsive toolbar buttons arranged across the top."""
        self.buttons.clear()

        y_top = 8
        h_btn = 46

        # Section 1: Drawing & Shape & Presenter Tools
        x = 10
        tools = [
            ("tool_pen", "Pen", ToolType.PEN, "PEN"),
            ("tool_highlighter", "High", ToolType.HIGHLIGHTER, "HL"),
            ("tool_eraser", "Erase", ToolType.ERASER, "ER"),
            ("tool_line", "Line", ToolType.LINE, "LN"),
            ("tool_rect", "Rect", ToolType.RECTANGLE, "REC"),
            ("tool_circle", "Circle", ToolType.CIRCLE, "CIR"),
            ("tool_arrow", "Arrow", ToolType.ARROW, "ARR"),
            ("tool_laser", "Laser", ToolType.LASER, "LSR"),
            ("tool_spot", "Spot", ToolType.SPOTLIGHT, "SPT"),
        ]
        for btn_id, label, tool_enum, icon in tools:
            w_btn = 48
            self.buttons.append(Button(btn_id, label, x, y_top, w_btn, h_btn, group="tool", data=tool_enum, icon=icon))
            x += w_btn + 4

        # Magic Alive & Smart Snap Action Buttons
        self.buttons.append(Button("act_alive", "Alive", x, y_top, 52, h_btn, group="action", data="ALIVE", icon="ALV"))
        x += 52 + 4
        self.buttons.append(Button("act_snap", "Snap", x, y_top, 46, h_btn, group="action", data="TOGGLE_SNAP", icon="SNP"))
        x += 46 + 8

        # Separator
        x += 6

        # Section 2: Designer Color Palette (Swatches)
        color_items = list(config.COLORS.items())
        for name, bgr in color_items:
            w_btn = 34
            self.buttons.append(
                Button(f"color_{name}", name, x, y_top + 4, w_btn, 36, group="color", data=name, color_bgr=bgr)
            )
            x += w_btn + 4

        # Separator
        x += 8

        # Section 3: Brush Sizes
        sizes = [
            ("size_fine", "S", "Fine", 4),
            ("size_med", "M", "Medium", 8),
            ("size_bold", "L", "Bold", 15),
            ("size_thick", "XL", "Marker", 26),
        ]
        for btn_id, label, size_name, val in sizes:
            w_btn = 34
            self.buttons.append(
                Button(btn_id, label, x, y_top + 4, w_btn, 36, group="size", data=size_name, icon=label)
            )
            x += w_btn + 4

        # Separator
        x += 8

        # Section 4: Actions (Undo, Redo, Clear, Save, PDF, Theme)
        actions = [
            ("act_undo", "Undo", "UNDO", "U"),
            ("act_redo", "Redo", "REDO", "R"),
            ("act_clear", "Clear", "CLEAR", "X"),
            ("act_save", "PNG", "SAVE_PNG", "PNG"),
            ("act_pdf", "PDF", "SAVE_PDF", "PDF"),
            ("act_mode", "Theme", "CYCLE_MODE", "BG"),
        ]
        for btn_id, label, act_code, icon in actions:
            w_btn = 44 if act_code in ("UNDO", "REDO", "CLEAR") else 50
            self.buttons.append(
                Button(btn_id, label, x, y_top, w_btn, h_btn, group="action", data=act_code, icon=icon)
            )
            x += w_btn + 4

    def show_toast(self, message, duration=2.5):
        """Displays temporary popup toast notification."""
        self.toast_message = message
        self.toast_start_time = time.time()
        self.toast_duration = duration

    def play_sound(self, sound_type="click"):
        """Plays subtle audio feedback for interactions."""
        if not HAS_WINSOUND:
            return
        try:
            if sound_type == "click":
                winsound.Beep(950, 40)
            elif sound_type == "success":
                winsound.Beep(1200, 60)
            elif sound_type == "clear":
                winsound.Beep(650, 75)
            elif sound_type == "magic":
                winsound.Beep(1050, 45)
                winsound.Beep(1400, 50)
                winsound.Beep(1760, 65)
            elif sound_type == "snap":
                winsound.Beep(1600, 45)
        except Exception:
            pass

    def check_interaction(self, cursor_pt, is_pinching, canvas_engine):
        """
        Tests if cursor is over any button. Handles dwell time progress and pinch click.
        Returns: action_triggered: str or None
        """
        if cursor_pt is None:
            self.hovered_btn_id = None
            self.hover_start_time = None
            self.dwell_progress = 0.0
            return None

        cx, cy = cursor_pt
        curr_time = time.time()
        hovered_btn = None

        for btn in self.buttons:
            if btn.contains(cx, cy):
                hovered_btn = btn
                break

        if hovered_btn is None:
            self.hovered_btn_id = None
            self.hover_start_time = None
            self.dwell_progress = 0.0
            return None

        # Button is hovered
        if self.hovered_btn_id != hovered_btn.btn_id:
            self.hovered_btn_id = hovered_btn.btn_id
            self.hover_start_time = curr_time
            self.dwell_progress = 0.0
            if not is_pinching:
                return None

        # Calculate dwell progress
        elapsed = curr_time - self.hover_start_time
        self.dwell_progress = min(1.0, elapsed / config.SELECTION_DWELL_TIME)

        # Trigger if dwell completes or pinch occurs
        should_trigger = self.dwell_progress >= 1.0 or is_pinching

        if should_trigger:
            self.hover_start_time = curr_time + 0.45
            self.dwell_progress = 0.0
            return self._execute_button(hovered_btn, canvas_engine)

        return None

    def _execute_button(self, btn, canvas_engine):
        """Applies button action to canvas engine."""
        self.play_sound("click")

        if btn.group == "tool":
            canvas_engine.set_tool(btn.data)
            self.show_toast(f"Tool: {btn.data.value}")
            return f"TOOL_{btn.data.value}"

        elif btn.group == "color":
            canvas_engine.set_color(btn.data)
            self.show_toast(f"Color: {btn.data}")
            return f"COLOR_{btn.data}"

        elif btn.group == "size":
            canvas_engine.set_brush_size(btn.data)
            self.show_toast(f"Brush Size: {btn.data}")
            return f"SIZE_{btn.data}"

        elif btn.group == "action":
            action = btn.data
            if action == "ALIVE":
                ok, msg = canvas_engine.animate_last_drawing()
                if ok:
                    self.play_sound("magic")
                self.show_toast(msg)
                return "ALIVE"

            elif action == "TOGGLE_SNAP":
                canvas_engine.auto_shape_snap = not canvas_engine.auto_shape_snap
                state_str = "ON" if canvas_engine.auto_shape_snap else "OFF"
                self.show_toast(f"Shape Snapping: {state_str}")
                return "TOGGLE_SNAP"

            elif action == "UNDO":
                success = canvas_engine.undo()
                self.show_toast("Undo" if success else "Nothing to undo")
                return "UNDO"

            elif action == "REDO":
                success = canvas_engine.redo()
                self.show_toast("Redo" if success else "Nothing to redo")
                return "REDO"

            elif action == "CLEAR":
                canvas_engine.clear()
                canvas_engine.clear_alive_doodles()
                self.play_sound("clear")
                self.show_toast("Canvas Cleared")
                return "CLEAR"

            elif action == "CYCLE_MODE":
                modes = [CanvasMode.CAMERA_OVERLAY, CanvasMode.WHITEBOARD, CanvasMode.BLACKBOARD]
                idx = (modes.index(canvas_engine.canvas_mode) + 1) % len(modes)
                canvas_engine.canvas_mode = modes[idx]
                self.show_toast(f"Mode: {canvas_engine.canvas_mode.value}")
                return "CYCLE_MODE"

            elif action in ("SAVE_PNG", "SAVE_PDF"):
                return action

        return None

    def render(self, frame_bgr, canvas_engine, gesture_info, fps=0):
        """Renders the complete UI HUD on top of the composited frame."""
        h, w = frame_bgr.shape[:2]

        # 1. Top Glassmorphic Toolbar Panel
        self._render_toolbar_background(frame_bgr)

        # 2. Render Buttons
        for btn in self.buttons:
            self._render_button(frame_bgr, btn, canvas_engine)

        # 3. Toast Banner
        self._render_toast(frame_bgr)

        # 4. Status Card (Bottom-Left)
        self._render_status_card(frame_bgr, canvas_engine, gesture_info, fps)

        # 5. Cursor Indicator
        self._render_cursor(frame_bgr, canvas_engine, gesture_info)

        return frame_bgr

    def _render_toolbar_background(self, frame):
        """Draws frosted glass background for the top toolbar."""
        h_bar = 66
        w_bar = self.width

        sub_img = frame[0:h_bar, 0:w_bar]
        glass_rect = np.full_like(sub_img, (22, 24, 28))
        cv2.addWeighted(glass_rect, 0.88, sub_img, 0.12, 0, sub_img)
        cv2.line(frame, (0, h_bar), (w_bar, h_bar), (60, 65, 75), 1, cv2.LINE_AA)

    def _render_button(self, frame, btn, canvas_engine):
        """Renders individual toolbar button with states (normal, hovered, active)."""
        x1, y1, x2, y2 = btn.rect
        is_hovered = (btn.btn_id == self.hovered_btn_id)

        is_active = False
        if btn.group == "tool" and canvas_engine.active_tool == btn.data:
            is_active = True
        elif btn.group == "color" and canvas_engine.active_color_name == btn.data:
            is_active = True
        elif btn.group == "size" and canvas_engine.brush_size == config.BRUSH_SIZES.get(btn.data, -1):
            is_active = True
        elif btn.btn_id == "act_snap" and canvas_engine.auto_shape_snap:
            is_active = True

        # Render Color Swatches
        if btn.group == "color":
            cx = (x1 + x2) // 2
            cy = (y1 + y2) // 2
            radius = 13

            if is_active:
                cv2.circle(frame, (cx, cy), radius + 4, (255, 255, 255), 2, cv2.LINE_AA)
            elif is_hovered:
                cv2.circle(frame, (cx, cy), radius + 3, (170, 170, 175), 1, cv2.LINE_AA)

            cv2.circle(frame, (cx, cy), radius, btn.color_bgr, -1, cv2.LINE_AA)
            cv2.circle(frame, (cx, cy), radius, (45, 45, 50), 1, cv2.LINE_AA)

            if is_hovered and self.dwell_progress > 0:
                self._draw_progress_arc(frame, (cx, cy), radius + 5, self.dwell_progress)
            return

        # Render Standard Buttons
        bg_color = (36, 38, 46)
        border_color = (65, 70, 82)
        text_color = (225, 225, 230)

        if btn.btn_id == "act_alive":
            bg_color = (60, 35, 75)
            border_color = (180, 80, 220)
            text_color = (240, 200, 255)

        if is_active:
            bg_color = (200, 85, 30)      # Rich Indigo/Cyan Accent (BGR)
            border_color = (255, 160, 70)
            text_color = (255, 255, 255)
        elif is_hovered:
            bg_color = (55, 60, 74)
            border_color = (160, 165, 180)

        cv2.rectangle(frame, (x1, y1), (x2, y2), bg_color, -1)
        cv2.rectangle(frame, (x1, y1), (x2, y2), border_color, 1, cv2.LINE_AA)

        # Label
        font = cv2.FONT_HERSHEY_SIMPLEX
        scale = 0.40
        thickness = 1
        text = btn.icon or btn.label
        (tw, th), _ = cv2.getTextSize(text, font, scale, thickness)
        tx = x1 + (btn.w - tw) // 2
        ty = y1 + (btn.h + th) // 2 - 1
        cv2.putText(frame, text, (tx, ty), font, scale, text_color, thickness, cv2.LINE_AA)

        # Dwell progress bar
        if is_hovered and self.dwell_progress > 0:
            pw = int(btn.w * self.dwell_progress)
            cv2.rectangle(frame, (x1, y2 - 3), (x1 + pw, y2), (0, 230, 255), -1)

    def _draw_progress_arc(self, frame, center, radius, progress):
        """Draws circular progress arc for dwell countdown."""
        angle = int(360 * progress)
        cv2.ellipse(frame, center, (radius, radius), -90, 0, angle, (0, 230, 255), 2, cv2.LINE_AA)

    def _render_toast(self, frame):
        """Renders animated toast banner if active."""
        if not self.toast_message:
            return

        elapsed = time.time() - self.toast_start_time
        if elapsed > self.toast_duration:
            self.toast_message = None
            return

        alpha = 1.0
        if elapsed > self.toast_duration - 0.5:
            alpha = (self.toast_duration - elapsed) / 0.5

        font = cv2.FONT_HERSHEY_SIMPLEX
        scale = 0.50
        thickness = 1
        (tw, th), _ = cv2.getTextSize(self.toast_message, font, scale, thickness)

        pw = tw + 36
        ph = th + 22
        px = (self.width - pw) // 2
        py = 78

        overlay = frame.copy()
        cv2.rectangle(overlay, (px, py), (px + pw, py + ph), (24, 26, 32), -1)
        cv2.rectangle(overlay, (px, py), (px + pw, py + ph), (0, 220, 255), 1, cv2.LINE_AA)
        cv2.putText(overlay, self.toast_message, (px + 18, py + ph - 7), font, scale, (255, 255, 255), thickness, cv2.LINE_AA)

        cv2.addWeighted(overlay, alpha * 0.92, frame, 1.0 - alpha * 0.92, 0, frame)

    def _render_status_card(self, frame, canvas_engine, gesture_info, fps):
        """Renders information status card in bottom-left corner."""
        card_w = 275
        card_h = 82
        card_x = 14
        card_y = self.height - card_h - 14

        sub_img = frame[card_y:card_y + card_h, card_x:card_x + card_w]
        glass_rect = np.full_like(sub_img, (20, 22, 28))
        cv2.addWeighted(glass_rect, 0.88, sub_img, 0.12, 0, sub_img)
        cv2.rectangle(frame, (card_x, card_y), (card_x + card_w, card_y + card_h), (55, 60, 72), 1, cv2.LINE_AA)

        gesture = gesture_info.get("gesture", "NONE")
        gesture_colors = {
            "DRAW": (104, 138, 45),    # Sage Green
            "SELECT": (253, 91, 59),   # Indigo
            "ERASER": (68, 93, 224),   # Terracotta
            "PINCH": (0, 220, 255),    # Gold
            "HOVER": (180, 160, 90),
            "FIST": (150, 150, 155),
            "NONE": (120, 120, 125),
        }
        badge_color = gesture_colors.get(gesture, (120, 120, 125))

        font = cv2.FONT_HERSHEY_SIMPLEX
        cv2.putText(frame, f"MODE: {gesture}", (card_x + 12, card_y + 22), font, 0.48, badge_color, 2, cv2.LINE_AA)

        # Ergonomics / Snap status
        pinch_mode = gesture_info.get("pinch_to_draw", False)
        ergo_str = "Pinch-Draw" if pinch_mode else "Index"
        snap_str = "Snap: ON" if canvas_engine.auto_shape_snap else "Snap: OFF"
        cv2.putText(frame, f"{ergo_str} | {snap_str}", (card_x + 12, card_y + 42), font, 0.36, (180, 185, 195), 1, cv2.LINE_AA)

        # Living Doodles / Tool
        num_alive = len(canvas_engine.alive_doodles)
        alive_str = f" | {num_alive} Alive ✨" if num_alive > 0 else ""
        tool_str = f"Tool: {canvas_engine.active_tool.value}{alive_str}"
        cv2.putText(frame, tool_str, (card_x + 12, card_y + 60), font, 0.36, (215, 215, 220), 1, cv2.LINE_AA)

        # FPS
        fps_str = f"FPS: {int(fps)} | {canvas_engine.canvas_mode.value.split()[-1]}"
        cv2.putText(frame, fps_str, (card_x + 12, card_y + 76), font, 0.33, (135, 140, 150), 1, cv2.LINE_AA)

    def _render_cursor(self, frame, canvas_engine, gesture_info):
        """Draws visual feedback cursor for fingertip."""
        cursor_pt = gesture_info.get("index_tip")
        if cursor_pt is None:
            return

        cx, cy = cursor_pt
        gesture = gesture_info.get("gesture", "NONE")

        # 1. Laser Pointer Cursor
        if canvas_engine.active_tool == ToolType.LASER:
            cv2.circle(frame, (cx, cy), 8, (60, 80, 255), 2, cv2.LINE_AA)
            cv2.circle(frame, (cx, cy), 4, (255, 255, 255), -1, cv2.LINE_AA)
            return

        # 2. Spotlight Cursor
        if canvas_engine.active_tool == ToolType.SPOTLIGHT:
            cv2.circle(frame, (cx, cy), 12, (0, 230, 255), 2, cv2.LINE_AA)
            cv2.line(frame, (cx - 16, cy), (cx + 16, cy), (0, 230, 255), 1, cv2.LINE_AA)
            cv2.line(frame, (cx, cy - 16), (cx, cy + 16), (0, 230, 255), 1, cv2.LINE_AA)
            return

        # 3. Eraser Mode Cursor
        if gesture == "ERASER" or canvas_engine.active_tool == ToolType.ERASER:
            radius = canvas_engine.eraser_radius * 2 if gesture == "ERASER" else canvas_engine.eraser_radius
            cv2.circle(frame, (cx, cy), radius, (68, 93, 224), 2, cv2.LINE_AA)
            cv2.circle(frame, (cx, cy), 3, (255, 255, 255), -1, cv2.LINE_AA)

        # 4. Draw Mode Cursor
        elif gesture == "DRAW":
            radius = max(3, canvas_engine.brush_size)
            cv2.circle(frame, (cx, cy), radius, canvas_engine.active_color_bgr, -1, cv2.LINE_AA)
            cv2.circle(frame, (cx, cy), radius + 1, (255, 255, 255), 1, cv2.LINE_AA)

        # 5. Selection / Hover Cursor
        elif gesture in ("SELECT", "HOVER"):
            cv2.circle(frame, (cx, cy), 7, (253, 91, 59), 2, cv2.LINE_AA)
            cv2.line(frame, (cx - 10, cy), (cx + 10, cy), (253, 91, 59), 1, cv2.LINE_AA)
            cv2.line(frame, (cx, cy - 10), (cx, cy + 10), (253, 91, 59), 1, cv2.LINE_AA)

        # 6. Pinch Cursor
        elif gesture == "PINCH":
            cv2.circle(frame, (cx, cy), 9, (0, 220, 255), 2, cv2.LINE_AA)
            cv2.circle(frame, (cx, cy), 4, (0, 220, 255), -1, cv2.LINE_AA)

    def render_pip(self, display_frame, camera_frame_bgr, tracker, landmarks):
        """Renders Picture-in-Picture webcam feed in the bottom-right corner."""
        pip_w = 230
        pip_h = 130
        margin = 14
        h, w = display_frame.shape[:2]

        x1 = w - pip_w - margin
        y1 = h - pip_h - margin
        x2 = x1 + pip_w
        y2 = y1 + pip_h

        pip_small = cv2.resize(camera_frame_bgr, (pip_w, pip_h))

        if landmarks:
            scale_x = pip_w / w
            scale_y = pip_h / h
            pip_lms = [(int(lm[0] * scale_x), int(lm[1] * scale_y), lm[2]) for lm in landmarks]
            pip_small = tracker.draw_hand_skeleton(pip_small, pip_lms)

        display_frame[y1:y2, x1:x2] = pip_small
        cv2.rectangle(display_frame, (x1, y1), (x2, y2), (65, 70, 82), 2, cv2.LINE_AA)
        cv2.putText(display_frame, "Hand Camera", (x1 + 8, y1 + 18), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (0, 220, 255), 1, cv2.LINE_AA)
