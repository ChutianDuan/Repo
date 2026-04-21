import { useEffect, useState } from "react";

export type AppRoute = "workspace" | "documents" | "tasks" | "monitor" | "settings";

export interface NavItem {
  route: AppRoute;
  label: string;
  description: string;
}

export const NAV_ITEMS: NavItem[] = [
  { route: "workspace", label: "Workspace", description: "问答工作台" },
  { route: "documents", label: "Documents", description: "文档库" },
  { route: "tasks", label: "Tasks", description: "任务队列" },
  { route: "monitor", label: "Monitor", description: "系统监控" },
  { route: "settings", label: "Settings", description: "检索配置" },
];

function normalizeRoute(value: string | null | undefined): AppRoute {
  const candidate = (value || "").replace(/^#\/?/, "") as AppRoute;
  if (NAV_ITEMS.some((item) => item.route === candidate)) {
    return candidate;
  }
  return "workspace";
}

export function useHashRoute(): [AppRoute, (route: AppRoute) => void] {
  const [route, setRoute] = useState<AppRoute>(() => normalizeRoute(window.location.hash));

  useEffect(() => {
    function handleHashChange() {
      setRoute(normalizeRoute(window.location.hash));
    }

    window.addEventListener("hashchange", handleHashChange);
    return () => window.removeEventListener("hashchange", handleHashChange);
  }, []);

  function navigate(nextRoute: AppRoute) {
    window.location.hash = nextRoute;
    setRoute(nextRoute);
  }

  return [route, navigate];
}
