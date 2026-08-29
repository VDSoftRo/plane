# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Python imports
import csv
import io
from datetime import date

# Django imports
from django.db.models import Sum
from django.http import HttpResponse

# Third Party imports
from rest_framework import status
from rest_framework.response import Response

# Module imports
from .. import BaseViewSet, BaseAPIView
from plane.app.permissions import allow_permission, ROLE
from plane.app.serializers import IssueWorklogSerializer
from plane.db.models import Issue, IssueWorklog, Project, ProjectMember
from plane.utils.csv_utils import sanitize_csv_row


def _is_project_admin(user, slug, project_id):
    return ProjectMember.objects.filter(
        member=user,
        workspace__slug=slug,
        project_id=project_id,
        role=ROLE.ADMIN.value,
        is_active=True,
    ).exists()


def _time_tracking_enabled(project_id):
    return Project.objects.filter(pk=project_id, is_time_tracking_enabled=True).exists()


class IssueWorklogViewSet(BaseViewSet):
    model = IssueWorklog
    serializer_class = IssueWorklogSerializer

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .filter(workspace__slug=self.kwargs.get("slug"))
            .filter(project_id=self.kwargs.get("project_id"))
            .filter(issue_id=self.kwargs.get("issue_id"))
            .filter(
                project__project_projectmember__member=self.request.user,
                project__project_projectmember__is_active=True,
                project__archived_at__isnull=True,
            )
            .select_related("logged_by")
            .distinct()
        )

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER])
    def list(self, request, slug, project_id, issue_id):
        worklogs = self.get_queryset()
        serializer = IssueWorklogSerializer(worklogs, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER])
    def create(self, request, slug, project_id, issue_id):
        if not _time_tracking_enabled(project_id):
            return Response(
                {"error": "Time tracking is not enabled for this project."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Guard against logging time on an issue from another project.
        if not Issue.objects.filter(pk=issue_id, project_id=project_id, workspace__slug=slug).exists():
            return Response({"error": "Work item does not exist."}, status=status.HTTP_404_NOT_FOUND)

        serializer = IssueWorklogSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(project_id=project_id, issue_id=issue_id, logged_by=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER])
    def partial_update(self, request, slug, project_id, issue_id, pk):
        worklog = self.get_queryset().filter(pk=pk).first()
        if worklog is None:
            return Response({"error": "Worklog does not exist."}, status=status.HTTP_404_NOT_FOUND)

        # Members may only edit their own entries; project admins may edit any.
        if worklog.logged_by_id != request.user.id and not _is_project_admin(request.user, slug, project_id):
            return Response(
                {"error": "You can only edit your own time entries."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = IssueWorklogSerializer(worklog, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER])
    def destroy(self, request, slug, project_id, issue_id, pk):
        worklog = self.get_queryset().filter(pk=pk).first()
        if worklog is None:
            return Response({"error": "Worklog does not exist."}, status=status.HTTP_404_NOT_FOUND)

        if worklog.logged_by_id != request.user.id and not _is_project_admin(request.user, slug, project_id):
            return Response(
                {"error": "You can only delete your own time entries."},
                status=status.HTTP_403_FORBIDDEN,
            )

        worklog.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class IssueTotalWorklogEndpoint(BaseAPIView):
    """Aggregate logged time for a work item, visible to every project member."""

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER, ROLE.GUEST])
    def get(self, request, slug, project_id, issue_id):
        total = (
            IssueWorklog.objects.filter(
                workspace__slug=slug,
                project_id=project_id,
                issue_id=issue_id,
            ).aggregate(total=Sum("duration"))["total"]
            or 0
        )
        return Response({"total_duration": total}, status=status.HTTP_200_OK)


def _parse_report_range(request):
    """Read start_date/end_date query params. Returns (start, end, error_response)."""
    parsed = {}
    for key in ("start_date", "end_date"):
        raw = request.GET.get(key)
        if not raw:
            return None, None, Response(
                {"error": f"{key} is required."}, status=status.HTTP_400_BAD_REQUEST
            )
        try:
            parsed[key] = date.fromisoformat(raw)
        except ValueError:
            return None, None, Response(
                {"error": f"{key} must be a valid YYYY-MM-DD date."},
                status=status.HTTP_400_BAD_REQUEST,
            )

    if parsed["start_date"] > parsed["end_date"]:
        return None, None, Response(
            {"error": "start_date cannot be after end_date."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    return parsed["start_date"], parsed["end_date"], None


def _report_rows(slug, project_id, start_date, end_date):
    """Per-work-item totals for the range, largest first. Both bounds inclusive."""
    aggregates = (
        IssueWorklog.objects.filter(
            workspace__slug=slug,
            project_id=project_id,
            logged_on__gte=start_date,
            logged_on__lte=end_date,
        )
        .values("issue_id")
        .annotate(total_duration=Sum("duration"))
        .order_by("-total_duration")
    )
    aggregates = list(aggregates)

    issues = Issue.objects.filter(pk__in=[row["issue_id"] for row in aggregates]).select_related("project")
    issue_map = {issue.id: issue for issue in issues}

    rows = []
    for row in aggregates:
        issue = issue_map.get(row["issue_id"])
        if issue is None:
            continue
        rows.append(
            {
                "issue_id": str(issue.id),
                "sequence_id": issue.sequence_id,
                "project_identifier": issue.project.identifier,
                "name": issue.name,
                "total_duration": row["total_duration"],
            }
        )
    return rows


class ProjectWorklogReportEndpoint(BaseAPIView):
    """Per-work-item logged time for a date range. Project admins only."""

    @allow_permission([ROLE.ADMIN])
    def get(self, request, slug, project_id):
        start_date, end_date, error = _parse_report_range(request)
        if error:
            return error

        rows = _report_rows(slug, project_id, start_date, end_date)
        return Response(
            {
                "start_date": str(start_date),
                "end_date": str(end_date),
                "total_duration": sum(row["total_duration"] for row in rows),
                "work_items": rows,
            },
            status=status.HTTP_200_OK,
        )


class ProjectWorklogReportCSVEndpoint(BaseAPIView):
    """The same report as a CSV download. Project admins only."""

    @allow_permission([ROLE.ADMIN])
    def get(self, request, slug, project_id):
        start_date, end_date, error = _parse_report_range(request)
        if error:
            return error

        rows = _report_rows(slug, project_id, start_date, end_date)
        table = [["Work item", "Title", "Duration (minutes)", "Duration"]]
        for row in rows:
            hours, minutes = divmod(row["total_duration"], 60)
            table.append(
                [
                    f"{row['project_identifier']}-{row['sequence_id']}",
                    row["name"],
                    row["total_duration"],
                    f"{hours}h {minutes}m",
                ]
            )

        buffer = io.StringIO()
        writer = csv.writer(buffer, delimiter=",", quoting=csv.QUOTE_ALL)
        for row in table:
            writer.writerow(sanitize_csv_row(row))
        buffer.seek(0)

        response = HttpResponse(buffer.getvalue(), content_type="text/csv")
        response["Content-Disposition"] = (
            f'attachment; filename="time-report-{start_date}-to-{end_date}.csv"'
        )
        return response
