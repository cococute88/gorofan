"use client";

import { Settings } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { PRIMARY_NAV } from "@/components/layout/nav-items";
import { useUIStore } from "@/stores/ui-store";
import { cn } from "@/lib/utils";

export function Sidebar() {
  const pathname = usePathname();
  const collapsed = useUIStore((s) => s.sidebarCollapsed);
  const toggle = useUIStore((s) => s.toggleSidebar);

  return (
    <aside
      className={cn(
        "hidden shrink-0 border-r bg-card transition-all md:flex md:flex-col",
        collapsed ? "w-16" : "w-60",
      )}
    >
      <button
        onClick={toggle}
        className="flex h-14 items-center gap-2 px-4 text-left font-bold"
        aria-label="사이드바 토글"
      >
        <span className="text-primary">✦</span>
        {!collapsed && <span>Creative</span>}
      </button>
      <nav className="flex-1 space-y-1 px-2 py-2">
        {PRIMARY_NAV.map((item) => {
          const active = pathname === item.href || (item.href !== "/" && pathname.startsWith(item.href));
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-3 rounded-md px-3 py-2 text-sm",
                active ? "bg-accent font-medium" : "hover:bg-accent/60",
              )}
            >
              <item.icon className="h-5 w-5 shrink-0" />
              {!collapsed && <span>{item.label}</span>}
            </Link>
          );
        })}
      </nav>
      <div className="border-t p-2">
        <Link
          href="/settings"
          className="flex items-center gap-3 rounded-md px-3 py-2 text-sm hover:bg-accent/60"
        >
          <Settings className="h-5 w-5 shrink-0" />
          {!collapsed && <span>설정</span>}
        </Link>
      </div>
    </aside>
  );
}
