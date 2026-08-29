/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import { observer } from "mobx-react";
// ui
import { Button } from "@plane/propel/button";
import { Input } from "@plane/propel/input";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
// hooks
import { useUser } from "@/hooks/store/user";
// services
import { IssueWorklogService } from "@/services/issue";
import type { TIssueWorklog } from "@/services/issue";
// local
import { formatDuration, parseDuration, todayISODate } from "./helpers";

const worklogService = new IssueWorklogService();

type Props = {
  workspaceSlug: string;
  projectId: string;
  issueId: string;
  disabled?: boolean;
  isProjectAdmin?: boolean;
};

export const IssueWorklogRoot = observer(function IssueWorklogRoot(props: Props) {
  const { workspaceSlug, projectId, issueId, disabled = false, isProjectAdmin = false } = props;
  // store hooks
  const { data: currentUser } = useUser();
  // state
  const [worklogs, setWorklogs] = useState<TIssueWorklog[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isFormOpen, setIsFormOpen] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [duration, setDuration] = useState("");
  const [loggedOn, setLoggedOn] = useState(todayISODate());
  const [description, setDescription] = useState("");

  const fetchWorklogs = useCallback(async () => {
    try {
      const response = await worklogService.getWorklogs(workspaceSlug, projectId, issueId);
      setWorklogs(response ?? []);
    } catch {
      // The panel is only rendered when time tracking is on, but a failed
      // fetch should degrade to an empty list rather than break the sidebar.
      setWorklogs([]);
    } finally {
      setIsLoading(false);
    }
  }, [workspaceSlug, projectId, issueId]);

  useEffect(() => {
    void fetchWorklogs();
  }, [fetchWorklogs]);

  const totalMinutes = useMemo(() => worklogs.reduce((sum, log) => sum + (log.duration ?? 0), 0), [worklogs]);

  const resetForm = () => {
    setDuration("");
    setLoggedOn(todayISODate());
    setDescription("");
    setIsFormOpen(false);
  };

  const handleSubmit = async () => {
    const minutes = parseDuration(duration);
    if (minutes === null) {
      setToast({
        type: TOAST_TYPE.ERROR,
        title: "Invalid duration",
        message: 'Enter a duration such as "2h 30m", "45m", or "90".',
      });
      return;
    }

    setIsSubmitting(true);
    try {
      const created = await worklogService.createWorklog(workspaceSlug, projectId, issueId, {
        duration: minutes,
        logged_on: loggedOn,
        description: description.trim(),
      });
      setWorklogs((previous) => [created, ...previous]);
      resetForm();
      setToast({ type: TOAST_TYPE.SUCCESS, title: "Time logged", message: `${formatDuration(minutes)} added.` });
    } catch (error) {
      const detail = (error as Record<string, string[] | string> | undefined) ?? {};
      const firstError = Object.values(detail).flat()[0];
      setToast({
        type: TOAST_TYPE.ERROR,
        title: "Could not log time",
        message: typeof firstError === "string" ? firstError : "Please try again.",
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDelete = async (worklogId: string) => {
    const previous = worklogs;
    setWorklogs((current) => current.filter((log) => log.id !== worklogId));
    try {
      await worklogService.deleteWorklog(workspaceSlug, projectId, issueId, worklogId);
    } catch {
      setWorklogs(previous);
      setToast({ type: TOAST_TYPE.ERROR, title: "Could not delete entry", message: "Please try again." });
    }
  };

  const canModify = (log: TIssueWorklog) => !disabled && (isProjectAdmin || log.logged_by === currentUser?.id);

  return (
    <div className="mt-4">
      <div className="flex items-center justify-between">
        <h5 className="text-body-xs-medium">Time tracked</h5>
        <span className="text-body-xs-medium text-secondary">{formatDuration(totalMinutes)}</span>
      </div>

      {isLoading ? (
        <p className="mt-2 text-body-xs-regular text-placeholder">Loading…</p>
      ) : (
        <>
          {worklogs.length === 0 && !isFormOpen && (
            <p className="mt-2 text-body-xs-regular text-placeholder">No time logged yet.</p>
          )}

          <div className="mt-2 space-y-1.5">
            {worklogs.map((log) => (
              <div key={log.id} className="group flex items-start justify-between gap-2 text-body-xs-regular">
                <div className="min-w-0">
                  <span className="text-secondary">{log.logged_by_detail?.display_name ?? "Unknown"}</span>
                  <span className="mx-1.5 text-placeholder">·</span>
                  <span>{formatDuration(log.duration)}</span>
                  <span className="mx-1.5 text-placeholder">·</span>
                  <span className="text-placeholder">{log.logged_on}</span>
                  {log.description && <p className="truncate text-placeholder">{log.description}</p>}
                </div>
                {canModify(log) && (
                  <button
                    type="button"
                    onClick={() => void handleDelete(log.id)}
                    className="hover:text-danger hidden shrink-0 text-placeholder group-hover:block"
                    aria-label="Delete time entry"
                  >
                    Remove
                  </button>
                )}
              </div>
            ))}
          </div>

          {!disabled &&
            (isFormOpen ? (
              <div className="mt-3 space-y-2">
                <Input
                  type="text"
                  value={duration}
                  onChange={(e) => setDuration(e.target.value)}
                  placeholder="2h 30m"
                  className="w-full text-body-xs-regular"
                />
                <Input
                  type="date"
                  value={loggedOn}
                  max={todayISODate()}
                  onChange={(e) => setLoggedOn(e.target.value)}
                  className="w-full text-body-xs-regular"
                />
                <Input
                  type="text"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="What did you work on? (optional)"
                  className="w-full text-body-xs-regular"
                />
                <div className="flex items-center gap-2">
                  <Button variant="primary" size="sm" onClick={() => void handleSubmit()} loading={isSubmitting}>
                    Save
                  </Button>
                  <Button variant="secondary" size="sm" onClick={resetForm} disabled={isSubmitting}>
                    Cancel
                  </Button>
                </div>
              </div>
            ) : (
              <button
                type="button"
                onClick={() => setIsFormOpen(true)}
                className="mt-2 text-body-xs-medium text-secondary hover:text-primary"
              >
                + Log time
              </button>
            ))}
        </>
      )}
    </div>
  );
});
