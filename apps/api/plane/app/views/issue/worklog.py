# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Django imports
from django.db.models import Sum

# Third Party imports
from rest_framework import status
from rest_framework.response import Response

# Module imports
from .. import BaseViewSet, BaseAPIView
from plane.app.permissions import allow_permission, ROLE
from plane.app.serializers import IssueWorklogSerializer
from plane.db.models import Issue, IssueWorklog, Project, ProjectMember


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
