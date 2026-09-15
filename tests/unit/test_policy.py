from orysys.domain.identity import Principal, Role
from orysys.domain.policy import ADMIN_ACTION, ANALYTICS, KNOWLEDGE_SEARCH, derive_access_scope


def test_viewer_scope_is_derived_from_verified_principal() -> None:
    principal = Principal(
        subject="viewer-1",
        tenant_id="bank-a",
        roles=frozenset({Role.VIEWER}),
        departments=frozenset({"payments"}),
        clearance=2,
    )

    scope = derive_access_scope(principal)

    assert scope.namespace == "bank-a"
    assert scope.metadata_filter == {
        "access_level": {"$lte": 2},
        "department": {"$in": ["payments"]},
    }
    assert KNOWLEDGE_SEARCH in scope.allowed_tools
    assert ANALYTICS not in scope.allowed_tools
    assert ADMIN_ACTION not in scope.allowed_tools


def test_administrator_receives_all_declared_tools() -> None:
    principal = Principal(
        subject="admin-1",
        tenant_id="bank-a",
        roles=frozenset({Role.ADMINISTRATOR}),
        clearance=10,
    )

    scope = derive_access_scope(principal)

    assert {KNOWLEDGE_SEARCH, ANALYTICS, ADMIN_ACTION} <= scope.allowed_tools
