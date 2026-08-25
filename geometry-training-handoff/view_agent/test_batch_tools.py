import unittest

from batch_view_agent import assert_input_only
from evaluate_batch import describe, percent_error
from prepare_batch import decoded_zip_name


class BatchToolsTest(unittest.TestCase):
    def test_inference_manifest_rejects_ground_truth(self):
        with self.assertRaises(ValueError):
            assert_input_only({"samples": [{"ground_truth_step": "/tmp/truth.step"}]})

    def test_inference_manifest_accepts_images(self):
        assert_input_only({"samples": [{"images": ["a.png", "b.png"]}]})

    def test_percent_error_is_signed(self):
        self.assertAlmostEqual(percent_error(110.0, 100.0), 10.0)
        self.assertAlmostEqual(percent_error(90.0, 100.0), -10.0)

    def test_describe(self):
        self.assertEqual(describe([1.0, 2.0, 3.0])["median"], 2.0)

    def test_repairs_utf8_zip_name(self):
        mojibake = "图纸".encode("utf-8").decode("cp437")
        self.assertEqual(decoded_zip_name(mojibake), "图纸")


if __name__ == "__main__":
    unittest.main()
