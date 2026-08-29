# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Django imports
from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models

# Module imports
from .project import ProjectBaseModel


class IssueWorklog(ProjectBaseModel):
    """A single logged time entry against a work item."""

    issue = models.ForeignKey("db.Issue", on_delete=models.CASCADE, related_name="worklogs")
    logged_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="issue_worklogs",
    )
    # Stored in minutes to keep aggregation exact and avoid float drift.
    duration = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    logged_on = models.DateField()
    description = models.TextField(blank=True)

    def __str__(self):
        return f"{self.issue.name} <{self.logged_by_id}> <{self.duration}m>"

    class Meta:
        verbose_name = "Issue Worklog"
        verbose_name_plural = "Issue Worklogs"
        db_table = "issue_worklogs"
        ordering = ("-logged_on", "-created_at")
        indexes = [
            models.Index(fields=["issue", "deleted_at"], name="worklog_issue_deleted_idx"),
            models.Index(fields=["logged_by", "logged_on"], name="worklog_user_date_idx"),
        ]
