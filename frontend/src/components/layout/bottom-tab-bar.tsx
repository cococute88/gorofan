"use client";

import { MoreHorizontal } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState } from "react";

import { MOBILE_TABS, SECONDARY_NAV } from "@/components/layout/nav-items";
import { cn } from "@/lib/utils";

export function BottomTabBar() {
  const pathname = usePathname();
  const router = useRouter();
  const [moreOpen, setMoreOpen] = useState(false);

  return (
    <>
      <nav
        className="fixed inset-x-0 bottom-0 z-40 flex h-14 items-stretch border-t bg-card pb-[env(safe-area-inset-bottom)] md:hidden"
        role="tablist"
      >
        {MOBILE_TABS.map((tab) => {
          const active = pathname === tab.href || (tab.href !== "/" && pathname.startsWith(tab.href));
          return (
            <Link
              key={tab.href}
              href={tab.href}
              className={cn(
                "flex flex-1 flex-col items-center justify-center gap-0.5 text-xs",
                active ? "text-primary" : "text-muted-foreground",
              )}
            >
              <tab.icon className="h-5 w-5" />
              {tab.label}
            </Link>
          );
        })}
        <button
          onClick={() => setMoreOpen(true)}
          className="flex flex-1 flex-col items-center justify-center gap-0.5 text-xs text-muted-foreground"
        >
          <MoreHorizontal className="h-5 w-5" />
          더보기
        </button>
      </nav>

      {moreOpen ? (
        <div
          className="fixed inset-0 z-50 flex items-end bg-black/40 md:hidden"
          onClick={() => setMoreOpen(false)}
        >
          <div
            className="w-full rounded-t-2xl bg-card p-4 pb-[calc(env(safe-area-inset-bottom)+1rem)]"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="mx-auto mb-3 h-1 w-10 rounded-full bg-muted" />
            {SECONDARY_NAV.map((item) => (
              <button
                key={item.href}
                onClick={() => {
                  setMoreOpen(false);
                  router.push(item.href);
                }}
                className="flex w-full items-center gap-3 rounded-md px-3 py-3 text-left text-sm hover:bg-accent/60"
              >
                <item.icon className="h-5 w-5" />
                {item.label}
              </button>
            ))}
          </div>
        </div>
      ) : null}
    </>
  );
}
