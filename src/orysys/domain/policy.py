from types import MappingProxyType

from orysys.domain.identity import AccessScope, Principal, Role

KNOWLEDGE_SEARCH = "knowledge.search"
ANALYTICS = "analytics.incidents"
MCP_READ = "mcp.read"
ADMIN_ACTION = "admin.impactful_action"

ROLE_TOOLS = MappingProxyType(
    {
        Role.VIEWER: frozenset({KNOWLEDGE_SEARCH}),
        Role.ANALYST: frozenset({KNOWLEDGE_SEARCH, ANALYTICS, MCP_READ}),
        Role.ADMINISTRATOR: frozenset({KNOWLEDGE_SEARCH, ANALYTICS, MCP_READ, ADMIN_ACTION}),
    }
)


def derive_access_scope(principal: Principal) -> AccessScope:
    """Derive retrieval and tool access only from verified identity data."""

    tools = frozenset().union(*(ROLE_TOOLS[role] for role in principal.roles))
    clauses: list[dict[str, object]] = [
        {"access_level": {"$lte": principal.clearance}},
    ]
    if principal.departments:
        clauses.append(
            {
                "$or": [
                    {"department": "all"},
                    {"department": {"$in": sorted(principal.departments)}},
                ]
            }
        )
    else:
        clauses.append({"department": "all"})
    return AccessScope(
        namespace=principal.tenant_id,
        metadata_filter={"$and": clauses},
        allowed_tools=tools,
    )


def tool_is_allowed(scope: AccessScope, tool_name: str) -> bool:
    return tool_name in scope.allowed_tools
