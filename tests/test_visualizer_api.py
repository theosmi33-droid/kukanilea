import base64
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from flask import Flask

mock_login_required = lambda x: x
with patch('app.auth.login_required', mock_login_required):
    from app.routes import visualizer


class TestVisualizerAPI(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.register_blueprint(visualizer.bp)
        self.client = self.app.test_client()
        self.tempdir = tempfile.TemporaryDirectory()
        self.file_path = Path(self.tempdir.name) / "demo.csv"
        self.file_path.write_text("name,value\nA,12\nB,7\n", encoding="utf-8")
        self.source = base64.b64encode(str(self.file_path).encode("utf-8")).decode("ascii")

    def tearDown(self):
        self.tempdir.cleanup()

    @patch('app.routes.visualizer._is_allowed_path', return_value=True)
    @patch('app.routes.visualizer.build_visualizer_payload')
    def test_summary_endpoint_returns_heuristic_text(self, mock_build, _mock_allowed):
        mock_build.return_value = {
            "kind": "sheet",
            "sheet": {"rows": 2, "cols": 2},
            "file": {"name": "demo.csv"},
        }

        response = self.client.post(
            '/api/visualizer/summary',
            json={'source': self.source, 'page': 0, 'sheet': '', 'force_ocr': False},
        )

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIn('summary', data)
        self.assertEqual(data['model'], 'heuristic')
        self.assertEqual(data['source']['kind'], 'sheet')

    def test_aux_endpoints_exist_without_404(self):
        projects = self.client.get('/api/visualizer/projects')
        self.assertEqual(projects.status_code, 200)

        note_missing = self.client.post('/api/visualizer/note', json={})
        self.assertEqual(note_missing.status_code, 400)

        export = self.client.post('/api/visualizer/export-pdf', json={})
        self.assertEqual(export.status_code, 501)


if __name__ == '__main__':
    unittest.main()
