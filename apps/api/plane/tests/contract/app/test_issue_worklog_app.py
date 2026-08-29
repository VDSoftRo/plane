# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""
Contract tests for the work item worklog endpoints.

Covers the two guarantees the feature rests on:

* **Ownership** — a MEMBER may only edit or delete the entries they logged
  themselves; a project ADMIN may edit or delete anyone's.
* **Input bounds** — the project toggle gates creation entirely, and a single
  entry must be a positive duration of at most 24h logged on a non-future date.
"""

import uuid
from datetime import date, timedelta

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from plane.db.models import (
    Issue,
    IssueWorklog,
    Project,
    ProjectMember,
    User,
    WorkspaceMember,
)

ADMIN_ROLE = 20
MEMBER_ROLE = 15
GUEST_ROLE = 5


def _worklogs_url(slug: str, project_id: uuid.UUID, issue_id: uuid.UUID) -> str:
    return f"/api/workspaces/{slug}/projects/{project_id}/issues/{issue_id}/worklogs/"


def _worklog_detail_url(slug: str, project_id: uuid.UUID, issue_id: uuid.UUID, pk: uuid.UUID) -> str:
    return f"{_worklogs_url(slug, project_id, issue_id)}{pk}/"


def _total_url(slug: str, project_id: uuid.UUID, issue_id: uuid.UUID) -> str:
    return f"/api/workspaces/{slug}/projects/{project_id}/issues/{issue_id}/total-worklogs/"


def _make_user(email: str) -> User:
    local_part = email.split("@")[0]
    user = User.objects.create(email=email, username=local_part, first_name=local_part)
    user.set_password("test-password")
    user.save()
    return user


def _add_member(workspace, project, user, *, project_role: int, ws_role: int = MEMBER_ROLE) -> ProjectMember:
    WorkspaceMember.objects.create(workspace=workspace, member=user, role=ws_role, is_active=True)
    return ProjectMember.objects.create(
        workspace=workspace, project=project, member=user, role=project_role, is_active=True
    )


def _client_for(user: User) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def project(db, workspace, create_user):
    """A project with time tracking enabled, administered by ``create_user``."""
    project = Project.objects.create(
        name="Worklog Project",
        identifier="WLG",
        workspace=workspace,
        created_by=create_user,
        is_time_tracking_enabled=True,
    )
    ProjectMember.objects.create(
        workspace=workspace,
        project=project,
        member=create_user,
        role=ADMIN_ROLE,
        is_active=True,
    )
    return project


@pytest.fixture
def issue(db, workspace, project, create_user):
    return Issue.objects.create(
        name="Work item under test",
        workspace=workspace,
        project=project,
        created_by=create_user,
    )


def _log_time(project, issue, user, *, duration: int = 60, logged_on: date | None = None) -> IssueWorklog:
    return IssueWorklog.objects.create(
        workspace=project.workspace,
        project=project,
        issue=issue,
        logged_by=user,
        duration=duration,
        logged_on=logged_on or date.today(),
    )


@pytest.mark.contract
class TestIssueWorklogOwnership:
    """A member owns their entries; an admin owns everyone's."""

    def test_member_cannot_edit_another_users_entry(self, workspace, project, issue, create_user):
        author = _make_user("worklog-author@plane.so")
        attacker = _make_user("worklog-attacker@plane.so")
        _add_member(workspace, project, author, project_role=MEMBER_ROLE)
        _add_member(workspace, project, attacker, project_role=MEMBER_ROLE)
        entry = _log_time(project, issue, author, duration=60)

        response = _client_for(attacker).patch(
            _worklog_detail_url(workspace.slug, project.id, issue.id, entry.id),
            {"duration": 999},
            format="json",
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN
        entry.refresh_from_db()
        assert entry.duration == 60

    def test_member_cannot_delete_another_users_entry(self, workspace, project, issue, create_user):
        author = _make_user("worklog-author-2@plane.so")
        attacker = _make_user("worklog-attacker-2@plane.so")
        _add_member(workspace, project, author, project_role=MEMBER_ROLE)
        _add_member(workspace, project, attacker, project_role=MEMBER_ROLE)
        entry = _log_time(project, issue, author)

        response = _client_for(attacker).delete(
            _worklog_detail_url(workspace.slug, project.id, issue.id, entry.id)
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert IssueWorklog.objects.filter(pk=entry.id).exists()

    def test_member_can_edit_own_entry(self, workspace, project, issue):
        author = _make_user("worklog-owner@plane.so")
        _add_member(workspace, project, author, project_role=MEMBER_ROLE)
        entry = _log_time(project, issue, author, duration=60)

        response = _client_for(author).patch(
            _worklog_detail_url(workspace.slug, project.id, issue.id, entry.id),
            {"duration": 90},
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK
        entry.refresh_from_db()
        assert entry.duration == 90

    def test_project_admin_can_edit_another_users_entry(self, workspace, project, issue, create_user):
        author = _make_user("worklog-author-3@plane.so")
        _add_member(workspace, project, author, project_role=MEMBER_ROLE)
        entry = _log_time(project, issue, author, duration=60)

        response = _client_for(create_user).patch(
            _worklog_detail_url(workspace.slug, project.id, issue.id, entry.id),
            {"duration": 120},
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK
        entry.refresh_from_db()
        assert entry.duration == 120

    def test_project_admin_can_delete_another_users_entry(self, workspace, project, issue, create_user):
        author = _make_user("worklog-author-4@plane.so")
        _add_member(workspace, project, author, project_role=MEMBER_ROLE)
        entry = _log_time(project, issue, author)

        response = _client_for(create_user).delete(
            _worklog_detail_url(workspace.slug, project.id, issue.id, entry.id)
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not IssueWorklog.objects.filter(pk=entry.id, deleted_at__isnull=True).exists()

    def test_guest_cannot_log_time(self, workspace, project, issue):
        guest = _make_user("worklog-guest@plane.so")
        _add_member(workspace, project, guest, project_role=GUEST_ROLE)

        response = _client_for(guest).post(
            _worklogs_url(workspace.slug, project.id, issue.id),
            {"duration": 60, "logged_on": str(date.today())},
            format="json",
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert IssueWorklog.objects.count() == 0


@pytest.mark.contract
class TestIssueWorklogValidation:
    """Creation is gated by the project toggle and bounded per entry."""

    def test_cannot_log_time_when_project_toggle_is_off(self, workspace, project, issue, create_user):
        project.is_time_tracking_enabled = False
        project.save()

        response = _client_for(create_user).post(
            _worklogs_url(workspace.slug, project.id, issue.id),
            {"duration": 60, "logged_on": str(date.today())},
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert IssueWorklog.objects.count() == 0

    @pytest.mark.parametrize("duration", [0, -30])
    def test_duration_must_be_positive(self, workspace, project, issue, create_user, duration):
        response = _client_for(create_user).post(
            _worklogs_url(workspace.slug, project.id, issue.id),
            {"duration": duration, "logged_on": str(date.today())},
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert IssueWorklog.objects.count() == 0

    def test_duration_cannot_exceed_24_hours(self, workspace, project, issue, create_user):
        response = _client_for(create_user).post(
            _worklogs_url(workspace.slug, project.id, issue.id),
            {"duration": 24 * 60 + 1, "logged_on": str(date.today())},
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "duration" in response.data

    def test_exactly_24_hours_is_allowed(self, workspace, project, issue, create_user):
        response = _client_for(create_user).post(
            _worklogs_url(workspace.slug, project.id, issue.id),
            {"duration": 24 * 60, "logged_on": str(date.today())},
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED

    def test_cannot_log_time_on_a_future_date(self, workspace, project, issue, create_user):
        response = _client_for(create_user).post(
            _worklogs_url(workspace.slug, project.id, issue.id),
            {"duration": 60, "logged_on": str(date.today() + timedelta(days=1))},
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "logged_on" in response.data

    def test_logged_by_is_taken_from_the_request_not_the_payload(self, workspace, project, issue, create_user):
        """A caller must not be able to attribute time to somebody else."""
        other = _make_user("worklog-impersonated@plane.so")
        _add_member(workspace, project, other, project_role=MEMBER_ROLE)

        response = _client_for(create_user).post(
            _worklogs_url(workspace.slug, project.id, issue.id),
            {"duration": 60, "logged_on": str(date.today()), "logged_by": str(other.id)},
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert IssueWorklog.objects.get(pk=response.data["id"]).logged_by_id == create_user.id


@pytest.mark.contract
class TestIssueWorklogTotals:
    """The per-item total aggregates every member's entries."""

    def test_total_sums_entries_from_all_users(self, workspace, project, issue, create_user):
        other = _make_user("worklog-teammate@plane.so")
        _add_member(workspace, project, other, project_role=MEMBER_ROLE)
        _log_time(project, issue, create_user, duration=150)
        _log_time(project, issue, other, duration=90)

        response = _client_for(create_user).get(_total_url(workspace.slug, project.id, issue.id))

        assert response.status_code == status.HTTP_200_OK
        assert response.data["total_duration"] == 240

    def test_total_is_zero_when_nothing_is_logged(self, workspace, project, issue, create_user):
        response = _client_for(create_user).get(_total_url(workspace.slug, project.id, issue.id))

        assert response.status_code == status.HTTP_200_OK
        assert response.data["total_duration"] == 0

    def test_deleted_entries_are_excluded_from_the_total(self, workspace, project, issue, create_user):
        keep = _log_time(project, issue, create_user, duration=60)
        drop = _log_time(project, issue, create_user, duration=30)
        _client_for(create_user).delete(
            _worklog_detail_url(workspace.slug, project.id, issue.id, drop.id)
        )

        response = _client_for(create_user).get(_total_url(workspace.slug, project.id, issue.id))

        assert response.data["total_duration"] == keep.duration
