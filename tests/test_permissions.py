
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from backend.app.api.cases import apply_case_access
from backend.app.models import Case


def make_user(role, user_id="TEST-USER"):
    return SimpleNamespace(user_id=user_id, role=role)


def test_administrator_can_build_unrestricted_case_query():
    user = make_user("Academic Administrator")

    query = apply_case_access(select(Case), user)

    # Administrator access should not add relationship joins.
    assert not query._setup_joins


def test_platform_administrator_can_build_unrestricted_case_query():
    user = make_user("Platform Administrator")

    query = apply_case_access(select(Case), user)

    assert not query._setup_joins


def test_reviewer_query_is_restricted_to_assignments():
    user = make_user("Case Reviewer", "TEST-REVIEWER")

    query = apply_case_access(select(Case), user)

    # The query must join assignment and reviewer records.
    assert len(query._setup_joins) == 2


def test_learner_query_is_restricted_by_ownership():
    user = make_user("Learner", "TEST-LEARNER")

    query = apply_case_access(select(Case), user)

    # The query must join submissions and learner records.
    assert len(query._setup_joins) == 2


def test_instructor_query_is_restricted_by_assessment_ownership():
    user = make_user("Instructor", "TEST-INSTRUCTOR")

    query = apply_case_access(select(Case), user)

    assert len(query._setup_joins) == 3


def test_unsupported_role_is_rejected():
    user = make_user("Support Staff")

    with pytest.raises(HTTPException) as exc_info:
        apply_case_access(select(Case), user)

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == (
        "Your role does not have permission to view cases."
    )
