# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.urls import path

from plane.app.views import (
    IssueWorklogViewSet,
    IssueTotalWorklogEndpoint,
    ProjectWorklogReportEndpoint,
    ProjectWorklogReportCSVEndpoint,
)


urlpatterns = [
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/issues/<uuid:issue_id>/worklogs/",
        IssueWorklogViewSet.as_view({"get": "list", "post": "create"}),
        name="issue-worklogs",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/issues/<uuid:issue_id>/worklogs/<uuid:pk>/",
        IssueWorklogViewSet.as_view({"patch": "partial_update", "delete": "destroy"}),
        name="issue-worklogs",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/issues/<uuid:issue_id>/total-worklogs/",
        IssueTotalWorklogEndpoint.as_view(),
        name="issue-total-worklog",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/worklog-report/",
        ProjectWorklogReportEndpoint.as_view(),
        name="project-worklog-report",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/worklog-report/csv/",
        ProjectWorklogReportCSVEndpoint.as_view(),
        name="project-worklog-report-csv",
    ),
]
