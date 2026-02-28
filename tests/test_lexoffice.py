from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

# Ensure we can import app
sys.path.append(os.getcwd())

from flask import Flask
from app.tools.lexoffice_tool import LexofficeUploadTool
from app.config import Config

def test_lexoffice_integration():
    print("Testing KUKANILEA Lexoffice Integration (Mocked)...")
    
    # Setup Flask app for context
    app = Flask(__name__)
    app.config.from_object(Config)
    
    # 1. Setup tool and dummy file
    tool = LexofficeUploadTool()
    dummy_file = Path("test_invoice.pdf")
    dummy_file.write_bytes(b"dummy pdf content")
    
    try:
        # Mock Config and Client
        with app.app_context():
            # Mock g.tenant_id
            from flask import g
            g.tenant_id = "test_tenant"
            
            with patch.object(Config, 'LEXOFFICE_API_KEY', 'test-key-123'):
                # Mock AuthDB in app extensions
                mock_auth_db = MagicMock()
                app.extensions["auth_db"] = mock_auth_db
                
                # 2. Run tool (should now queue instead of upload)
                result = tool.run(file_path=str(dummy_file))
                
                print(f"Tool result: {result}")
                assert result["status"] == "queued"
                assert "job_id" in result
                assert "Postausgang" in result["message"]
                
                # Verify DB insert was called
                assert mock_auth_db._db.return_value.__enter__.return_value.execute.called

        # 3. Test missing config
        with app.app_context():
            with patch.object(Config, 'LEXOFFICE_API_KEY', ''):
                result = tool.run(file_path=str(dummy_file))
                assert "error" in result
                assert "nicht konfiguriert" in result["error"]

    finally:
        if dummy_file.exists():
            dummy_file.unlink()

    print("Lexoffice Integration Test: PASS")

if __name__ == "__main__":
    test_lexoffice_integration()
