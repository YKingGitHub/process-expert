import importlib.util
import tempfile
import unittest
from pathlib import Path

from cad_executor import UnsafeCadCode, execute_to_step, validate_source
from view_agent import build_messages, extract_python, repair_prompt


class ViewAgentTest(unittest.TestCase):
    def test_extract_python_fence(self):
        self.assertEqual(extract_python("```python\nsolid = 1\n```"), "solid = 1\n")

    def test_extract_plain_python(self):
        self.assertEqual(extract_python("solid = 1"), "solid = 1\n")

    def test_extract_unclosed_python_fence(self):
        self.assertEqual(extract_python("```python\nsolid = 1"), "solid = 1\n")

    def test_repair_prompt_includes_failure_and_code(self):
        prompt = repair_prompt("solid = broken", {"error": "name not defined"})
        self.assertIn("solid = broken", prompt)
        self.assertIn("name not defined", prompt)

    def test_multi_sheet_message_keeps_all_images_before_prompt(self):
        messages = build_messages([Path("sheet-1.png"), Path("sheet-2.png")], "prompt")
        content = messages[0]["content"]
        self.assertEqual([item["type"] for item in content], ["image", "image", "text"])
        self.assertEqual(content[1]["image"], "sheet-2.png")

    def test_multi_sheet_message_rejects_empty_input(self):
        with self.assertRaises(ValueError):
            build_messages([], "prompt")

    def test_executor_accepts_typical_cadquery(self):
        validate_source(
            "import cadquery as cq\n"
            "solid = cq.Workplane('XY').box(10, 20, 3)\n"
        )

    def test_executor_rejects_unsafe_code(self):
        samples = [
            "import os\nsolid = None\n",
            "open('/tmp/x', 'w')\nsolid = None\n",
            "import subprocess\nsolid = None\n",
            "import cadquery as cq\nsolid = cq.importers.importStep('/tmp/x.step')\n",
            "import cadquery as cq\nsolid = cq.Workplane('XY'); solid.exportStl('/tmp/x.stl')\n",
            "solid = (1).__class__\n",
        ]
        for source in samples:
            with self.subTest(source=source):
                with self.assertRaises(UnsafeCadCode):
                    validate_source(source)

    @unittest.skipUnless(importlib.util.find_spec("cadquery"), "cadquery not installed")
    def test_executor_exports_expected_box(self):
        import cadquery as cq

        with tempfile.TemporaryDirectory() as directory:
            step_path = Path(directory) / "box.step"
            execute_to_step(
                "import cadquery as cq\n"
                "solid = cq.Workplane('XY').box(10, 20, 3)\n",
                step_path,
            )
            solid = cq.importers.importStep(str(step_path)).val()
            self.assertAlmostEqual(solid.Volume(), 600.0, places=6)


if __name__ == "__main__":
    unittest.main()
