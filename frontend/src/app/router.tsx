import { useEffect, useState } from "react";

export type AppRoute = "workspace" | "documents" | "tasks" | "monitor" | "settings";

export interface NavItem {
  route: AppRoute;
  label: string;
  description: string;
}

export const NAV_ITEMS: NavItem[] = [
  { route: "workspace", label: "问答", description: "基于已索引文档提问" },
  { route: "documents", label: "文档", description: "上传、索引、删除" },
  { route: "tasks", label: "任务", description: "查看处理进度" },
  { route: "settings", label: "配置", description: "连接和检索参数" },
  { route: "monitor", label: "状态", description: "基础服务状态" },
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
