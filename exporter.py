"""
Export engine for saving notes and sketches.
Supports high-resolution PNG, JPG, and multi-page/single-page PDF export.
"""

import os
from datetime import datetime
import cv2
from PIL import Image

import config


class Exporter:
    """Manages file storage and document export for digital whiteboard notes."""

    def __init__(self, output_dir=config.NOTES_DIR):
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)

    def _generate_filename(self, extension="png"):
        """Generates a clean timestamped filename."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"note_{timestamp}.{extension}"

    def save_image(self, bgr_image, format="png"):
        """
        Saves canvas image as PNG or JPG file.
        Returns:
            (success: bool, filepath: str or None)
        """
        try:
            filename = self._generate_filename(format.lower())
            filepath = os.path.join(self.output_dir, filename)

            if format.lower() == "png":
                # High quality PNG
                success = cv2.imwrite(filepath, bgr_image, [cv2.IMWRITE_PNG_COMPRESSION, 3])
            else:
                # High quality JPEG
                success = cv2.imwrite(filepath, bgr_image, [cv2.IMWRITE_JPEG_QUALITY, 95])

            if success:
                return True, filepath
            return False, None
        except Exception as e:
            print(f"[Exporter] Error saving image: {e}")
            return False, None

    def save_pdf(self, bgr_image):
        """
        Exports canvas image as a PDF document using Pillow.
        Returns:
            (success: bool, filepath: str or None)
        """
        try:
            filename = self._generate_filename("pdf")
            filepath = os.path.join(self.output_dir, filename)

            # Convert BGR to RGB for Pillow
            rgb_image = cv2.cvtColor(bgr_image, cv2.COLOR_BGR2RGB)
            pil_img = Image.fromarray(rgb_image)

            # Save as PDF
            pil_img.save(filepath, "PDF", resolution=150.0)
            return True, filepath
        except Exception as e:
            print(f"[Exporter] Error exporting PDF: {e}")
            return False, None
