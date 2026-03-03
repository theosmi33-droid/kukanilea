"""
app/core/auto_evolution.py
KUKANILEA v2.5 Self-Healing & Auto-Evolution Engine.
Handles Task 201-210: Detecting system decay and applying autonomous patches.
"""

import os
import logging
import sqlite3
import subprocess
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any

logger = logging.getLogger("kukanilea.healer")

class SystemHealer:
    def __init__(self, db_path: Path, repo_root: Path):
        self.db_path = db_path
        self.repo_root = repo_root

    def run_healing_cycle(self):
        """Main loop for forensic repair."""
        logger.info("Starting Auto-Evolution Healing Cycle...")
        
        # 1. Database Optimization (Step 184)
        self.optimize_database()
        
        # 2. Forensic Consistency Check
        self.verify_file_system_sync()
        
        # 3. Auto-Repair Registry (Mock implementation of common fixes)
        self.apply_hotfixes()
        
        # 4. Task 105: Indexing Worker (Plugin-style)
        self.run_indexing_worker()

    def run_indexing_worker(self):
        """Task 105: Background Indexing & Phase 2: Index Optimization."""
        logger.info("Indexing Worker (Task 105) started...")
        
        from app.core.indexing_logic import IndividualIntelligence
        intel = IndividualIntelligence(self.db_path)
        
        # Phase 2: Optimize FTS
        intel.optimize_index()
        
        # Simulation: Re-calculating keyword weights in docs_index
        try:
            conn = sqlite3.connect(str(self.db_path))
            # Mock indexing logic: update 'updated_at' for all docs
            conn.execute("UPDATE docs_index SET updated_at = ? WHERE updated_at IS NULL", (datetime.now().isoformat(),))
            conn.commit()
            conn.close()
            logger.info("Indexing complete.")
        except Exception as e:
            logger.error(f"Indexing failed: {e}")

    def optimize_database(self):
        """Task 184: Weekly VACUUM and performance tuning."""
        try:
            conn = sqlite3.connect(str(self.db_path))
            conn.execute("PRAGMA optimize;")
            conn.execute("ANALYZE;")
            conn.execute("VACUUM;")
            logger.info("Database vacuumed and optimized.")
            conn.close()
        except Exception as e:
            logger.error(f"DB Optimization failed: {e}")

    def verify_file_system_sync(self):
        """Ensures all docs in DB exist on disk (Forensic Reliability)."""
        logger.info("Verifying file system sync...")
        try:
            conn = sqlite3.connect(str(self.db_path))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("SELECT doc_id, object_folder, tenant_id FROM docs")
            rows = cursor.fetchall()
            
            # Find base path: /Users/gensuminguyen/Kukanilea/data/Kukanilea_Kundenablage
            base_path = self.repo_root.parent.parent / "data" / "Kukanilea_Kundenablage"
            if not base_path.exists():
                # Fallback for unconventional setups
                base_path = Path("/Users/gensuminguyen/Kukanilea/data/Kukanilea_Kundenablage")
                
            if not base_path.exists():
                logger.error(f"Vault base path not found: {base_path}")
                conn.close()
                return

            missing_count = 0
            checked_count = 0
            for row in rows:
                doc_id = row['doc_id']
                folder = row['object_folder']
                tenant = row['tenant_id'] or "kukanilea"
                
                if not folder:
                    continue

                checked_count += 1
                tenant_dir = base_path / tenant.lower()
                folder_dir = tenant_dir / folder
                
                if not folder_dir.exists():
                    missing_count += 1
                    logger.warning(f"Forensic Alert: Missing folder {folder_dir} for doc {doc_id}")
                    continue
                    
                # Look for any file starting with doc_id
                matches = list(folder_dir.glob(f"{doc_id}*"))
                if not matches:
                    missing_count += 1
                    logger.warning(f"Forensic Alert: Missing file {doc_id} in {folder_dir}")
            
            conn.close()
            if missing_count > 0:
                logger.error(f"Sync check failed: {missing_count}/{checked_count} issues found.")
            else:
                logger.info(f"File system sync verified successfully ({checked_count} docs).")
                
        except Exception as e:
            logger.error(f"Verify sync failed: {e}")

    def apply_hotfixes(self):
        """Task 202: Apply known patches for common environment issues."""
        # Example: Ensure certain directories exist
        required_dirs = ["logs/crash", "vault", "trash", "instance/backups"]
        for d in required_dirs:
            (self.repo_root / d).mkdir(parents=True, exist_ok=True)

    def evolution_step(self):
        """Self-optimization: Adjust system threads based on performance_report.json."""
        report_path = self.repo_root / "logs/reports/performance_report.json"
        if report_path.exists():
            import json
            with open(report_path, "r") as f:
                data = json.load(f)
            
            # If boot time is too high, suggest/apply thread scaling (Task 185)
            if data.get("boot_time_ms", 0) > 1000:
                logger.warning("System evolution: High boot time detected. Scaling worker threads.")
                # Logic to update config.py or env variables
