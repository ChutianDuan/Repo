import type { ReactNode } from "react";
import type { AppRoute } from "../../app/router";
import type { MonitorOverview } from "../../types/monitor";
import type { SessionSummary } from "../../types/session";
import type { UserItem } from "../../types/user";
import { AppFooterStatus } from "./AppFooterStatus";
import { AppHeader } from "./AppHeader";
import { AppSidebar } from "./AppSidebar";

interface AppShellProps {
  route: AppRoute;
  children: ReactNode;
  overview: MonitorOverview;
  searchScope: string;
  sessions: SessionSummary[];
  currentSessionId: number | null;
  users: UserItem[];
  userId: string;
  newUserName: string;
  pending: string | null;
  refreshing: boolean;
  retrievalMode: string;
  modelName: string;
  onNavigate: (route: AppRoute) => void;
  onRefresh: () => void;
  onSelectSession: (sessionId: number) => void;
  onNewSession: () => void;
  onSelectUser: (user: UserItem) => void;
  onNewUserNameChange: (value: string) => void;
  onCreateUser: () => void;
}

export function AppShell({
  route,
  children,
  overview,
  searchScope,
  sessions,
  currentSessionId,
  users,
  userId,
  newUserName,
  pending,
  refreshing,
  retrievalMode,
  modelName,
  onNavigate,
  onRefresh,
  onSelectSession,
  onNewSession,
  onSelectUser,
  onNewUserNameChange,
  onCreateUser,
}: AppShellProps) {
  return (
    <div className="workbench-shell">
      <AppHeader
        route={route}
        overview={overview}
        searchScope={searchScope}
        onNavigate={onNavigate}
        onRefresh={onRefresh}
        refreshing={refreshing}
      />
      <div className="workbench-body">
        <AppSidebar
          route={route}
          sessions={sessions}
          currentSessionId={currentSessionId}
          users={users}
          userId={userId}
          newUserName={newUserName}
          overview={overview}
          pending={pending}
          onNavigate={onNavigate}
          onSelectSession={onSelectSession}
          onNewSession={onNewSession}
          onSelectUser={onSelectUser}
          onNewUserNameChange={onNewUserNameChange}
          onCreateUser={onCreateUser}
        />
        <main className="app-content">{children}</main>
      </div>
      <AppFooterStatus overview={overview} retrievalMode={retrievalMode} modelName={modelName} />
    </div>
  );
}
