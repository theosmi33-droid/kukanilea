import unittest
from unittest.mock import patch

from app.autonomy.ocr import resolve_tesseract_path


class TestOCRAutonomy(unittest.TestCase):
    @patch("shutil.which")
    def test_tesseract_found(self, mock_which):
        mock_which.return_value = "/usr/bin/tesseract"
        path = resolve_tesseract_path()
        assert path == "/usr/bin/tesseract"
        mock_which.assert_called_with("tesseract")

    @patch("shutil.which")
    def test_tesseract_not_found(self, mock_which):
        mock_which.return_value = None
        path = resolve_tesseract_path()
        assert path is None
        mock_which.assert_called_with("tesseract")


if __name__ == "__main__":
    unittest.main()
