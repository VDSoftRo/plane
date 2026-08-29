# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Django imports
from django.utils import timezone

# Third party imports
from rest_framework import serializers

# Module imports
from .base import BaseSerializer
from .user import UserLiteSerializer
from plane.db.models import IssueWorklog

# A single entry is capped at 24h to catch typos such as "600" meant as "6h".
MAX_WORKLOG_DURATION = 24 * 60


class IssueWorklogSerializer(BaseSerializer):
    logged_by_detail = UserLiteSerializer(read_only=True, source="logged_by")

    class Meta:
        model = IssueWorklog
        fields = [
            "id",
            "issue",
            "project",
            "workspace",
            "logged_by",
            "logged_by_detail",
            "duration",
            "logged_on",
            "description",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "workspace",
            "project",
            "issue",
            "logged_by",
            "created_at",
            "updated_at",
        ]

    def validate_duration(self, value):
        if value <= 0:
            raise serializers.ValidationError("Duration must be greater than 0 minutes.")
        if value > MAX_WORKLOG_DURATION:
            raise serializers.ValidationError("Duration cannot exceed 24 hours for a single entry.")
        return value

    def validate_logged_on(self, value):
        if value > timezone.now().date():
            raise serializers.ValidationError("Time cannot be logged against a future date.")
        return value
