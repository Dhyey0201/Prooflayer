"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

export function NavLink({
  href,
  children,
}: {
  href: string;
  children: ReactNode;
}) {
  const pathname = usePathname();
  const isActive = pathname === href;

  return (
    <Link
      href={href}
      aria-current={isActive ? "page" : undefined}
      className={`block rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
        isActive
          ? "bg-accent/15 text-accent"
          : "text-muted hover:bg-surface hover:text-foreground"
      }`}
    >
      {children}
    </Link>
  );
}
