from gst_hsn_tool.matcher import resolve_row, select_primary
import unittest


class TestMatcher(unittest.TestCase):
    def test_prefix_expansion_returns_candidates(self):
        hsn_rows = [
            {
                "hsn8": "30049011",
                "description": "Paracetamol tablets",
                "category": "pharma",
                "rate": "12",
                "description_norm": "paracetamol tablets",
                "category_norm": "pharma",
                "aliases_norm": [],
                "hsn4": "3004",
                "hsn6": "300490",
            },
            {
                "hsn8": "30045010",
                "description": "Vitamin preparations",
                "category": "pharma",
                "rate": "12",
                "description_norm": "vitamin preparations",
                "category_norm": "pharma",
                "aliases_norm": [],
                "hsn4": "3004",
                "hsn6": "300450",
            },
            {
                "hsn8": "21069099",
                "description": "Nutritional supplements",
                "category": "food",
                "rate": "18",
                "description_norm": "nutritional supplements",
                "category_norm": "food",
                "aliases_norm": [],
                "hsn4": "2106",
                "hsn6": "210690",
            },
        ]

        candidates = resolve_row("", "", "3004", hsn_rows)
        self.assertGreaterEqual(len(candidates), 1)
        self.assertIn(candidates[0].hsn8, {"30049011", "30045010"})

    def test_exact_description_preferred_over_fuzzy(self):
        hsn_rows = [
            {
                "hsn8": "10063010",
                "description": "Basmati rice",
                "category": "food",
                "rate": "5",
                "description_norm": "basmati rice",
                "category_norm": "food",
                "aliases_norm": [],
                "hsn4": "1006",
                "hsn6": "100630",
            },
            {
                "hsn8": "10063090",
                "description": "Other rice",
                "category": "food",
                "rate": "5",
                "description_norm": "other rice",
                "category_norm": "food",
                "aliases_norm": [],
                "hsn4": "1006",
                "hsn6": "100630",
            },
        ]
        candidates = resolve_row("basmati rice", "food", "", hsn_rows)
        primary, _ = select_primary(candidates)

        self.assertIsNotNone(primary)
        self.assertEqual(primary.hsn8, "10063010")
        self.assertGreaterEqual(primary.score, 90)


if __name__ == "__main__":
    unittest.main()
