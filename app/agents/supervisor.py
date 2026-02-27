"""
app/agents/supervisor.py
Agent crash recovery and health monitoring.
"""
import logging
import time
import threading

logger = logging.getLogger("kukanilea.agent_supervisor")

class AgentSupervisor:
    def __init__(self):
        self.monitored_agents = {}
        self._stop_event = threading.Event()
        self._thread = None

    def register_agent(self, agent_id: str, start_func):
        self.monitored_agents[agent_id] = {
            "start_func": start_func,
            "status": "STOPPED",
            "last_heartbeat": 0
        }

    def heartbeat(self, agent_id: str):
        if agent_id in self.monitored_agents:
            self.monitored_agents[agent_id]["last_heartbeat"] = time.time()
            self.monitored_agents[agent_id]["status"] = "RUNNING"

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
                    logger.warning(f"Agent {agent_id} unresponsive. Attempting restart.")
                    data["status"] = "RESTARTING"
                    try:
                        data["start_func"]()
                        data["last_heartbeat"] = time.time()
                        data["status"] = "RUNNING"
                        logger.info(f"Agent {agent_id} restarted successfully.")
                    except Exception as e:
                        logger.error(f"Failed to restart agent {agent_id}: {e}")
                        data["status"] = "ERROR"
            self._stop_event.wait(15)

supervisor = AgentSupervisor()
