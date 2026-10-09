"""
Virtual Whiteboard Using Hand Gestures.
Main application orchestrating webcam capture, MediaPipe hand tracking,
ergonomic depth/pinch drawing, smart shape snapping, presenter tools (Laser, Spotlight),
animated living doodles ("Bring to Life"), and document export.
"""

import sys
import time
import cv2
import numpy as np

import config
from config import CanvasMode, ToolType
from hand_tracker import HandTracker
from canvas_engine import CanvasEngine
from ui_overlay import UIOverlay
from exporter import Exporter


class VirtualWhiteboardApp:
    """Core controller for the Virtual Whiteboard application."""

    def __init__(self, camera_index=0):
        self.camera_index = camera_index
        self.cap = None

        # Components
        self.tracker = None
        self.canvas_engine = None
        self.ui = None
        self.exporter = None

        # State
        self.width = config.DEFAULT_WIDTH
        self.height = config.DEFAULT_HEIGHT
        self.fps = 0.0
        self.prev_time = time.time()
        self.is_running = False

        # Mouse fallback support
        self.mouse_cursor = None
        self.mouse_pressed = False

    def setup(self):
        """Initializes camera, tracking model, canvas, and UI overlay."""
        print("[VirtualWhiteboard] Initializing camera...")
        self.cap = cv2.VideoCapture(self.camera_index)
        if not self.cap.isOpened():
            print(f"[VirtualWhiteboard] Warning: Could not open camera {self.camera_index}, trying camera 1...")
            self.cap = cv2.VideoCapture(1)

        if self.cap.isOpened():
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.DEFAULT_WIDTH)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.DEFAULT_HEIGHT)
            actual_w = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            actual_h = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            if actual_w > 0 and actual_h > 0:
                self.width = actual_w
                self.height = actual_h

        print(f"[VirtualWhiteboard] Resolution: {self.width}x{self.height}")
        print("[VirtualWhiteboard] Loading MediaPipe Hand Landmarker...")
        self.tracker = HandTracker()
        self.canvas_engine = CanvasEngine(self.width, self.height)
        self.ui = UIOverlay(self.width, self.height)
        self.exporter = Exporter()

        # OpenCV window configuration
        cv2.namedWindow("Virtual Whiteboard", cv2.WINDOW_NORMAL)
        cv2.resizeWindow("Virtual Whiteboard", self.width, self.height)
        cv2.setMouseCallback("Virtual Whiteboard", self._on_mouse)

    def _on_mouse(self, event, x, y, flags, param):
        """Allows mouse interaction as a fallback/debugging input."""
        self.mouse_cursor = (x, y)
        if event == cv2.EVENT_LBUTTONDOWN:
            self.mouse_pressed = True
            action = self.ui.check_interaction((x, y), is_pinching=True, canvas_engine=self.canvas_engine)
            if action:
                self._handle_action(action)
        elif event == cv2.EVENT_LBUTTONUP:
            self.mouse_pressed = False
            self.canvas_engine.finish_stroke()

    def _handle_action(self, action):
        """Executes actions triggered from UI toolbar or keyboard shortcuts."""
        if action == "SAVE_PNG":
            export_img = self.canvas_engine.get_clean_export_image()
            ok, path = self.exporter.save_image(export_img, format="png")
            if ok:
                self.ui.play_sound("success")
                self.ui.show_toast(f"Saved: {path}")
                print(f"[VirtualWhiteboard] Image saved to {path}")
            else:
                self.ui.show_toast("Failed to save image")

        elif action == "SAVE_PDF":
            export_img = self.canvas_engine.get_clean_export_image()
            ok, path = self.exporter.save_pdf(export_img)
            if ok:
                self.ui.play_sound("success")
                self.ui.show_toast(f"Exported PDF: {path}")
                print(f"[VirtualWhiteboard] PDF saved to {path}")
            else:
                self.ui.show_toast("Failed to export PDF")

        elif action == "ALIVE":
            ok, msg = self.canvas_engine.animate_last_drawing()
            if ok:
                self.ui.play_sound("magic")
            self.ui.show_toast(msg)

        elif action == "TOGGLE_SNAP":
            self.canvas_engine.auto_shape_snap = not self.canvas_engine.auto_shape_snap
            state_str = "ON" if self.canvas_engine.auto_shape_snap else "OFF"
            self.ui.show_toast(f"Shape Snapping: {state_str}")

        elif action == "TOGGLE_PINCH_DRAW":
            self.tracker.pinch_to_draw = not self.tracker.pinch_to_draw
            state_str = "ON" if self.tracker.pinch_to_draw else "OFF"
            self.ui.show_toast(f"Pinch-Draw Mode: {state_str}")

    def run(self):
        """Main application execution loop."""
        self.setup()
        self.is_running = True
        self.ui.show_toast("Welcome! Index to Draw, Peace sign to Select, [W] to Bring Doodle Alive ✨", duration=4.0)

        print("\n=======================================================")
        print("          Virtual Whiteboard Application Active        ")
        print("=======================================================")
        print(" Gestures:")
        print("  - Index Finger UP: Draw / Freehand / Shapes")
        print("  - Index + Middle UP: Selection / Hover Cursor")
        print("  - Open Palm / 3+ Fingers: Eraser Mode")
        print("  - Thumb + Index Pinch: Instant Click / Select")
        print(" Smart & Presenter Features:")
        print("  - [W]: Bring your drawing alive! (swimming/floating doodle)")
        print("  - [F]: Freeze / bake living doodles back to canvas")
        print("  - [N]: Toggle Smart Shape Snapping (Circle, Rect, Line)")
        print("  - [K]: Presenter Laser Pointer (fading trail)")
        print("  - [J]: Presenter Spotlight Mode")
        print("  - [T]: Toggle Apple Vision Pro Pinch-to-Draw Mode")
        print("  - [C]: Clear Canvas       [Z]: Undo       [Y]: Redo")
        print("  - [S]: Save PNG           [P]: Export PDF [M]: Cycle BG Mode")
        print("=======================================================\n")

        while self.is_running:
            # 1. Capture camera frame
            if self.cap and self.cap.isOpened():
                ret, frame = self.cap.read()
                if not ret:
                    frame = 255 * (time.time() % 2 > 1) * cv2.ones((self.height, self.width, 3), dtype=np.uint8)
            else:
                frame = np.full((self.height, self.width, 3), 240, dtype=np.uint8)

            # Mirror frame horizontally for natural interaction
            frame = cv2.flip(frame, 1)

            if frame.shape[0] != self.height or frame.shape[1] != self.width:
                frame = cv2.resize(frame, (self.width, self.height))

            # 2. Track hand landmarks
            hand_info = self.tracker.find_hands(frame)

            # 3. Determine active cursor point and interaction mode
            cursor_pt = hand_info.get("index_tip")
            gesture = hand_info.get("gesture", "NONE")
            is_pinching = (gesture == "PINCH")

            # Mouse fallback
            if not hand_info["detected"] and self.mouse_pressed and self.mouse_cursor:
                cursor_pt = self.mouse_cursor
                gesture = "DRAW"

            # 4. Handle UI Toolbar Interaction (Top region: y < 66)
            in_toolbar = False
            if cursor_pt is not None:
                cx, cy = cursor_pt
                if cy < 66:
                    in_toolbar = True
                    action = self.ui.check_interaction(cursor_pt, is_pinching, self.canvas_engine)
                    if action:
                        self._handle_action(action)
                else:
                    self.ui.check_interaction(None, False, self.canvas_engine)

            # 5. Process Drawing on Canvas (Only outside toolbar)
            if not in_toolbar:
                self.canvas_engine.process_point(cursor_pt, gesture)
            else:
                self.canvas_engine.finish_stroke()

            # Check if smart shape was snapped and notify
            if self.canvas_engine.last_snapped_shape:
                self.ui.play_sound("snap")
                self.ui.show_toast(f"Snapped: {self.canvas_engine.last_snapped_shape} ✨")
                self.canvas_engine.last_snapped_shape = None

            # 6. Composite Canvas with Background Mode
            display_frame = self.canvas_engine.composite_frame(frame)

            # 7. Render live shape ghost preview
            display_frame = self.canvas_engine.render_preview(display_frame)

            # 8. Update and render living doodles ("Bring to Life")
            if self.canvas_engine.alive_doodles:
                self.canvas_engine.update_alive_doodles(cursor_pt, gesture)
                display_frame = self.canvas_engine.render_alive_doodles(display_frame)

            # 9. Render Presenter Tools: Laser & Spotlight
            display_frame = self.canvas_engine.render_laser(display_frame)
            if self.canvas_engine.active_tool == ToolType.SPOTLIGHT and cursor_pt is not None:
                display_frame = self.canvas_engine.render_spotlight(display_frame, cursor_pt)

            # 10. Render Hand Skeleton Visualizer
            if hand_info["detected"]:
                landmarks = hand_info["landmarks"]
                if self.canvas_engine.canvas_mode == CanvasMode.CAMERA_OVERLAY:
                    self.tracker.draw_hand_skeleton(display_frame, landmarks, draw_color=(0, 220, 255))
                else:
                    self.ui.render_pip(display_frame, frame, self.tracker, landmarks)
            elif self.canvas_engine.canvas_mode != CanvasMode.CAMERA_OVERLAY:
                self.ui.render_pip(display_frame, frame, self.tracker, None)

            # 11. Compute FPS
            curr_time = time.time()
            fps_instant = 1.0 / max(0.001, curr_time - self.prev_time)
            self.fps = 0.9 * self.fps + 0.1 * fps_instant
            self.prev_time = curr_time

            # 12. Render UI HUD, Toolbars, Cursors & Toasts
            display_frame = self.ui.render(display_frame, self.canvas_engine, hand_info, self.fps)

            # 13. Display Frame
            cv2.imshow("Virtual Whiteboard", display_frame)

            # 14. Handle Keyboard Shortcuts
            key = cv2.waitKey(1) & 0xFF
            if key != 255:
                self._handle_key(key)

        self._cleanup()

    def _handle_key(self, key):
        """Processes keyboard hotkey shortcuts."""
        if key in (27, ord('q'), ord('Q')):  # ESC or Q: Quit
            self.is_running = False

        elif key in (ord('c'), ord('C')):    # C: Clear
            self.canvas_engine.clear()
            self.canvas_engine.clear_alive_doodles()
            self.ui.play_sound("clear")
            self.ui.show_toast("Canvas Cleared")

        elif key in (ord('z'), ord('Z')):    # Z: Undo
            ok = self.canvas_engine.undo()
            self.ui.show_toast("Undo" if ok else "Nothing to undo")

        elif key in (ord('y'), ord('Y')):    # Y: Redo
            ok = self.canvas_engine.redo()
            self.ui.show_toast("Redo" if ok else "Nothing to redo")

        elif key in (ord('w'), ord('W')):    # W: Bring doodle alive!
            ok, msg = self.canvas_engine.animate_last_drawing()
            if ok:
                self.ui.play_sound("magic")
            self.ui.show_toast(msg)

        elif key in (ord('f'), ord('F')):    # F: Freeze living doodles
            ok = self.canvas_engine.freeze_alive_doodles()
            self.ui.show_toast("Doodles baked to canvas" if ok else "No active doodles")

        elif key in (ord('n'), ord('N')):    # N: Toggle smart shape snapping
            self.canvas_engine.auto_shape_snap = not self.canvas_engine.auto_shape_snap
            state_str = "ON" if self.canvas_engine.auto_shape_snap else "OFF"
            self.ui.show_toast(f"Shape Snapping: {state_str}")

        elif key in (ord('t'), ord('T')):    # T: Toggle Pinch-to-draw
            self.tracker.pinch_to_draw = not self.tracker.pinch_to_draw
            state_str = "ON" if self.tracker.pinch_to_draw else "OFF"
            self.ui.show_toast(f"Pinch-to-Draw: {state_str}")

        elif key in (ord('k'), ord('K')):    # K: Laser pointer
            self.canvas_engine.set_tool(ToolType.LASER)
            self.ui.show_toast("Tool: Laser Pointer")

        elif key in (ord('j'), ord('J')):    # J: Spotlight
            self.canvas_engine.set_tool(ToolType.SPOTLIGHT)
            self.ui.show_toast("Tool: Spotlight")

        elif key in (ord('s'), ord('S')):    # S: Save PNG
            self._handle_action("SAVE_PNG")

        elif key in (ord('p'), ord('P')):    # P: Export PDF
            self._handle_action("SAVE_PDF")

        elif key in (ord('m'), ord('M')):    # M: Cycle background mode
            modes = [CanvasMode.CAMERA_OVERLAY, CanvasMode.WHITEBOARD, CanvasMode.BLACKBOARD]
            idx = (modes.index(self.canvas_engine.canvas_mode) + 1) % len(modes)
            self.canvas_engine.canvas_mode = modes[idx]
            self.ui.show_toast(f"Mode: {self.canvas_engine.canvas_mode.value}")

        elif key == ord('1'):
            self.canvas_engine.set_brush_size("Fine")
            self.ui.show_toast("Brush: Fine (4px)")
        elif key == ord('2'):
            self.canvas_engine.set_brush_size("Medium")
            self.ui.show_toast("Brush: Medium (8px)")
        elif key == ord('3'):
            self.canvas_engine.set_brush_size("Bold")
            self.ui.show_toast("Brush: Bold (15px)")
        elif key == ord('4'):
            self.canvas_engine.set_brush_size("Marker")
            self.ui.show_toast("Brush: Marker (26px)")

        elif key in (ord('d'), ord('D')):
            self.canvas_engine.set_tool(ToolType.PEN)
            self.ui.show_toast("Tool: Pen")
        elif key in (ord('e'), ord('E')):
            self.canvas_engine.set_tool(ToolType.ERASER)
            self.ui.show_toast("Tool: Eraser")
        elif key in (ord('h'), ord('H')):
            self.canvas_engine.set_tool(ToolType.HIGHLIGHTER)
            self.ui.show_toast("Tool: Highlighter")
        elif key in (ord('l'), ord('L')):
            self.canvas_engine.set_tool(ToolType.LINE)
            self.ui.show_toast("Tool: Line")
        elif key in (ord('r'), ord('R')):
            self.canvas_engine.set_tool(ToolType.RECTANGLE)
            self.ui.show_toast("Tool: Rectangle")
        elif key in (ord('o'), ord('O')):
            self.canvas_engine.set_tool(ToolType.CIRCLE)
            self.ui.show_toast("Tool: Circle")
        elif key in (ord('a'), ord('A')):
            self.canvas_engine.set_tool(ToolType.ARROW)
            self.ui.show_toast("Tool: Arrow")

    def _cleanup(self):
        """Releases camera and closes windows."""
        print("[VirtualWhiteboard] Shutting down...")
        if self.cap:
            self.cap.release()
        cv2.destroyAllWindows()
        print("[VirtualWhiteboard] Application terminated cleanly.")


if __name__ == "__main__":
    app = VirtualWhiteboardApp()
    try:
        app.run()
    except KeyboardInterrupt:
        app._cleanup()
        sys.exit(0)
