"""
Automated unit and integration test suite for Virtual Whiteboard.
Validates tracking initialization, canvas engine operations, undo/redo,
shapes, smart shape snapping, presenter tools (Laser, Spotlight),
animated living doodles ("Bring to Life"), UI interactions, and PDF/image export.
"""

import os
import unittest
import numpy as np
import cv2

import config
from config import CanvasMode, ToolType
from hand_tracker import HandTracker
from canvas_engine import CanvasEngine
from ui_overlay import UIOverlay
from exporter import Exporter


class TestVirtualWhiteboard(unittest.TestCase):
    """Integration test suite for all whiteboard components."""

    @classmethod
    def setUpClass(cls):
        cls.width = 1280
        cls.height = 720
        cls.test_dir = os.path.join(config.BASE_DIR, "test_output")
        os.makedirs(cls.test_dir, exist_ok=True)

    def test_01_hand_tracker_init_and_detect(self):
        """Validates MediaPipe HandLandmarker initialization and dummy inference."""
        tracker = HandTracker()
        dummy_frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        result = tracker.find_hands(dummy_frame)

        self.assertIsInstance(result, dict)
        self.assertIn("detected", result)
        self.assertIn("gesture", result)
        self.assertIn("z_depth", result)
        self.assertIn("pinch_to_draw", result)
        self.assertFalse(result["detected"])
        self.assertEqual(result["gesture"], "NONE")

    def test_02_canvas_pen_and_highlighter(self):
        """Tests freehand pen and highlighter drawing on RGBA canvas."""
        engine = CanvasEngine(self.width, self.height)

        engine.set_tool(ToolType.PEN)
        engine.process_point((100, 100), "DRAW")
        engine.process_point((200, 200), "DRAW")
        engine.finish_stroke()

        alpha_channel = engine.canvas[:, :, 3]
        drawn_pixels = np.count_nonzero(alpha_channel)
        self.assertGreater(drawn_pixels, 50, "Pen stroke should write non-zero alpha pixels")

        engine.set_tool(ToolType.HIGHLIGHTER)
        engine.process_point((300, 300), "DRAW")
        engine.process_point((400, 300), "DRAW")
        engine.finish_stroke()

        new_drawn = np.count_nonzero(engine.canvas[:, :, 3])
        self.assertGreater(new_drawn, drawn_pixels, "Highlighter should add to drawn canvas")

    def test_03_canvas_shapes(self):
        """Tests geometric shape drawing (Line, Rectangle, Circle, Arrow)."""
        engine = CanvasEngine(self.width, self.height)

        # Rectangle
        engine.set_tool(ToolType.RECTANGLE)
        engine.process_point((150, 150), "DRAW")
        engine.process_point((350, 350), "DRAW")
        engine.finish_stroke()

        rect_pixels = np.count_nonzero(engine.canvas[:, :, 3])
        self.assertGreater(rect_pixels, 100, "Rectangle should commit pixels")

        # Circle
        engine.set_tool(ToolType.CIRCLE)
        engine.process_point((500, 500), "DRAW")
        engine.process_point((550, 550), "DRAW")
        engine.finish_stroke()

        circle_pixels = np.count_nonzero(engine.canvas[:, :, 3])
        self.assertGreater(circle_pixels, rect_pixels, "Circle should add pixels")

    def test_04_undo_redo_and_clear(self):
        """Tests canvas history stack, undo, redo, and clear operations."""
        engine = CanvasEngine(self.width, self.height)

        self.assertEqual(np.count_nonzero(engine.canvas[:, :, 3]), 0)

        engine.set_tool(ToolType.PEN)
        engine.process_point((100, 100), "DRAW")
        engine.process_point((150, 150), "DRAW")
        engine.finish_stroke()
        pixels_state_1 = np.count_nonzero(engine.canvas[:, :, 3])
        self.assertGreater(pixels_state_1, 0)

        undo_ok = engine.undo()
        self.assertTrue(undo_ok)
        self.assertEqual(np.count_nonzero(engine.canvas[:, :, 3]), 0)

        redo_ok = engine.redo()
        self.assertTrue(redo_ok)
        self.assertEqual(np.count_nonzero(engine.canvas[:, :, 3]), pixels_state_1)

        engine.clear()
        self.assertEqual(np.count_nonzero(engine.canvas[:, :, 3]), 0)

        engine.undo()
        self.assertEqual(np.count_nonzero(engine.canvas[:, :, 3]), pixels_state_1)

    def test_05_compositing_modes(self):
        """Tests frame compositing across AR Camera, Whiteboard, and Blackboard modes."""
        engine = CanvasEngine(self.width, self.height)
        engine.set_tool(ToolType.PEN)
        engine.process_point((200, 200), "DRAW")
        engine.process_point((300, 300), "DRAW")
        engine.finish_stroke()

        dummy_cam = np.zeros((self.height, self.width, 3), dtype=np.uint8)

        ar_frame = engine.composite_frame(dummy_cam, CanvasMode.CAMERA_OVERLAY)
        self.assertEqual(ar_frame.shape, (self.height, self.width, 3))

        wb_frame = engine.composite_frame(dummy_cam, CanvasMode.WHITEBOARD)
        self.assertGreaterEqual(wb_frame[0, 0, 0], 240)

        bb_frame = engine.composite_frame(dummy_cam, CanvasMode.BLACKBOARD)
        self.assertLessEqual(bb_frame[0, 0, 0], 40)

    def test_06_ui_overlay_and_buttons(self):
        """Validates toolbar button setup, designer colors, and dwell/pinch interaction."""
        ui = UIOverlay(self.width, self.height)
        engine = CanvasEngine(self.width, self.height)

        self.assertGreater(len(ui.buttons), 18, "Toolbar should have all tools, colors, sizes, and actions")

        # Verify new designer palette buttons exist
        indigo_btn = next((b for b in ui.buttons if b.btn_id == "color_Royal Indigo"), None)
        self.assertIsNotNone(indigo_btn, "Royal Indigo designer color button should exist")

        # Test clicking Pen button via pinch
        pen_btn = next(b for b in ui.buttons if b.btn_id == "tool_pen")
        action = ui.check_interaction((pen_btn.x + 5, pen_btn.y + 5), is_pinching=True, canvas_engine=engine)
        self.assertEqual(action, "TOOL_Pen")
        self.assertEqual(engine.active_tool, ToolType.PEN)

        # Test clicking Redo button
        redo_btn = next(b for b in ui.buttons if b.btn_id == "act_redo")
        action = ui.check_interaction((redo_btn.x + 5, redo_btn.y + 5), is_pinching=True, canvas_engine=engine)
        self.assertEqual(action, "REDO")

    def test_07_export_png_and_pdf(self):
        """Validates saving note to PNG and exporting to PDF document."""
        exporter = Exporter(output_dir=self.test_dir)
        engine = CanvasEngine(self.width, self.height)

        engine.set_tool(ToolType.PEN)
        engine.process_point((100, 100), "DRAW")
        engine.process_point((400, 400), "DRAW")
        engine.finish_stroke()

        export_img = engine.get_clean_export_image(CanvasMode.WHITEBOARD)

        ok_png, path_png = exporter.save_image(export_img, format="png")
        self.assertTrue(ok_png)
        self.assertIsNotNone(path_png)
        self.assertTrue(os.path.exists(path_png))
        self.assertGreater(os.path.getsize(path_png), 1000)

        ok_pdf, path_pdf = exporter.save_pdf(export_img)
        self.assertTrue(ok_pdf)
        self.assertIsNotNone(path_pdf)
        self.assertTrue(os.path.exists(path_pdf))
        self.assertGreater(os.path.getsize(path_pdf), 1000)

    def test_08_smart_shape_snapping(self):
        """Validates that by default freehand writing is preserved without unwanted snapping."""
        engine = CanvasEngine(self.width, self.height)
        self.assertFalse(engine.auto_shape_snap, "Auto-shape snapping should be disabled by default")
        engine.set_tool(ToolType.PEN)

        # Simulate writing a letter with a rough circular loop
        center_x, center_y, radius = 300, 300, 60
        for angle_deg in range(0, 360, 15):
            rad = np.radians(angle_deg)
            px = int(center_x + radius * np.cos(rad) + np.random.randint(-2, 2))
            py = int(center_y + radius * np.sin(rad) + np.random.randint(-2, 2))
            engine.process_point((px, py), "DRAW")
        engine.process_point((center_x + radius, center_y), "DRAW")
        engine.finish_stroke()

        self.assertIsNone(engine.last_snapped_shape, "Freehand writing should not be auto-snapped into shapes")

    def test_09_presenter_laser_and_spotlight(self):
        """Validates presenter tools (Laser pointer trail and Spotlight aperture)."""
        engine = CanvasEngine(self.width, self.height)

        # Test Laser
        engine.set_tool(ToolType.LASER)
        engine.process_point((200, 200), "DRAW")
        engine.process_point((220, 220), "DRAW")
        self.assertGreaterEqual(len(engine.laser_points), 2)

        dummy_frame = np.full((self.height, self.width, 3), 100, dtype=np.uint8)
        laser_rendered = engine.render_laser(dummy_frame.copy())
        self.assertEqual(laser_rendered.shape, dummy_frame.shape)

        # Test Spotlight
        engine.set_tool(ToolType.SPOTLIGHT)
        spot_rendered = engine.render_spotlight(dummy_frame.copy(), (300, 300))
        self.assertEqual(spot_rendered.shape, dummy_frame.shape)
        # Inside spotlight should be brighter than the dimmed outer region
        self.assertGreater(spot_rendered[300, 300, 0], spot_rendered[50, 50, 0])

    def test_10_alive_doodle_bring_to_life(self):
        """Validates drawing a doodle, bringing it alive, updating motion, and freezing."""
        engine = CanvasEngine(self.width, self.height)
        engine.set_tool(ToolType.PEN)

        # Draw a doodle (e.g. fish shape)
        for x in range(200, 300, 5):
            engine.process_point((x, 250), "DRAW")
        engine.finish_stroke()

        self.assertEqual(len(engine.alive_doodles), 0)

        # Bring to life!
        ok, msg = engine.animate_last_drawing()
        self.assertTrue(ok, "Doodle should successfully come alive")
        self.assertEqual(len(engine.alive_doodles), 1)

        doodle = engine.alive_doodles[0]
        initial_x = doodle.x

        # Update motion
        engine.update_alive_doodles(hand_pt=(400, 250), gesture="SELECT")
        self.assertNotEqual(doodle.x, initial_x, "Living doodle should move via kinematics")

        # Test rendering
        dummy_frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        rendered = engine.render_alive_doodles(dummy_frame)
        self.assertEqual(rendered.shape, dummy_frame.shape)

        # Freeze back to canvas
        freeze_ok = engine.freeze_alive_doodles()
        self.assertTrue(freeze_ok)
        self.assertEqual(len(engine.alive_doodles), 0)
        self.assertGreater(np.count_nonzero(engine.canvas[:, :, 3]), 0, "Frozen doodle should be baked onto canvas")


if __name__ == "__main__":
    unittest.main()
