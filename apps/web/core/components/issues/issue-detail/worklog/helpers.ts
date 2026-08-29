/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

/**
 * Formats a duration in minutes into a compact human string, e.g. 150 -> "2h 30m".
 */
export const formatDuration = (minutes: number): string => {
  if (!minutes || minutes <= 0) return "0m";
  const hours = Math.floor(minutes / 60);
  const mins = minutes % 60;
  if (hours && mins) return `${hours}h ${mins}m`;
  if (hours) return `${hours}h`;
  return `${mins}m`;
};

/**
 * Parses a user-typed duration into minutes.
 * Accepts "2h 30m", "2h", "45m", "1.5h", "90" (bare number = minutes).
 * Returns null when the input cannot be understood.
 */
export const parseDuration = (input: string): number | null => {
  const value = input.trim().toLowerCase();
  if (!value) return null;

  // Bare number is treated as minutes.
  if (/^\d+(\.\d+)?$/.test(value)) {
    const minutes = Math.round(parseFloat(value));
    return minutes > 0 ? minutes : null;
  }

  const pattern = /^(?:(\d+(?:\.\d+)?)\s*h)?\s*(?:(\d+(?:\.\d+)?)\s*m)?$/;
  const match = value.match(pattern);
  if (!match || (!match[1] && !match[2])) return null;

  const hours = match[1] ? parseFloat(match[1]) : 0;
  const mins = match[2] ? parseFloat(match[2]) : 0;
  const total = Math.round(hours * 60 + mins);
  return total > 0 ? total : null;
};

/** Today's date as YYYY-MM-DD in the viewer's local timezone. */
export const todayISODate = (): string => {
  const now = new Date();
  const offset = now.getTimezoneOffset();
  return new Date(now.getTime() - offset * 60 * 1000).toISOString().split("T")[0];
};
