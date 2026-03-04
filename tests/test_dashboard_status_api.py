import unittest
from unittest.mock import patch, MagicMock
import sys

# Mock login_required before importing the blueprint
from flask import Flask
mock_login_required = lambda x: x
with patch('app.auth.login_required', mock_login_required):
    from app.routes.dashboard import dashboard_bp

class TestDashboardAPI(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.register_blueprint(dashboard_bp, url_prefix="/api/dashboard")
        self.client = self.app.test_client()

    @patch('app.routes.dashboard.run_vault_selftest')
    def test_vault_selftest_success(self, mock_selftest):
        mock_selftest.return_value = {
            "integrity_ok": True,
            "database_status": "ok",
            "files_verified": 5,
            "files_missing": [],
            "timestamp": "test_ts"
        }
        
        response = self.client.post('/api/dashboard/selftest')
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data['status'], 'OK')
        self.assertTrue(data['details']['integrity_ok'])

    @patch('app.routes.dashboard.run_vault_selftest')
    def test_vault_selftest_failure(self, mock_selftest):
        mock_selftest.return_value = {
            "integrity_ok": False,
            "files_missing": ["app/core/logic.py"]
        }
        
        response = self.client.post('/api/dashboard/selftest')
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data['status'], 'ERROR')

if __name__ == "__main__":
    unittest.main()
