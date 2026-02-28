"""
app/agents/supervisor.py
Agent crash recovery and health monitoring with Exponential Backoff.
"""
import logging
import time
import threading
from typing import Dict, Any

logger = logging.getLogger("kukanilea.agent_supervisor")

class AgentSupervisor:
    def __init__(self):
        self.monitored_agents: Dict[str, Dict[str, Any]] = {}
        self._stop_event = threading.Event()
        self._thread = None

    def register_agent(self, agent_id: str, start_func):
        self.monitored_agents[agent_id] = {
            "start_func": start_func,
            "status": "STOPPED",
            "last_heartbeat": 0,
            "fail_count": 0,
            "next_retry": 0
        }

    def heartbeat(self, agent_id: str):
        if agent_id in self.monitored_agents:
            self.monitored_agents[agent_id]["last_heartbeat"] = time.time()
            self.monitored_agents[agent_id]["status"] = "RUNNING"
            self.monitored_agents[agent_id]["fail_count"] = 0 # Reset on success

    def start(self):
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True, name="AgentSupervisor")
        self._thread.start()
        logger.info("Agent Supervisor started.")

    def stop(self):
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2.0)

    def _monitor_loop(self):
        while not self._stop_event.is_set():
            now = time.time()
            for agent_id, data in self.monitored_agents.items():
                if data["status"] == "RUNNING" and (now - data["last_heartbeat"] > 60):
                    logger.warning(f"Agent {agent_id} unresponsive.")
                    self._handle_failure(agent_id, data)
                
                elif data["status"] == "ERROR" and (now >= data["next_retry"]):
                    logger.info(f"Attempting scheduled restart for agent {agent_id}.")
                    self._attempt_start(agent_id, data)
                    
            self._stop_event.wait(15)

    def _handle_failure(self, agent_id: str, data: Dict[str, Any]):
        data["fail_count"] += 1
        data["status"] = "ERROR"
        # Exponential backoff: 30s, 60s, 120s, ... up to 1 hour
        wait_time = min(3600, 30 * (2 ** (data["fail_count"] - 1)))
        data["next_retry"] = time.time() + wait_time
        logger.error(f"Agent {agent_id} failed. Retry #{data['fail_count']} in {wait_time}s.")

    def _attempt_start(self, agent_id: str, data: Dict[str, Any]):
        try:
            data["start_func"]()
            data["last_heartbeat"] = time.time()
            data["status"] = "RUNNING"
            logger.info(f"Agent {agent_id} restarted successfully.")
        except Exception as e:
            logger.error(f"Failed to restart agent {agent_id}: {e}")
            self._handle_failure(agent_id, data)

supervisor = AgentSupervisor()
