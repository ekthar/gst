import unittest

from gst_hsn_tool.web_collector import _extract_google_result_links


class TestWebCollector(unittest.TestCase):
    def test_extract_google_result_links(self):
        sample = '''
        <html><body>
          <a href="/url?q=https://cbic-gst.gov.in/hsn-codes&amp;sa=U&amp;ved=2ah">CBIC</a>
          <a href="/url?q=https://services.gst.gov.in/services/searchhsnsac&amp;sa=U&amp;ved=2ah">GST</a>
          <a href="https://www.google.com/preferences">Prefs</a>
        </body></html>
        '''

        links = _extract_google_result_links(sample)
        self.assertIn("https://cbic-gst.gov.in/hsn-codes", links)
        self.assertIn("https://services.gst.gov.in/services/searchhsnsac", links)
        self.assertTrue(all("google." not in link for link in links))

    def test_extract_google_result_links_with_absolute_google_redirect(self):
        sample = '''
        <html><body>
          <a href="https://www.google.com/url?url=https%3A%2F%2Fcbic-gst.gov.in%2Fhsn-codes&amp;sa=t">CBIC</a>
        </body></html>
        '''

        links = _extract_google_result_links(sample)
        self.assertIn("https://cbic-gst.gov.in/hsn-codes", links)


if __name__ == "__main__":
    unittest.main()
