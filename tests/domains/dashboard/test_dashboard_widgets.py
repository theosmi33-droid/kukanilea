import unittest
from unittest.mock import patch

from flask import Flask

mock_login_required = lambda x: x
with patch('app.auth.login_required', mock_login_required):
    from app.routes.dashboard import bp as dashboard_bp


class TestDashboardWidgetReliability(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__, template_folder='app/templates')
        self.app.register_blueprint(dashboard_bp)
        self.client = self.app.test_client()

    @patch('app.routes.dashboard.current_tenant', return_value='default')
    @patch('app.routes.dashboard._core_get')
    def test_dashboard_quick_action_and_reminder_anchors_exist(self, mock_core_get, _tenant):
        mock_core_get.return_value = None
        response = self.client.get('/dashboard')
        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn('id="quick-actions"', body)
        self.assertIn('id="reminders"', body)

    @patch('app.core.observer.get_system_status', side_effect=RuntimeError('boom'))
    def test_system_status_html_fallback_on_error(self, _status):
        response = self.client.get('/api/system/status', headers={'Accept': 'text/html'})
        self.assertEqual(response.status_code, 503)
        self.assertIn('Systemstatus nicht verfügbar', response.get_data(as_text=True))

    @patch('app.api.outbound_status', side_effect=RuntimeError('queue down'))
    def test_outbound_status_html_fallback_on_error(self, _outbound):
        response = self.client.get('/api/outbound/status', headers={'Accept': 'text/html'})
        self.assertEqual(response.status_code, 503)
        self.assertIn('Temporär nicht erreichbar', response.get_data(as_text=True))


if __name__ == '__main__':
    unittest.main()
