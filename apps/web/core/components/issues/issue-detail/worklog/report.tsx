/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useCallback, useEffect, useState } from "react";
import { observer } from "mobx-react";
// ui
import { Button } from "@plane/propel/button";
import { Input } from "@plane/propel/input";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
// services
import { IssueWorklogService } from "@/services/issue";
import type { TWorklogReport } from "@/services/issue";
// local
import { formatDuration, todayISODate } from "./helpers";

const worklogService = new IssueWorklogService();

/** First day of the current month, as YYYY-MM-DD in the viewer's timezone. */
const startOfMonthISODate = (): string => {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-01`;
};

type Props = {
  workspaceSlug: string;
  projectId: string;
};

export const ProjectWorklogReport = observer(function ProjectWorklogReport(props: Props) {
  const { workspaceSlug, projectId } = props;
  // state
  const [startDate, setStartDate] = useState(startOfMonthISODate());
  const [endDate, setEndDate] = useState(todayISODate());
  const [report, setReport] = useState<TWorklogReport | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const fetchReport = useCallback(
    async (from: string, to: string) => {
      setIsLoading(true);
      try {
        const response = await worklogService.getProjectReport(workspaceSlug, projectId, from, to);
        setReport(response);
      } catch (error) {
        const detail = (error as { error?: string } | undefined)?.error;
        setReport(null);
        setToast({
          type: TOAST_TYPE.ERROR,
          title: "Could not load the report",
          message: detail ?? "Please try again.",
        });
      } finally {
        setIsLoading(false);
      }
    },
    [workspaceSlug, projectId]
  );

  useEffect(() => {
    void fetchReport(startDate, endDate);
    // Only run on mount; later reloads happen through Apply.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fetchReport]);

  const isRangeValid = Boolean(startDate) && Boolean(endDate) && startDate <= endDate;

  const handleExport = () => {
    // The endpoint returns a file download; the browser handles it from the URL.
    window.open(worklogService.getProjectReportCSVUrl(workspaceSlug, projectId, startDate, endDate), "_blank");
  };

  return (
    <div>
      <div className="flex flex-wrap items-end gap-3">
        <div>
          <label htmlFor="worklog-report-start" className="text-body-xs-medium text-secondary">
            From
          </label>
          <Input
            id="worklog-report-start"
            type="date"
            value={startDate}
            max={endDate || undefined}
            onChange={(e) => setStartDate(e.target.value)}
            className="mt-1 text-body-xs-regular"
          />
        </div>
        <div>
          <label htmlFor="worklog-report-end" className="text-body-xs-medium text-secondary">
            To
          </label>
          <Input
            id="worklog-report-end"
            type="date"
            value={endDate}
            min={startDate || undefined}
            onChange={(e) => setEndDate(e.target.value)}
            className="mt-1 text-body-xs-regular"
          />
        </div>
        <Button
          variant="primary"
          size="sm"
          onClick={() => void fetchReport(startDate, endDate)}
          disabled={!isRangeValid || isLoading}
        >
          Apply
        </Button>
        <Button
          variant="secondary"
          size="sm"
          onClick={handleExport}
          disabled={!isRangeValid || !report?.work_items.length}
        >
          Export CSV
        </Button>
      </div>

      {!isRangeValid && (
        <p className="text-danger mt-2 text-body-xs-regular">The start date must be on or before the end date.</p>
      )}

      <div className="mt-6">
        {isLoading ? (
          <p className="text-body-xs-regular text-placeholder">Loading…</p>
        ) : !report || report.work_items.length === 0 ? (
          <p className="text-body-xs-regular text-placeholder">No time logged in this period.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-body-xs-regular">
              <thead>
                <tr className="border-b border-subtle-1 text-left text-secondary">
                  <th className="py-2 pr-4 font-medium">Work item</th>
                  <th className="py-2 pr-4 font-medium">Title</th>
                  <th className="py-2 text-right font-medium">Time</th>
                </tr>
              </thead>
              <tbody>
                {report.work_items.map((row) => (
                  <tr key={row.issue_id} className="border-b border-subtle-1">
                    <td className="py-2 pr-4 whitespace-nowrap text-secondary">
                      {row.project_identifier}-{row.sequence_id}
                    </td>
                    <td className="py-2 pr-4">{row.name}</td>
                    <td className="py-2 text-right whitespace-nowrap">{formatDuration(row.total_duration)}</td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr>
                  <td className="py-2 pr-4 text-body-xs-medium" colSpan={2}>
                    Total
                  </td>
                  <td className="py-2 text-right text-body-xs-medium whitespace-nowrap">
                    {formatDuration(report.total_duration)}
                  </td>
                </tr>
              </tfoot>
            </table>
          </div>
        )}
      </div>
    </div>
  );
});
