/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// plane constants
import { API_BASE_URL } from "@plane/constants";
// services
import { APIService } from "@/services/api.service";

export type TIssueWorklogUser = {
  id: string;
  display_name: string;
  first_name: string;
  last_name: string;
  avatar_url: string | null;
};

export type TIssueWorklog = {
  id: string;
  issue: string;
  project: string;
  workspace: string;
  logged_by: string;
  logged_by_detail: TIssueWorklogUser;
  duration: number;
  logged_on: string;
  description: string;
  created_at: string;
  updated_at: string;
};

export type TWorklogReportRow = {
  issue_id: string;
  sequence_id: number;
  project_identifier: string;
  name: string;
  total_duration: number;
};

export type TWorklogReport = {
  start_date: string;
  end_date: string;
  total_duration: number;
  work_items: TWorklogReportRow[];
};

export class IssueWorklogService extends APIService {
  constructor() {
    super(API_BASE_URL);
  }

  async getWorklogs(workspaceSlug: string, projectId: string, issueId: string): Promise<TIssueWorklog[]> {
    return this.get(`/api/workspaces/${workspaceSlug}/projects/${projectId}/issues/${issueId}/worklogs/`)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async getTotalWorklog(
    workspaceSlug: string,
    projectId: string,
    issueId: string
  ): Promise<{ total_duration: number }> {
    return this.get(`/api/workspaces/${workspaceSlug}/projects/${projectId}/issues/${issueId}/total-worklogs/`)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async getProjectReport(
    workspaceSlug: string,
    projectId: string,
    startDate: string,
    endDate: string
  ): Promise<TWorklogReport> {
    return this.get(`/api/workspaces/${workspaceSlug}/projects/${projectId}/worklog-report/`, {
      params: { start_date: startDate, end_date: endDate },
    })
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  /** URL for the CSV download of the same report. */
  getProjectReportCSVUrl(workspaceSlug: string, projectId: string, startDate: string, endDate: string): string {
    const params = new URLSearchParams({ start_date: startDate, end_date: endDate });
    return `${API_BASE_URL}/api/workspaces/${workspaceSlug}/projects/${projectId}/worklog-report/csv/?${params.toString()}`;
  }

  async createWorklog(
    workspaceSlug: string,
    projectId: string,
    issueId: string,
    data: Partial<TIssueWorklog>
  ): Promise<TIssueWorklog> {
    return this.post(`/api/workspaces/${workspaceSlug}/projects/${projectId}/issues/${issueId}/worklogs/`, data)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async updateWorklog(
    workspaceSlug: string,
    projectId: string,
    issueId: string,
    worklogId: string,
    data: Partial<TIssueWorklog>
  ): Promise<TIssueWorklog> {
    return this.patch(
      `/api/workspaces/${workspaceSlug}/projects/${projectId}/issues/${issueId}/worklogs/${worklogId}/`,
      data
    )
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async deleteWorklog(workspaceSlug: string, projectId: string, issueId: string, worklogId: string): Promise<void> {
    return this.delete(
      `/api/workspaces/${workspaceSlug}/projects/${projectId}/issues/${issueId}/worklogs/${worklogId}/`
    )
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }
}
