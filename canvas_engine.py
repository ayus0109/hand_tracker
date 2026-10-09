"""
Canvas and drawing engine for the Virtual Whiteboard.
Handles freehand pen strokes, highlighters, erasers, geometric shapes,
live previews, smart shape snapping, presenter tools (Laser, Spotlight),
animated living doodles ("Bring to Life"), and a multi-level undo/redo stack.
"""

import math
import time
import cv2
import numpy as np

import config
from config import CanvasMode, ToolType


class AliveDoodle:
    """
    An animated doodle entity that swims and floats like a living fish or creature.
    Supports undulating sine-wave body deformation, autonomous wandering, bubble emission,
    and responsive hand interactions (attracted to pinch/pointing, frightened by eraser).
    """

    def __init__(self, sprite_rgba, x, y):
        self.orig_sprite = sprite_rgba.copy()  # (H, W, 4)
        self.h, self.w = sprite_rgba.shape[:2]
        self.x = float(x)
        self.y = float(y)

        # Initial swimming velocity
        angle = np.random.uniform(-math.pi / 4, math.pi / 4)
        if np.random.rand() > 0.5:
            angle += math.pi
        speed = np.random.uniform(2.8, 4.4)
        self.vx = math.cos(angle) * speed
        self.vy = math.sin(angle) * speed * 0.4

        self.phase = np.random.uniform(0.0, 6.28)
        self.wiggle_speed = 0.22
        self.wiggle_amp = min(12.0, max(3.0, self.h * 0.12))
        self.bubbles = []  # [[x, y, radius, alpha]]

    def update(self, bounds_w, bounds_h, hand_pt=None, gesture="NONE"):
        self.phase += self.wiggle_speed

        # Hand interaction
        if hand_pt is not None:
            hx, hy = hand_pt
            dist = math.hypot(hx - self.x, hy - self.y)
            if gesture in ("SELECT", "PINCH", "DRAW") and dist < 420:
                # Attracted to finger (feed the fish!)
                pull = 0.16 if gesture == "PINCH" else 0.08
                angle_to = math.atan2(hy - self.y, hx - self.x)
                self.vx += math.cos(angle_to) * pull
                self.vy += math.sin(angle_to) * pull
            elif gesture == "ERASER" and dist < 280:
                # Frightened by open hand: dart away!
                angle_away = math.atan2(self.y - hy, self.x - hx)
                self.vx += math.cos(angle_away) * 0.55
                self.vy += math.sin(angle_away) * 0.55
                if np.random.rand() < 0.35:
                    self.bubbles.append([self.x, self.y, np.random.randint(4, 9), 1.0])

        # Gentle organic wandering force
        self.vx += np.random.uniform(-0.14, 0.14)
        self.vy += np.random.uniform(-0.09, 0.09)

        # Velocity damping / clamping
        speed = math.hypot(self.vx, self.vy)
        if speed > 6.5:
            self.vx = (self.vx / speed) * 6.5
            self.vy = (self.vy / speed) * 6.5
        elif speed < 1.6:
            self.vx = (self.vx / max(0.1, speed)) * 2.2
            self.vy = (self.vy / max(0.1, speed)) * 0.8

        self.x += self.vx
        self.y += self.vy

        # Boundary bouncing with smooth margins (avoiding top toolbar at y < 75)
        pad_x = self.w // 2 + 20
        pad_y = self.h // 2 + 75
        if self.x < pad_x:
            self.x = pad_x
            self.vx = abs(self.vx) * 0.95 + 0.8
        elif self.x > bounds_w - pad_x:
            self.x = bounds_w - pad_x
            self.vx = -abs(self.vx) * 0.95 - 0.8

        if self.y < pad_y:
            self.y = pad_y
            self.vy = abs(self.vy) * 0.95 + 0.5
        elif self.y > bounds_h - (self.h // 2 + 25):
            self.y = bounds_h - (self.h // 2 + 25)
            self.vy = -abs(self.vy) * 0.95 - 0.5

        # Bubble emission from tail
        if np.random.rand() < 0.06:
            bx = self.x - (1 if self.vx >= 0 else -1) * (self.w // 2)
            by = self.y + np.random.uniform(-4, 4)
            self.bubbles.append([bx, by, np.random.randint(3, 7), 0.85])

        # Update bubbles
        for b in self.bubbles:
            b[1] -= 1.6
            b[0] += np.random.uniform(-0.3, 0.3)
            b[3] -= 0.018
        self.bubbles = [b for b in self.bubbles if b[3] > 0 and b[1] > 70]

    def draw(self, target_bgr):
        # Determine facing direction
        sprite_to_draw = self.orig_sprite
        facing_left = (self.vx < 0)
        if facing_left:
            sprite_to_draw = cv2.flip(sprite_to_draw, 1)

        sh, sw = sprite_to_draw.shape[:2]

        # Apply swimming sine-wave wiggle deformation along width
        # The head remains steady while the tail swishes back and forth
        deformed = np.zeros_like(sprite_to_draw)
        max_shift = int(self.wiggle_amp) + 2
        padded_h = sh + max_shift * 2
        padded = np.zeros((padded_h, sw, 4), dtype=np.uint8)
        padded[max_shift:max_shift + sh, :, :] = sprite_to_draw

        for col in range(sw):
            # Tail weight: 1.0 at tail, 0.0 at head
            tail_factor = (col / max(1, sw)) if facing_left else ((sw - col) / max(1, sw))
            shift_y = int(self.wiggle_amp * tail_factor * math.sin(self.phase + col * 0.12))
            src_y_start = max_shift - shift_y
            if 0 <= src_y_start and src_y_start + sh <= padded_h:
                deformed[:, col] = padded[src_y_start:src_y_start + sh, col]
            else:
                deformed[:, col] = sprite_to_draw[:, col]

        # Target placement
        top_left_x = int(self.x - sw // 2)
        top_left_y = int(self.y - sh // 2)

        # Bounds clipping
        th, tw = target_bgr.shape[:2]
        x1 = max(0, top_left_x)
        y1 = max(0, top_left_y)
        x2 = min(tw, top_left_x + sw)
        y2 = min(th, top_left_y + sh)

        if x2 > x1 and y2 > y1:
            src_x1 = x1 - top_left_x
            src_y1 = y1 - top_left_y
            src_x2 = src_x1 + (x2 - x1)
            src_y2 = src_y1 + (y2 - y1)

            sub_deformed = deformed[src_y1:src_y2, src_x1:src_x2]
            alpha = (sub_deformed[:, :, 3] / 255.0)[:, :, np.newaxis]
            rgb = sub_deformed[:, :, :3]

            target_bgr[y1:y2, x1:x2] = (
                alpha * rgb + (1.0 - alpha) * target_bgr[y1:y2, x1:x2]
            ).astype(np.uint8)

        # Draw bubbles
        for bx, by, br, balpha in self.bubbles:
            ibx, iby = int(bx), int(by)
            if 0 <= ibx < tw and 0 <= iby < th:
                cv2.circle(target_bgr, (ibx, iby), br, (240, 240, 255), 1, cv2.LINE_AA)
                cv2.circle(target_bgr, (ibx - 1, iby - 1), max(1, br // 2), (255, 255, 255), -1, cv2.LINE_AA)


class CanvasEngine:
    """Manages digital drawing layers, strokes, shapes, presenter tools, and living doodles."""

    def __init__(self, width=config.DEFAULT_WIDTH, height=config.DEFAULT_HEIGHT):
        self.width = width
        self.height = height

        # RGBA canvas: BGR color + Alpha channel (0 = transparent, 255 = drawn)
        self.canvas = np.zeros((self.height, self.width, 4), dtype=np.uint8)

        # Drawing state
        self.active_tool = ToolType.PEN
        self.active_color_name = config.DEFAULT_COLOR_NAME
        self.active_color_bgr = config.COLORS[self.active_color_name]
        self.brush_size = config.BRUSH_SIZES[config.DEFAULT_BRUSH_SIZE_NAME]
        self.eraser_radius = config.ERASER_SIZES[config.DEFAULT_ERASER_SIZE_NAME]
        self.canvas_mode = CanvasMode.CAMERA_OVERLAY

        # Stroke tracking
        self.prev_point = None
        self.shape_start_point = None
        self.is_drawing_shape = False
        self.current_stroke_points = []

        # Smart features
        self.auto_shape_snap = config.AUTO_SHAPE_SNAP_DEFAULT
        self.last_snapped_shape = None

        # Presenter tools
        self.laser_points = []  # [(x, y, timestamp)]
        self.spotlight_radius = config.SPOTLIGHT_RADIUS

        # Living Doodles system
        self.alive_doodles = []

        # Undo / Redo history
        self.undo_stack = []
        self.redo_stack = []
        self.stroke_in_progress = False

    def push_undo_state(self):
        """Saves current canvas state to undo history before making changes."""
        if len(self.undo_stack) >= config.MAX_HISTORY_STATES:
            self.undo_stack.pop(0)
        self.undo_stack.append(self.canvas.copy())
        self.redo_stack.clear()

    def undo(self):
        """Restores the previous canvas state."""
        if not self.undo_stack:
            return False
        self.redo_stack.append(self.canvas.copy())
        self.canvas = self.undo_stack.pop()
        self.prev_point = None
        self.shape_start_point = None
        self.current_stroke_points.clear()
        return True

    def redo(self):
        """Restores the forward canvas state."""
        if not self.redo_stack:
            return False
        self.undo_stack.append(self.canvas.copy())
        self.canvas = self.redo_stack.pop()
        self.prev_point = None
        self.shape_start_point = None
        self.current_stroke_points.clear()
        return True

    def clear(self):
        """Wipes the canvas completely, saving to undo history."""
        self.push_undo_state()
        self.canvas = np.zeros((self.height, self.width, 4), dtype=np.uint8)
        self.prev_point = None
        self.shape_start_point = None
        self.stroke_in_progress = False
        self.current_stroke_points.clear()

    def set_tool(self, tool_type):
        """Switches active tool and resets active stroke."""
        self.active_tool = tool_type
        self.prev_point = None
        self.shape_start_point = None
        self.current_stroke_points.clear()

    def set_color(self, color_name):
        """Updates active drawing color."""
        if color_name in config.COLORS:
            self.active_color_name = color_name
            self.active_color_bgr = config.COLORS[color_name]

    def set_brush_size(self, size_name_or_val):
        """Updates brush stroke size."""
        if isinstance(size_name_or_val, str) and size_name_or_val in config.BRUSH_SIZES:
            self.brush_size = config.BRUSH_SIZES[size_name_or_val]
        elif isinstance(size_name_or_val, (int, float)):
            self.brush_size = int(size_name_or_val)

    def set_eraser_size(self, size_name_or_val):
        """Updates eraser radius."""
        if isinstance(size_name_or_val, str) and size_name_or_val in config.ERASER_SIZES:
            self.eraser_radius = config.ERASER_SIZES[size_name_or_val]
        elif isinstance(size_name_or_val, (int, float)):
            self.eraser_radius = int(size_name_or_val)

    def process_point(self, curr_point, gesture):
        """
        Receives smoothed fingertip point and active gesture, updating canvas.
        Handles stroke initiation, continuation, laser recording, and termination.
        """
        if curr_point is None:
            self.finish_stroke()
            return

        x, y = curr_point

        # 1. Presenter Laser Pointer (does not write to permanent canvas)
        if self.active_tool == ToolType.LASER:
            self.laser_points.append((x, y, time.time()))
            return

        # 2. Presenter Spotlight Mode (no permanent stroke)
        if self.active_tool == ToolType.SPOTLIGHT:
            return

        # 3. Quick Gesture Eraser (Open Palm or 3+ fingers)
        if gesture == "ERASER" or self.active_tool == ToolType.ERASER:
            if not self.stroke_in_progress:
                self.push_undo_state()
                self.stroke_in_progress = True

            radius = self.eraser_radius * 2 if gesture == "ERASER" else self.eraser_radius
            self._erase_at(x, y, radius)
            self.prev_point = (x, y)
            return

        # 4. Freehand Pen & Highlighter
        if gesture == "DRAW":
            if self.active_tool in (ToolType.PEN, ToolType.HIGHLIGHTER):
                if not self.stroke_in_progress:
                    self.push_undo_state()
                    self.stroke_in_progress = True
                    self.current_stroke_points = [(x, y)]

                if self.prev_point is None:
                    self.prev_point = (x, y)

                if self.active_tool == ToolType.PEN:
                    self._draw_pen_segment(self.prev_point, (x, y))
                    self.current_stroke_points.append((x, y))
                elif self.active_tool == ToolType.HIGHLIGHTER:
                    self._draw_highlighter_segment(self.prev_point, (x, y))

                self.prev_point = (x, y)

            # 5. Shape Tools: Line, Rectangle, Circle, Arrow
            elif self.active_tool in (ToolType.LINE, ToolType.RECTANGLE, ToolType.CIRCLE, ToolType.ARROW):
                if not self.is_drawing_shape:
                    self.shape_start_point = (x, y)
                    self.is_drawing_shape = True
                self.prev_point = (x, y)
        else:
            # Gesture is SELECT, PINCH, HOVER, or NONE -> finalize active stroke
            self.finish_stroke()

    def finish_stroke(self):
        """Finalizes any active stroke, checks for auto-shape snapping, or commits shape."""
        # Check for smart shape snapping if drawing in Pen mode
        if self.stroke_in_progress and self.auto_shape_snap and self.active_tool == ToolType.PEN:
            snapped, shape_name = self._detect_and_snap_shape(self.current_stroke_points)
            if snapped:
                self.last_snapped_shape = shape_name

        self.current_stroke_points.clear()

        # Commit manual shape tool if active
        if self.is_drawing_shape and self.shape_start_point and self.prev_point:
            self.push_undo_state()
            self._commit_shape(self.shape_start_point, self.prev_point, self.active_tool)
            self.is_drawing_shape = False
            self.shape_start_point = None

        self.prev_point = None
        self.stroke_in_progress = False

    def _draw_pen_segment(self, pt1, pt2):
        """Draws solid anti-aliased segment with rounded caps onto canvas."""
        b, g, r = self.active_color_bgr
        color_rgba = (b, g, r, 255)
        cv2.line(self.canvas, pt1, pt2, color_rgba, self.brush_size, cv2.LINE_AA)
        radius = max(1, self.brush_size // 2)
        cv2.circle(self.canvas, pt2, radius, color_rgba, -1, cv2.LINE_AA)

    def _draw_highlighter_segment(self, pt1, pt2):
        """Draws translucent highlighter stroke with alpha blending."""
        b, g, r = self.active_color_bgr
        color_rgba = (b, g, r, 90)
        thick_size = self.brush_size * 2 + 6

        overlay = np.zeros_like(self.canvas)
        cv2.line(overlay, pt1, pt2, color_rgba, thick_size, cv2.LINE_AA)
        cv2.circle(overlay, pt2, thick_size // 2, color_rgba, -1, cv2.LINE_AA)

        mask = overlay[:, :, 3] > 0
        self.canvas[mask] = overlay[mask]

    def _erase_at(self, x, y, radius):
        """Clears circular area on canvas back to transparent."""
        cv2.circle(self.canvas, (x, y), radius, (0, 0, 0, 0), -1, cv2.LINE_AA)

    def _commit_shape(self, start_pt, end_pt, tool_type):
        """Bakes geometric shape into canvas."""
        b, g, r = self.active_color_bgr
        color_rgba = (b, g, r, 255)
        thickness = self.brush_size

        if tool_type == ToolType.LINE:
            cv2.line(self.canvas, start_pt, end_pt, color_rgba, thickness, cv2.LINE_AA)

        elif tool_type == ToolType.RECTANGLE:
            cv2.rectangle(self.canvas, start_pt, end_pt, color_rgba, thickness, cv2.LINE_AA)

        elif tool_type == ToolType.CIRCLE:
            radius = int(math.hypot(end_pt[0] - start_pt[0], end_pt[1] - start_pt[1]))
            if radius > 2:
                cv2.circle(self.canvas, start_pt, radius, color_rgba, thickness, cv2.LINE_AA)

        elif tool_type == ToolType.ARROW:
            self._draw_arrow(self.canvas, start_pt, end_pt, color_rgba, thickness)

    def _draw_arrow(self, target_img, start_pt, end_pt, color, thickness):
        """Draws an anti-aliased arrow from start_pt to end_pt."""
        dx = end_pt[0] - start_pt[0]
        dy = end_pt[1] - start_pt[1]
        length = math.hypot(dx, dy)
        if length < 5:
            return

        cv2.line(target_img, start_pt, end_pt, color, thickness, cv2.LINE_AA)
        arrow_size = min(35, max(15, thickness * 3))
        angle = math.atan2(dy, dx)
        wing1 = (
            int(end_pt[0] - arrow_size * math.cos(angle - math.pi / 6)),
            int(end_pt[1] - arrow_size * math.sin(angle - math.pi / 6))
        )
        wing2 = (
            int(end_pt[0] - arrow_size * math.cos(angle + math.pi / 6)),
            int(end_pt[1] - arrow_size * math.sin(angle + math.pi / 6))
        )
        cv2.line(target_img, end_pt, wing1, color, thickness, cv2.LINE_AA)
        cv2.line(target_img, end_pt, wing2, color, thickness, cv2.LINE_AA)

    def _detect_and_snap_shape(self, stroke_pts):
        """
        Analyzes freehand stroke points and snaps to clean geometry if shape detected.
        Detects: Straight Line, Circle/Ellipse, Rectangle, Triangle.
        Returns: (detected: bool, shape_name: str or None)
        """
        if len(stroke_pts) < 14:
            return False, None

        pts = np.array(stroke_pts, dtype=np.int32)
        start_pt = stroke_pts[0]
        end_pt = stroke_pts[-1]

        diffs = pts[1:] - pts[:-1]
        segment_lengths = np.sqrt(np.sum(diffs ** 2, axis=1))
        total_path_len = np.sum(segment_lengths)
        direct_dist = math.hypot(end_pt[0] - start_pt[0], end_pt[1] - start_pt[1])

        if total_path_len < 35:
            return False, None

        linearity = direct_dist / total_path_len

        # Case A: Straight Line (high linearity)
        if linearity > 0.88 and direct_dist > 45:
            if self.undo_stack:
                self.canvas = self.undo_stack[-1].copy()
            self._commit_shape(start_pt, end_pt, ToolType.LINE)
            return True, "Straight Line"

        # Case B: Closed Loop (start & end points are near each other)
        is_closed = (direct_dist < 0.28 * total_path_len) or (direct_dist < 55)
        if is_closed:
            contour = pts.reshape((-1, 1, 2))
            area = cv2.contourArea(contour)
            perimeter = cv2.arcLength(contour, True)

            if perimeter > 45 and area > 120:
                circularity = (4.0 * math.pi * area) / (perimeter * perimeter)

                # Circle / Ellipse
                if circularity >= 0.65:
                    (cx, cy), radius = cv2.minEnclosingCircle(contour)
                    if self.undo_stack:
                        self.canvas = self.undo_stack[-1].copy()
                    center_pt = (int(cx), int(cy))
                    cv2.circle(self.canvas, center_pt, int(radius), (*self.active_color_bgr, 255), self.brush_size, cv2.LINE_AA)
                    return True, "Circle"

                # Polygon approximation
                epsilon = 0.045 * perimeter
                approx = cv2.approxPolyDP(contour, epsilon, True)
                num_vertices = len(approx)

                # Triangle
                if num_vertices == 3:
                    if self.undo_stack:
                        self.canvas = self.undo_stack[-1].copy()
                    tri_pts = approx.reshape((-1, 2))
                    for i in range(3):
                        p1 = tuple(tri_pts[i])
                        p2 = tuple(tri_pts[(i + 1) % 3])
                        cv2.line(self.canvas, p1, p2, (*self.active_color_bgr, 255), self.brush_size, cv2.LINE_AA)
                    return True, "Triangle"

                # Rectangle / Square
                elif num_vertices == 4:
                    if self.undo_stack:
                        self.canvas = self.undo_stack[-1].copy()
                    rect_x, rect_y, rect_w, rect_h = cv2.boundingRect(contour)
                    cv2.rectangle(
                        self.canvas,
                        (rect_x, rect_y),
                        (rect_x + rect_w, rect_y + rect_h),
                        (*self.active_color_bgr, 255),
                        self.brush_size,
                        cv2.LINE_AA
                    )
                    return True, "Rectangle"

        return False, None

    def render_laser(self, display_frame):
        """Renders dynamic fading laser trail and tip particle glow."""
        now = time.time()
        self.laser_points = [p for p in self.laser_points if now - p[2] <= config.LASER_DECAY_SECONDS]
        if len(self.laser_points) < 2:
            return display_frame

        pts = self.laser_points
        n = len(pts)
        laser_overlay = display_frame.copy()

        for i in range(n - 1):
            pt1 = (pts[i][0], pts[i][1])
            pt2 = (pts[i + 1][0], pts[i + 1][1])
            age = now - pts[i + 1][2]
            progress = max(0.0, 1.0 - (age / config.LASER_DECAY_SECONDS))

            thickness = max(2, int(8 * progress))
            # Glowing laser core (warm ruby / vibrant coral red)
            cv2.line(laser_overlay, pt1, pt2, (80, 100, 255), thickness + 4, cv2.LINE_AA)
            cv2.line(laser_overlay, pt1, pt2, (220, 230, 255), max(1, thickness - 2), cv2.LINE_AA)

        # Tip flare
        tip = (pts[-1][0], pts[-1][1])
        cv2.circle(laser_overlay, tip, 8, (120, 140, 255), -1, cv2.LINE_AA)
        cv2.circle(laser_overlay, tip, 4, (255, 255, 255), -1, cv2.LINE_AA)

        cv2.addWeighted(laser_overlay, 0.85, display_frame, 0.15, 0, display_frame)
        return display_frame

    def render_spotlight(self, display_frame, cursor_pt):
        """Dims everything except an illuminated radial spotlight on the cursor."""
        if cursor_pt is None:
            return display_frame

        cx, cy = cursor_pt
        h, w = display_frame.shape[:2]
        radius = config.SPOTLIGHT_RADIUS

        mask = np.zeros((h, w), dtype=np.float32)
        cv2.circle(mask, (cx, cy), radius, 1.0, -1, cv2.LINE_AA)
        mask = cv2.GaussianBlur(mask, (71, 71), 25)

        dimmed = (display_frame.astype(np.float32) * 0.25).astype(np.uint8)
        mask_3ch = np.dstack([mask, mask, mask])

        spotlight_frame = (
            mask_3ch * display_frame.astype(np.float32) + (1.0 - mask_3ch) * dimmed.astype(np.float32)
        ).astype(np.uint8)

        # Subtle golden spotlight border ring
        cv2.circle(spotlight_frame, (cx, cy), radius, (0, 220, 255), 2, cv2.LINE_AA)
        return spotlight_frame

    def animate_last_drawing(self):
        """
        Extracts the most recently drawn doodle from the canvas, clears it from static ink,
        and spawns an animated AliveDoodle that swims and moves around!
        Returns: (success: bool, message: str)
        """
        alpha = self.canvas[:, :, 3]
        if np.count_nonzero(alpha) < 50:
            return False, "Draw a doodle first to bring it alive!"

        contours, _ = cv2.findContours(alpha, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return False, "No doodle contours found!"

        valid_contours = [c for c in contours if cv2.contourArea(c) > 80]
        if not valid_contours:
            valid_contours = contours

        # Pick the largest doodle contour
        chosen = max(valid_contours, key=cv2.contourArea)
        bx, by, bw, bh = cv2.boundingRect(chosen)

        pad = 8
        bx1 = max(0, bx - pad)
        by1 = max(0, by - pad)
        bx2 = min(self.width, bx + bw + pad)
        by2 = min(self.height, by + bh + pad)

        cropped_sprite = self.canvas[by1:by2, bx1:bx2].copy()

        # Save state before clearing static ink
        self.push_undo_state()

        # Erase doodle from static ink (it comes alive!)
        self.canvas[by1:by2, bx1:bx2] = 0

        center_x = (bx1 + bx2) // 2
        center_y = (by1 + by2) // 2
        doodle = AliveDoodle(cropped_sprite, center_x, center_y)
        self.alive_doodles.append(doodle)

        return True, f"Doodle brought to life! ({len(self.alive_doodles)} active ✨)"

    def update_alive_doodles(self, hand_pt=None, gesture="NONE"):
        """Advances animation kinematics and hand interaction for all living doodles."""
        for doodle in self.alive_doodles:
            doodle.update(self.width, self.height, hand_pt, gesture)

    def render_alive_doodles(self, target_bgr):
        """Draws all living creatures onto display frame."""
        for doodle in self.alive_doodles:
            doodle.draw(target_bgr)
        return target_bgr

    def freeze_alive_doodles(self):
        """Bakes active living doodles back into static canvas ink."""
        if not self.alive_doodles:
            return False
        self.push_undo_state()
        for d in self.alive_doodles:
            sh, sw = d.orig_sprite.shape[:2]
            tx = int(d.x - sw // 2)
            ty = int(d.y - sh // 2)
            for y in range(sh):
                for x in range(sw):
                    cy = ty + y
                    cx = tx + x
                    if 0 <= cy < self.height and 0 <= cx < self.width:
                        if d.orig_sprite[y, x, 3] > 0:
                            self.canvas[cy, cx] = d.orig_sprite[y, x]
        self.alive_doodles.clear()
        return True

    def clear_alive_doodles(self):
        """Clears all living doodles."""
        count = len(self.alive_doodles)
        self.alive_doodles.clear()
        return count > 0

    def render_preview(self, frame_bgr):
        """Renders live shape ghost preview onto display frame while user is dragging."""
        if not self.is_drawing_shape or not self.shape_start_point or not self.prev_point:
            return frame_bgr

        preview = frame_bgr.copy()
        color = self.active_color_bgr
        thickness = self.brush_size
        start_pt = self.shape_start_point
        end_pt = self.prev_point

        if self.active_tool == ToolType.LINE:
            cv2.line(preview, start_pt, end_pt, color, thickness, cv2.LINE_AA)

        elif self.active_tool == ToolType.RECTANGLE:
            cv2.rectangle(preview, start_pt, end_pt, color, thickness, cv2.LINE_AA)

        elif self.active_tool == ToolType.CIRCLE:
            radius = int(math.hypot(end_pt[0] - start_pt[0], end_pt[1] - start_pt[1]))
            if radius > 2:
                cv2.circle(preview, start_pt, radius, color, thickness, cv2.LINE_AA)

        elif self.active_tool == ToolType.ARROW:
            self._draw_arrow(preview, start_pt, end_pt, color, thickness)

        return cv2.addWeighted(preview, 0.85, frame_bgr, 0.15, 0)

    def composite_frame(self, camera_frame_bgr, mode=None):
        """
        Composites canvas drawings onto the chosen background mode:
        - CAMERA_OVERLAY: Draws directly over mirrored camera feed.
        - WHITEBOARD: Pure crisp off-white digital whiteboard background.
        - BLACKBOARD: Modern dark slate chalkboard background.
        """
        mode = mode or self.canvas_mode
        h, w = camera_frame_bgr.shape[:2]

        if mode == CanvasMode.WHITEBOARD:
            base_frame = np.full((h, w, 3), 250, dtype=np.uint8)
        elif mode == CanvasMode.BLACKBOARD:
            base_frame = np.full((h, w, 3), (30, 26, 24), dtype=np.uint8)
        else:
            base_frame = camera_frame_bgr.copy()

        canvas_bgr = self.canvas[:, :, :3]
        alpha = self.canvas[:, :, 3] / 255.0

        for c in range(3):
            base_frame[:, :, c] = (
                alpha * canvas_bgr[:, :, c] + (1.0 - alpha) * base_frame[:, :, c]
            ).astype(np.uint8)

        return base_frame

    def get_clean_export_image(self, mode=None):
        """Produces a crisp full-resolution export image (without camera artifacts)."""
        mode = mode or self.canvas_mode
        if mode in (CanvasMode.CAMERA_OVERLAY, CanvasMode.WHITEBOARD):
            bg_color = (252, 250, 248)  # Clean off-white
        else:
            bg_color = (30, 26, 24)      # Dark slate chalkboard

        export_img = np.full((self.height, self.width, 3), bg_color, dtype=np.uint8)
        canvas_bgr = self.canvas[:, :, :3]
        alpha = self.canvas[:, :, 3] / 255.0

        for c in range(3):
            export_img[:, :, c] = (
                alpha * canvas_bgr[:, :, c] + (1.0 - alpha) * export_img[:, :, c]
            ).astype(np.uint8)

        return export_img
