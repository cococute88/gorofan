"use client";

import { useEffect } from "react";

import { BottomTabBar } from "@/components/layout/bottom-tab-bar";
import { Sidebar } from "@/components/layout/sidebar";
import { useUIStore } from "@/stores/ui-store";

export function AppShell({ children }: { children: React.ReactNode }) {
  const theme = useUIStore((s) => s.theme);

  useEffect(() => {
    const root = document.documentElement;
    const apply = () => {
      const dark =
        theme === "dark" ||
        (theme === "system" && window.matchMedia("(prefers-color-scheme: dark)").matches);
      root.classList.toggle("dark", dark);
    };
    apply();
  }, [theme]);

  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <div className="flex min-h-screen flex-1 flex-col">
        <main className="mx-auto w-full max-w-screen-xl flex-1 px-4 pb-20 pt-4 md:pb-8 md:pt-6">
          {children}
        </main>
      </div>
      <BottomTabBar />
    </div>
  );
}

export function PageHeader({
  title,
  action,
}: {
  title: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="mb-4 flex items-center justify-between">
      <h1 className="text-2xl font-bold">{title}</h1>
      {action}
    </div>
  );
}
