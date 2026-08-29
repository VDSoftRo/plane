/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
// plane imports
import { EUserPermissions, EUserPermissionsLevel } from "@plane/constants";
import { useTranslation } from "@plane/i18n";
// components
import { NotAuthorizedView } from "@/components/auth-screens/not-authorized-view";
import { PageHead } from "@/components/core/page-title";
import { ProjectWorklogReport } from "@/components/issues/issue-detail/worklog";
import { SettingsContentWrapper } from "@/components/settings/content-wrapper";
import { SettingsHeading } from "@/components/settings/heading";
// hooks
import { useProject } from "@/hooks/store/use-project";
import { useUserPermissions } from "@/hooks/store/user";
// local imports
import type { Route } from "./+types/page";
import { FeaturesTimeReportProjectSettingsHeader } from "./header";

function FeaturesTimeReportSettingsPage({ params }: Route.ComponentProps) {
  const { workspaceSlug, projectId } = params;
  // store hooks
  const { workspaceUserInfo, allowPermissions } = useUserPermissions();
  const { currentProjectDetails } = useProject();
  // translation
  const { t } = useTranslation();
  // derived values
  const pageTitle = currentProjectDetails?.name ? `${currentProjectDetails?.name} settings - Time report` : undefined;
  const canPerformProjectAdminActions = allowPermissions([EUserPermissions.ADMIN], EUserPermissionsLevel.PROJECT);

  if (workspaceUserInfo && !canPerformProjectAdminActions) {
    return <NotAuthorizedView section="settings" isProjectView className="h-auto" />;
  }

  return (
    <SettingsContentWrapper header={<FeaturesTimeReportProjectSettingsHeader />}>
      <PageHead title={pageTitle} />
      <section className="w-full">
        <SettingsHeading title="Time report" description="Total time logged against each work item over a period." />
        {currentProjectDetails?.is_time_tracking_enabled ? (
          <div className="mt-7">
            <ProjectWorklogReport workspaceSlug={workspaceSlug} projectId={projectId} />
          </div>
        ) : (
          <p className="mt-7 text-body-xs-regular text-placeholder">
            {t("project_settings.features.time_tracking.toggle_title")} is off for this project, so there is nothing to
            report on yet.
          </p>
        )}
      </section>
    </SettingsContentWrapper>
  );
}

export default observer(FeaturesTimeReportSettingsPage);
