import csv
import tempfile
import unittest
from pathlib import Path

from gst_hsn_tool.training import (
    _build_practice_file,
    _compose_google_queries,
    backup_training_state,
    restore_training_state,
)


class TestTraining(unittest.TestCase):
    def test_compose_google_queries_includes_product_templates(self):
        queries = _compose_google_queries(
            base_queries=["gst hsn code list india"],
            product_names=["cabdury silk"],
        )
        self.assertIn("gst hsn code list india", queries)
        self.assertIn("cabdury silk 8 digit hsn code category", queries)
        self.assertIn("cabdury silk gst hsn code 8 digit", queries)

    def test_build_practice_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            master = tmp_path / "master.csv"
            with master.open("w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=["hsn8", "description", "category", "rate", "aliases"])
                w.writeheader()
                w.writerow(
                    {
                        "hsn8": "33051010",
                        "description": "Shampoo preparations",
                        "category": "chapter_33",
                        "rate": "",
                        "aliases": "",
                    }
                )

            out_csv = tmp_path / "practice.csv"
            path, rows = _build_practice_file(master, out_csv, max_rows=10)
            self.assertTrue(path.exists())
            self.assertGreaterEqual(rows, 1)

    def test_backup_and_restore(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_dir = root / "data"
            data_dir.mkdir(parents=True, exist_ok=True)

            learned = data_dir / "learned_mappings.csv"
            learned.write_text(
                "input_description_norm,input_category_norm,input_client_hsn_norm,resolved_hsn8,resolved_description,resolved_category,resolved_rate,match_type,score,learned_date,use_count\n"
                "shampoo,, ,33051010,Shampoo,chapter_33,,manual,80,2026-01-01T00:00:00,1\n",
                encoding="utf-8",
            )

            training_file = data_dir / "training" / "practice" / "p.csv"
            training_file.parent.mkdir(parents=True, exist_ok=True)
            training_file.write_text("x\n", encoding="utf-8")

            backup_path = root / "backup.zip"

            # Temporarily switch cwd so relative data paths used by backup/restore point to temp folder.
            old_cwd = Path.cwd()
            try:
                import os

                os.chdir(root)
                out = backup_training_state(backup_path)
                self.assertTrue(out.exists())

                learned.unlink()
                training_file.unlink()

                result = restore_training_state(backup_path)
                self.assertGreaterEqual(result["files_restored"], 2)
                self.assertTrue(learned.exists())
            finally:
                import os

                os.chdir(old_cwd)


if __name__ == "__main__":
    unittest.main()
