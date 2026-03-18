import tempfile
import unittest
from pathlib import Path

from gst_hsn_tool.learning import LearningMemory, import_learning_file


class TestLearningMemory(unittest.TestCase):
    def test_upsert_and_exact_lookup(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "learned.csv"
            memory = LearningMemory(db_path)

            count = memory.upsert_many(
                [
                    {
                        "input_description_norm": "camlin ink blue",
                        "input_category_norm": "",
                        "input_client_hsn_norm": "",
                        "resolved_hsn8": "32159020",
                        "resolved_description": "INK",
                        "resolved_category": "chapter_32",
                        "resolved_rate": "",
                        "match_type": "keyword_hint",
                        "score": 81,
                    }
                ]
            )
            self.assertEqual(count, 1)

            reloaded = LearningMemory(db_path)
            hit = reloaded.lookup_exact("camlin ink blue", "", "")
            self.assertIsNotNone(hit)
            self.assertEqual(hit.resolved_hsn8, "32159020")

    def test_fuzzy_lookup(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "learned.csv"
            memory = LearningMemory(db_path)
            memory.upsert_many(
                [
                    {
                        "input_description_norm": "cadbury dairy milk chocolate",
                        "input_category_norm": "",
                        "input_client_hsn_norm": "",
                        "resolved_hsn8": "18069010",
                        "resolved_description": "CHOCOLATE",
                        "resolved_category": "chapter_18",
                        "resolved_rate": "",
                        "match_type": "keyword_hint",
                        "score": 82,
                    }
                ]
            )

            reloaded = LearningMemory(db_path)
            hit = reloaded.lookup_fuzzy("cadbury dairy milk choco", "")
            self.assertIsNotNone(hit)
            self.assertEqual(hit.resolved_hsn8, "18069010")

    def test_import_learning_file_with_custom_headers(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "train.csv"
            source.write_text(
                "Si No,Product,Category,HSN Code\n"
                "1,DATHRI DHEEDHI SHAMPOO 250ML,personal care,3305\n"
                "2,CAMLIN P.M INK BLACK RS 25,stationery,3215\n",
                encoding="utf-8",
            )
            db = root / "learned.csv"

            result = import_learning_file(
                file_path=source,
                memory_csv_path=db,
                product_header="Product",
                category_header="Category",
                hsn_header="HSN Code",
            )

            self.assertEqual(result["total_rows"], 2)
            self.assertEqual(result["usable_rows"], 2)
            self.assertGreaterEqual(result["saved_rows"], 2)

            mem = LearningMemory(db)
            hit = mem.lookup_exact("dathri dheedhi shampoo 250ml", "personal care", "")
            self.assertIsNotNone(hit)
            self.assertEqual(hit.resolved_hsn8, "3305")


if __name__ == "__main__":
    unittest.main()
