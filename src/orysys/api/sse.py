import json

from orysys.domain.events import ActivityEvent


def encode_sse(event: ActivityEvent) -> bytes:
    data = json.dumps(event.model_dump(mode="json"), separators=(",", ":"))
    return f"id: {event.sequence}\nevent: {event.type.value}\ndata: {data}\n\n".encode()
