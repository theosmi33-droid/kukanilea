"""
license_server/server.py
Zentraler Lizenz-Server (läuft auf dem Master-NAS/ZimaBlade).
Liest dynamisch die licenses.xlsx und antwortet auf Validierungs-Pings der Kunden.
"""
from flask import Flask, request, jsonify
import pandas as pd
import os
import datetime

app = Flask(__name__)
EXCEL_PATH = os.path.join(os.path.dirname(__file__), "licenses.xlsx")

@app.route("/api/v1/license/validate", methods=["POST"])
def validate_license():
    payload = request.get_json() or {}
    hwid = payload.get("hardware_id")
    
    if not hwid:
        return jsonify({"valid": False, "reason": "Hardware ID missing"}), 400
        
    try:
        # Lese das Excel bei jedem Request neu ein (so sind Änderungen sofort wirksam!)
        df = pd.read_excel(EXCEL_PATH)
        df['HardwareID'] = df['HardwareID'].astype(str)
        
        customer = df[df['HardwareID'] == str(hwid)]
        
        if customer.empty:
            return jsonify({"valid": False, "reason": "Hardware ID not registered"}), 403
            
        row = customer.iloc[0]
        
        if not bool(row.get('IsActive', False)):
            return jsonify({"valid": False, "reason": "License explicitly revoked"}), 403
            
        valid_until = pd.to_datetime(row.get('ValidUntil'))
        if pd.notna(valid_until) and valid_until < datetime.datetime.now():
            return jsonify({"valid": False, "reason": "License expired"}), 403
            
        return jsonify({
            "valid": True,
            "plan": str(row.get('Plan', 'GOLD')),
            "customer": str(row.get('CustomerName', 'Unknown'))
        }), 200
        
    except Exception as e:
        app.logger.error(f"Excel read error: {e}")
        return jsonify({"valid": False, "reason": f"Server error"}), 500

if __name__ == "__main__":
    print("🚀 Starte zentralen Excel-Lizenzserver auf Port 9090...")
    app.run(host="0.0.0.0", port=9090)
