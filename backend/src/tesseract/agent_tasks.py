"""v1.1: Aufgaben für Agents (z. B. „ist das Ziel vom Node aus erreichbar?“, „welche
Zertifikate liefert dein Caddy aus?“).

Der Controller kann einen Agent nicht anrufen – der Agent holt ab. Aufgaben warten deshalb
hier, bis der Agent beim nächsten Durchlauf seines Long-Pollings (höchstens 1 s später) sie
mitnimmt, ausführt und das Ergebnis über `POST /api/agent/tasks/{id}` zurückschickt.
Alles läuft im Event-Loop des Controllers; Aufgaben leben nur im Speicher.
"""

import asyncio
import secrets
from typing import Any

from tesseract.db.models import Node

# Ab dieser Agent-Version werden Aufgaben verstanden
MIN_AGENT = (1, 1, 0)


def supports_tasks(node: Node) -> bool:
    if not node.is_agent or not node.agent_version:
        return False
    try:
        version = tuple(int(x) for x in node.agent_version.split(".")[:3])
    except ValueError:
        return False
    return version >= MIN_AGENT


class TaskBroker:
    def __init__(self) -> None:
        self.pending: dict[int, list[dict[str, Any]]] = {}
        self.futures: dict[str, asyncio.Future] = {}

    def has(self, node_id: int) -> bool:
        return bool(self.pending.get(node_id))

    def take(self, node_id: int) -> list[dict[str, Any]]:
        return self.pending.pop(node_id, [])

    def resolve(self, task_id: str, result: dict[str, Any]) -> bool:
        fut = self.futures.pop(task_id, None)
        if fut is None or fut.done():
            return False
        fut.set_result(result)
        return True

    async def run(
        self, node_id: int, kind: str, params: dict[str, Any], timeout: float = 10.0
    ) -> dict[str, Any] | None:
        """Aufgabe stellen und auf das Ergebnis warten. None = keine Antwort in der Zeit."""
        task = {"id": secrets.token_urlsafe(12), "kind": kind, "params": params}
        fut = asyncio.get_running_loop().create_future()
        self.futures[task["id"]] = fut
        self.pending.setdefault(node_id, []).append(task)
        try:
            return await asyncio.wait_for(fut, timeout)
        except TimeoutError:
            return None
        finally:
            self.futures.pop(task["id"], None)
            queue = self.pending.get(node_id)
            if queue and task in queue:
                queue.remove(task)
