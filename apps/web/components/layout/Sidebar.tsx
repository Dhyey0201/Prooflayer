import { NavLink } from "./NavLink";

export const NAV_ITEMS = [
  { href: "/", label: "Dashboard" },
  { href: "/runs", label: "Runs" },
  { href: "/benchmark", label: "Benchmark" },
] as const;

export function LogoMark({ className = "h-8 w-8" }: { className?: string }) {
  return (
    <span
      aria-hidden
      className={`flex shrink-0 items-center justify-center rounded-lg bg-gradient-to-br from-sky-400 to-emerald-400 text-background shadow-md shadow-sky-950/50 ${className}`}
    >
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.4} className="h-[60%] w-[60%]">
        <path d="M12 3l7 3v5c0 4.5-3 8.3-7 10-4-1.7-7-5.5-7-10V6l7-3z" strokeLinejoin="round" />
        <path d="M9 12l2 2 4-4" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    </span>
  );
}

export function Sidebar() {
  return (
    <aside className="hidden w-60 flex-col border-r border-border bg-surface/60 px-4 py-6 backdrop-blur md:flex">
      <div className="mb-8 flex items-center gap-3 px-2">
        <LogoMark />
        <div>
          <p className="text-sm font-semibold tracking-wide text-foreground">ProofLayer</p>
          <p className="text-xs text-muted">Outcome verification studio</p>
        </div>
      </div>
      <nav aria-label="Primary" className="flex flex-col gap-1">
        {NAV_ITEMS.map((item) => (
          <NavLink key={item.href} href={item.href}>
            {item.label}
          </NavLink>
        ))}
      </nav>
      <p className="mt-auto px-2 text-[11px] leading-relaxed text-muted">
        Live runs: NVIDIA Nemotron on Nebius Token Factory. Verifier: network-less container.
      </p>
    </aside>
  );
}
