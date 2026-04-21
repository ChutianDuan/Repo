import type { AppRoute } from "../../app/router";
import { NAV_ITEMS } from "../../app/router";
import type { MonitorOverview } from "../../types/monitor";
import type { SessionSummary } from "../../types/session";
import type { UserItem } from "../../types/user";
import { HealthDot } from "../common/HealthDot";
import { TimestampText } from "../common/TimestampText";

interface AppSidebarProps {
  route: AppRoute;
  sessions: SessionSummary[];
  currentSessionId: number | null;
  users: UserItem[];
  userId: string;
  newUserName: string;
  overview: MonitorOverview;
  pending: string | null;
  onNavigate: (route: AppRoute) => void;
  onSelectSession: (sessionId: number) => void;
  onNewSession: () => void;
  onSelectUser: (user: UserItem) => void;
  onNewUserNameChange: (value: string) => void;
  onCreateUser: () => void;
}

export function AppSidebar({
  route,
  sessions,
  currentSessionId,
  users,
  userId,
  newUserName,
  overview,
  pending,
  onNavigate,
  onSelectSession,
  onNewSession,
  onSelectUser,
  onNewUserNameChange,
  onCreateUser,
}: AppSidebarProps) {
  return (
    <aside className="app-sidebar">
      <nav className="app-sidebar__nav" aria-label="main navigation">
        {NAV_ITEMS.map((item) => (
          <button
            key={item.route}
            type="button"
            className={route === item.route ? "nav-item nav-item--active" : "nav-item"}
            onClick={() => onNavigate(item.route)}
          >
            <span>{item.label}</span>
            <small>{item.description}</small>
          </button>
        ))}
      </nav>

      <div className="sidebar-block">
        <div className="sidebar-block__head">
          <span>Sessions</span>
          <button type="button" className="icon-button" onClick={onNewSession} disabled={pending !== null}>
            +
          </button>
        </div>
        <div className="session-list">
          {sessions.length === 0 ? (
            <p className="sidebar-muted">暂无会话，点击 + 创建。</p>
          ) : (
            sessions.map((session) => (
              <button
                key={session.session_id}
                type="button"
                className={session.session_id === currentSessionId ? "session-item session-item--active" : "session-item"}
                onClick={() => onSelectSession(session.session_id)}
              >
                <strong>{session.title}</strong>
                <span>{session.message_count} messages</span>
                <TimestampText value={session.updated_at} />
              </button>
            ))
          )}
        </div>
      </div>

      <div className="sidebar-block">
        <div className="sidebar-block__head">
          <span>Operator</span>
          <small>User #{userId || "--"}</small>
        </div>
        <div className="compact-form">
          <input
            value={newUserName}
            onChange={(event) => onNewUserNameChange(event.target.value)}
            placeholder="new user name"
          />
          <button type="button" className="button-secondary" onClick={onCreateUser} disabled={pending !== null}>
            Create
          </button>
        </div>
        <div className="user-list">
          {users.map((user) => (
            <button
              type="button"
              key={user.id}
              className={String(user.id) === userId ? "user-pill user-pill--active" : "user-pill"}
              onClick={() => onSelectUser(user)}
            >
              {user.name}
            </button>
          ))}
        </div>
      </div>

      <div className="sidebar-health">
        <HealthDot label="MySQL" state={overview.services.mysql} />
        <HealthDot label="Redis" state={overview.services.redis} />
        <HealthDot label="Worker" state={overview.services.worker} />
        <HealthDot label="LLM" state={overview.services.llm} />
      </div>
    </aside>
  );
}
