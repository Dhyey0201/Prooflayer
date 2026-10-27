import { NavLink } from "./NavLink";

export const NAV_ITEMS = [
  { href: "/", label: "Dashboard" },
  { href: "/runs", label: "Runs" },
  { href: "/benchmark", label: "Benchmark" },
] as const;

export function Sidebar() {
  return (
    <aside className="hidden w-60 flex-col border-r border-border bg-surface/60 px-4 py-6 md:flex">
      <div className="mb-8 px-2">
        <p className="text-sm font-semibold tracking-wide text-foreground">
          ProofLayer
        </p>
        <p className="text-xs text-muted">Outcome verification studio</p>
      </div>
      <nav aria-label="Primary" className="flex flex-col gap-1">
        {NAV_ITEMS.map((item) => (
          <NavLink key={item.href} href={item.href}>
            {item.label}
          </NavLink>
        ))}
      </nav>
    </aside>
  );
}
