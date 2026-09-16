import argparse
import asyncio
import json
from uuid import uuid4

from orysys.application.assistant import AssistantRequest
from orysys.bootstrap import live_assistant_runtime
from orysys.config import Settings
from orysys.domain.identity import Principal, Role
from orysys.observability import configure_logging


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run one live grounded Orysys answer")
    parser.add_argument("question")
    parser.add_argument("--tenant", default="commercial-bank")
    parser.add_argument("--department", action="append", default=["payments"])
    parser.add_argument("--role", choices=[role.value for role in Role], default="analyst")
    parser.add_argument("--clearance", type=int, default=2)
    return parser


async def _run(args: argparse.Namespace) -> None:
    settings = Settings()
    configure_logging(settings.log_level)
    principal = Principal(
        subject="assistant-cli",
        tenant_id=args.tenant,
        roles=frozenset({Role(args.role)}),
        departments=frozenset(args.department),
        clearance=args.clearance,
    )
    request = AssistantRequest(
        request_id=str(uuid4()),
        thread_id=str(uuid4()),
        message=args.question,
    )
    async with live_assistant_runtime(settings) as runtime:
        result = await runtime.run(request, principal)
        await asyncio.to_thread(runtime.flush)
    payload = {
        "run_id": result.run_id,
        "answer": result.answer.model_dump(mode="json"),
        "evidence": [
            {
                "evidence_id": item.evidence_id,
                "title": item.title,
                "section": item.section,
                "page": item.page,
                "source_uri": str(item.source_uri),
            }
            for item in result.evidence
        ],
        "validation": [item.model_dump(mode="json") for item in result.validations],
        "event_types": [item.type.value for item in result.events],
    }
    print(json.dumps(payload, indent=2))


def main() -> None:
    asyncio.run(_run(_parser().parse_args()))


if __name__ == "__main__":
    main()
