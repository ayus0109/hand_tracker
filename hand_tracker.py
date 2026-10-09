"""
Hand tracking module using MediaPipe Tasks HandLandmarker.
Provides real-time hand landmark detection, adaptive jitter filtering,
finger status detection, and gesture classification.
"""

import math
import os
import urllib.request
import cv2
import numpy as np
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

import config


class HandTracker:
    """Detects hand landmarks and classifies gestures in real-time."""

    # Landmark indices for readability
    WRIST = 0
    THUMB_CMC = 1
    THUMB_MCP = 2
    THUMB_IP = 3
    THUMB_TIP = 4

    INDEX_MCP = 5
    INDEX_PIP = 6
    INDEX_DIP = 7
    INDEX_TIP = 8

    MIDDLE_MCP = 9
    MIDDLE_PIP = 10
    MIDDLE_DIP = 11
    MIDDLE_TIP = 12

    RING_MCP = 13
    RING_PIP = 14
    RING_DIP = 15
    RING_TIP = 16

    PINKY_MCP = 17
    PINKY_PIP = 18
    PINKY_DIP = 19
    PINKY_TIP = 20

    # Skeleton connection pairs for drawing
    CONNECTIONS = [
        # Thumb
        (0, 1), (1, 2), (2, 3), (3, 4),
        # Index
        (0, 5), (5, 6), (6, 7), (7, 8),
        # Middle
        (5, 9), (9, 10), (10, 11), (11, 12),
        # Ring
        (9, 13), (13, 14), (14, 15), (15, 16),
        # Pinky
        (13, 17), (17, 18), (18, 19), (19, 20),
        # Palm base
        (0, 17)
    ]

    def __init__(self, model_path=config.MODEL_PATH, num_hands=1, min_detection_confidence=0.7):
        self.model_path = model_path
        self._ensure_model_exists()

        base_options = python.BaseOptions(model_asset_path=self.model_path)
        options = vision.HandLandmarkerOptions(
            base_options=base_options,
            running_mode=vision.RunningMode.IMAGE,
            num_hands=num_hands,
            min_hand_detection_confidence=min_detection_confidence,
            min_hand_presence_confidence=min_detection_confidence,
            min_tracking_confidence=min_detection_confidence
        )
        self.detector = vision.HandLandmarker.create_from_options(options)

        # Smoothed coordinates for index finger tip
        self.smooth_index_tip = None
        self.prev_raw_index = None
        self.pinch_to_draw = config.PINCH_TO_DRAW_DEFAULT
        self.z_touch_enabled = False

    def _ensure_model_exists(self):
        """Downloads the model task file if not already present."""
        if not os.path.exists(self.model_path):
            os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
            url = "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=30) as response, open(self.model_path, "wb") as out_file:
                out_file.write(response.read())

    def find_hands(self, frame_bgr):
        """
        Processes a BGR frame and returns landmark coordinates and gesture data.
        Returns:
            dict containing:
                - 'detected': bool
                - 'landmarks': list of (x, y, z) in pixel coords (or None)
                - 'norm_landmarks': list of normalized landmarks
                - 'fingers_up': [thumb, index, middle, ring, pinky] as bools
                - 'gesture': 'DRAW', 'SELECT', 'ERASER', 'PINCH', 'FIST', 'HOVER', or 'NONE'
                - 'index_tip': (x, y) smoothed coordinates
                - 'thumb_tip': (x, y) coordinates
                - 'pinch_distance': float
                - 'z_depth': float (index tip relative to knuckle)
                - 'is_z_touching': bool
                - 'pinch_to_draw': bool
                - 'handedness': 'Left' or 'Right' (mirrored)
        """
        h, w, _ = frame_bgr.shape
        frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame_rgb)

        result = self.detector.detect(mp_image)

        if not result.hand_landmarks or len(result.hand_landmarks) == 0:
            self.smooth_index_tip = None
            return {
                "detected": False,
                "landmarks": None,
                "norm_landmarks": None,
                "fingers_up": [False, False, False, False, False],
                "gesture": "NONE",
                "index_tip": None,
                "thumb_tip": None,
                "pinch_distance": 9999.0,
                "z_depth": 0.0,
                "is_z_touching": False,
                "pinch_to_draw": self.pinch_to_draw,
                "handedness": "Unknown"
            }

        # Take the primary hand detected
        hand_lms = result.hand_landmarks[0]
        handedness = "Right"
        if result.handedness and len(result.handedness) > 0:
            # MediaPipe handedness is for un-mirrored feed
            handedness = result.handedness[0][0].category_name

        # Convert to pixel space
        landmarks = []
        for lm in hand_lms:
            px = int(lm.x * w)
            py = int(lm.y * h)
            pz = lm.z * w
            landmarks.append((px, py, pz))

        # Determine which fingers are extended
        fingers_up = self._get_fingers_up(landmarks, hand_lms)

        # Raw tip positions
        raw_index_tip = (landmarks[self.INDEX_TIP][0], landmarks[self.INDEX_TIP][1])
        thumb_tip = (landmarks[self.THUMB_TIP][0], landmarks[self.THUMB_TIP][1])

        # Calculate distance between index tip and thumb tip (pinch distance)
        pinch_dist = math.hypot(raw_index_tip[0] - thumb_tip[0], raw_index_tip[1] - thumb_tip[1])

        # Calculate 3D Z-depth relative to MCP knuckle
        z_tip = hand_lms[self.INDEX_TIP].z
        z_mcp = hand_lms[self.INDEX_MCP].z
        delta_z = z_tip - z_mcp
        is_z_touching = delta_z <= config.Z_TOUCH_DELTA_THRESHOLD

        # Smooth index tip coordinates using adaptive EMA
        is_drawing_gesture = fingers_up[1] and not fingers_up[2]
        smooth_tip = self._smooth_coordinates(raw_index_tip, is_drawing_gesture)

        # Classify gesture with ergonomics support
        gesture = self._classify_gesture(fingers_up, pinch_dist, is_z_touching)

        return {
            "detected": True,
            "landmarks": landmarks,
            "norm_landmarks": hand_lms,
            "fingers_up": fingers_up,
            "gesture": gesture,
            "index_tip": smooth_tip,
            "thumb_tip": thumb_tip,
            "pinch_distance": pinch_dist,
            "z_depth": delta_z,
            "is_z_touching": is_z_touching,
            "pinch_to_draw": self.pinch_to_draw,
            "handedness": handedness
        }

    def _get_fingers_up(self, lm, norm_lm):
        """
        Determines which of the 5 fingers are currently UP/extended.
        Returns: [thumb, index, middle, ring, pinky]
        """
        fingers = [False, False, False, False, False]

        # 1. Thumb extension test:
        thumb_tip = np.array([lm[self.THUMB_TIP][0], lm[self.THUMB_TIP][1]])
        thumb_ip = np.array([lm[self.THUMB_IP][0], lm[self.THUMB_IP][1]])
        pinky_mcp = np.array([lm[self.PINKY_MCP][0], lm[self.PINKY_MCP][1]])
        wrist = np.array([lm[self.WRIST][0], lm[self.WRIST][1]])

        dist_tip_pinky = np.linalg.norm(thumb_tip - pinky_mcp)
        dist_ip_pinky = np.linalg.norm(thumb_ip - pinky_mcp)
        dist_tip_wrist = np.linalg.norm(thumb_tip - wrist)
        dist_mcp_wrist = np.linalg.norm(np.array([lm[self.THUMB_MCP][0], lm[self.THUMB_MCP][1]]) - wrist)

        if dist_tip_pinky > dist_ip_pinky * 1.15 and dist_tip_wrist > dist_mcp_wrist * 1.1:
            fingers[0] = True

        # 2. Index Finger:
        if lm[self.INDEX_TIP][1] < lm[self.INDEX_PIP][1] and lm[self.INDEX_TIP][1] < lm[self.INDEX_DIP][1]:
            fingers[1] = True

        # 3. Middle Finger:
        if lm[self.MIDDLE_TIP][1] < lm[self.MIDDLE_PIP][1] and lm[self.MIDDLE_TIP][1] < lm[self.MIDDLE_DIP][1]:
            fingers[2] = True

        # 4. Ring Finger:
        if lm[self.RING_TIP][1] < lm[self.RING_PIP][1] and lm[self.RING_TIP][1] < lm[self.RING_DIP][1]:
            fingers[3] = True

        # 5. Pinky Finger:
        if lm[self.PINKY_TIP][1] < lm[self.PINKY_PIP][1] and lm[self.PINKY_TIP][1] < lm[self.PINKY_DIP][1]:
            fingers[4] = True

        return fingers

    def _classify_gesture(self, fingers_up, pinch_dist, is_z_touching=False):
        """
        Translates finger states into high-level whiteboard gestures:
        Supports both natural index finger drawing and Apple Vision Pro pinch-to-draw.
        """
        thumb, index, middle, ring, pinky = fingers_up
        num_extended = sum(fingers_up)

        # 1. Quick Eraser: Open hand (4 or 5 fingers up) or Index+Middle+Ring up
        if num_extended >= 4 or (index and middle and ring and not pinky):
            return "ERASER"

        # 2. Pinch-to-Draw Mode (Vision Pro style)
        if self.pinch_to_draw:
            if pinch_dist < config.PINCH_THRESHOLD:
                return "DRAW"
            else:
                return "SELECT"

        # 3. Standard Pinch Click
        if pinch_dist < config.PINCH_THRESHOLD:
            return "PINCH"

        # 4. Selection / Hover: Index and Middle UP, Ring & Pinky DOWN
        if index and middle and not ring and not pinky:
            return "SELECT"

        # 5. Drawing: Only Index UP
        if index and not middle and not ring and not pinky:
            if self.z_touch_enabled:
                return "DRAW" if is_z_touching else "HOVER"
            return "DRAW"

        # 6. Fist: All down
        if num_extended == 0:
            return "FIST"

        return "NONE"

    def _smooth_coordinates(self, raw_point, is_drawing):
        """
        Applies adaptive Exponential Moving Average (EMA) to prevent hand tremor
        while maintaining zero lag during fast movement.
        """
        if self.smooth_index_tip is None:
            self.smooth_index_tip = raw_point
            return raw_point

        prev_x, prev_y = self.smooth_index_tip
        curr_x, curr_y = raw_point

        # Speed of motion
        distance = math.hypot(curr_x - prev_x, curr_y - prev_y)

        # Dynamic alpha: when moving fast, trust raw point more (responsive)
        base_alpha = config.SMOOTHING_ALPHA_DRAW if is_drawing else config.SMOOTHING_ALPHA_HOVER
        speed_boost = min(0.45, distance / 120.0)
        alpha = min(0.95, base_alpha + speed_boost)

        smooth_x = int(alpha * curr_x + (1.0 - alpha) * prev_x)
        smooth_y = int(alpha * curr_y + (1.0 - alpha) * prev_y)

        self.smooth_index_tip = (smooth_x, smooth_y)
        return (smooth_x, smooth_y)

    def draw_hand_skeleton(self, frame_bgr, landmarks, draw_color=(0, 240, 255), joint_color=(255, 255, 255)):
        """Renders an aesthetic glowing hand skeleton on the frame."""
        if not landmarks:
            return frame_bgr

        # Draw bones
        for start_idx, end_idx in self.CONNECTIONS:
            pt1 = (landmarks[start_idx][0], landmarks[start_idx][1])
            pt2 = (landmarks[end_idx][0], landmarks[end_idx][1])
            cv2.line(frame_bgr, pt1, pt2, draw_color, 2, cv2.LINE_AA)

        # Draw joints
        for i, pt in enumerate(landmarks):
            radius = 5 if i in (4, 8, 12, 16, 20) else 3
            pt_xy = (pt[0], pt[1])
            cv2.circle(frame_bgr, pt_xy, radius + 1, (20, 20, 20), -1, cv2.LINE_AA)
            cv2.circle(frame_bgr, pt_xy, radius, joint_color, -1, cv2.LINE_AA)

        return frame_bgr
