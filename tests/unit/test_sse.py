from orysys.api.sse import encode_sse
from orysys.domain.events import ActivityEvent, EventType


def test_sse_frame_has_id_event_json_data_and_blank_terminator() -> None:
    event = ActivityEvent(
        sequence=3,
        request_id="request-1",
        run_id="run-1",
        thread_id="thread-1",
        type=EventType.ANSWER_DELTA,
        public_payload={"text": "hello"},
    )

    frame = encode_sse(event).decode()

    assert frame.startswith("id: 3\nevent: answer.delta\ndata: {")
    assert frame.endswith("\n\n")
    assert '"text":"hello"' in frame
