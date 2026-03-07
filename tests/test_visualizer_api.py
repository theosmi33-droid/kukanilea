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

    @patch('app.routes.visualizer._is_allowed_path', return_value=True)
    @patch('app.routes.visualizer.build_visualizer_payload')
    def test_summary_endpoint_includes_excel_analyzer(self, mock_build, _mock_allowed):
        mock_build.return_value = {
            "kind": "sheet",
            "sheet": {"rows": 2, "cols": 2},
            "file": {"name": "demo.csv"},
        }

        response = self.client.post('/api/visualizer/summary', json={'source': self.source})
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIn('excel_summary', data)
        self.assertEqual(data['excel_summary']['columns'], 2)


    @patch('app.routes.visualizer.current_tenant', return_value='tenant-x')
    @patch('app.routes.visualizer._collect_visualizer_items')
    def test_sources_endpoint_returns_items_and_count(self, mock_collect, _mock_tenant):
        mock_collect.return_value = [{"id": "abc", "name": "demo.csv", "ext": ".csv", "size": 10, "source": "pending"}]

        response = self.client.get('/api/visualizer/sources')
        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertEqual(body['count'], 1)
        self.assertEqual(len(body['items']), 1)

    @patch('app.routes.visualizer._is_allowed_path', return_value=True)
    @patch('app.routes.visualizer.build_visualizer_payload', None)
    def test_summary_endpoint_degrades_when_backend_missing(self, _mock_allowed):
        response = self.client.post('/api/visualizer/summary', json={'source': self.source})
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.get_json()['error'], 'visualizer_logic_missing')

    @patch('app.routes.visualizer.current_tenant', return_value='tenant-x')
    def test_markup_endpoints_persist_json_document(self, _mock_tenant):
        self.app.instance_path = self.tempdir.name
        created = self.client.post('/api/visualizer/markup', json={
            'project_id': 'proj-1',
            'source': 'demo-source',
            'page': 0,
            'x': 12,
            'y': 34,
            'note': 'hello',
            'highlight': {'x': 10, 'y': 30, 'width': 40, 'height': 10}
        })
        self.assertEqual(created.status_code, 200)
        payload = created.get_json()
        self.assertTrue(payload['ok'])

        fetched = self.client.get('/api/visualizer/markup?project_id=proj-1')
        self.assertEqual(fetched.status_code, 200)
        doc = fetched.get_json()['markup']
        self.assertEqual(len(doc['anchors']), 1)
        self.assertEqual(len(doc['notes']), 1)
        self.assertEqual(len(doc['highlights']), 1)

    def test_aux_endpoints_exist_without_404(self):
        projects = self.client.get('/api/visualizer/projects')
        self.assertEqual(projects.status_code, 200)

        note_missing = self.client.post('/api/visualizer/note', json={})
        self.assertEqual(note_missing.status_code, 400)

        export = self.client.post('/api/visualizer/export-pdf', json={})
        self.assertEqual(export.status_code, 501)


if __name__ == '__main__':
    unittest.main()
