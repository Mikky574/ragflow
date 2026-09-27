from PIL import Image
import unittest

from extract_regions import crop_region, overlap_ratio, unique_layouts


class ExtractRegionTests(unittest.TestCase):
    def test_overlap_ratio_uses_smallest_region(self):
        self.assertEqual(overlap_ratio((0, 0, 10, 10), (2, 2, 8, 8)), 1.0)

    def test_unique_layouts_keeps_equation_in_preference_to_same_figure(self):
        layouts = [
            {"type": "figure", "x0": 0, "top": 0, "x1": 10, "bottom": 10},
            {"type": "equation", "x0": 0, "top": 0, "x1": 10, "bottom": 10},
        ]
        self.assertEqual([item["type"] for item in unique_layouts(layouts, {"figure", "equation"})], ["equation"])

    def test_crop_region_uses_zoomed_coordinates(self):
        image = Image.new("RGB", (300, 300))
        crop = crop_region(image, (10, 20, 50, 60), zoomin=3)
        self.assertIsNotNone(crop)
        self.assertEqual(crop.size, (120, 120))
