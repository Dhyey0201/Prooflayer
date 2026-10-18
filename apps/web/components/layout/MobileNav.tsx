import { NavLink } from "./NavLink";
import { NAV_ITEMS } from "./Sidebar";

export function MobileNav() {
  return (
    <nav
      aria-label="Primary"
      className="flex gap-2 overflow-x-auto border-b border-border bg-surface/60 px-4 py-3 md:hidden"
    >
      {NAV_ITEMS.map((item) => (
        <NavLink key={item.href} href={item.href}>
          {item.label}
        </NavLink>
      ))}
    </nav>
  );
}
