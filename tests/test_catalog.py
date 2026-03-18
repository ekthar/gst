import unittest

from gst_hsn_tool.catalog import transform_hsn_rows


class TestCatalog(unittest.TestCase):
    def test_transform_hsn_rows_keeps_only_8_digit(self):
        rows = [
            ("01", "LIVE ANIMALS"),
            ("0101", "LIVE HORSES"),
            ("01011010", "HORSES FOR BREEDING"),
            ("01011020", "ASSES FOR BREEDING"),
        ]

        out = transform_hsn_rows(rows)
        self.assertEqual(len(out), 2)
        self.assertEqual(out[0]["hsn8"], "01011010")
        self.assertEqual(out[1]["hsn8"], "01011020")

    def test_transform_hsn_rows_deduplicates(self):
        rows = [
            ("01011010", "DESC A"),
            ("01011010", "DESC B"),
        ]

        out = transform_hsn_rows(rows)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["description"], "DESC A")


if __name__ == "__main__":
    unittest.main()
