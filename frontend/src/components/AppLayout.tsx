import { Link, Outlet } from "react-router-dom";

import { useAuth } from "@/contexts/AuthContext";

const navLinks = [
  { to: "/dashboard", label: "Dashboard" },
  { to: "/upload", label: "Upload" },
  { to: "/transactions", label: "Transactions" },
  { to: "/recurring", label: "Recurring" },
  { to: "/insights", label: "Insights" },
  { to: "/progress", label: "Progress" },
  { to: "/settings", label: "Settings" },
];

export function AppLayout() {
  const { user, logout } = useAuth();

  return (
    <div className="min-h-screen">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-4">
          <div className="flex items-center gap-6">
            <Link to="/dashboard" className="text-lg font-semibold text-brand-700">
              Financial Health
            </Link>
            <nav className="hidden gap-4 sm:flex">
              {navLinks.map((link) => (
                <Link
                  key={link.to}
                  to={link.to}
                  className="text-sm font-medium text-slate-600 hover:text-brand-700"
                >
                  {link.label}
                </Link>
              ))}
            </nav>
          </div>
          <div className="flex items-center gap-4">
            <span className="text-sm text-slate-600">{user?.email}</span>
            <button
              type="button"
              onClick={() => logout()}
              className="rounded-md bg-slate-100 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-200"
            >
              Log out
            </button>
          </div>
        </div>
      </header>
      <main className="mx-auto w-full min-w-0 max-w-7xl px-4 py-8">
        <Outlet />
      </main>
    </div>
  );
}
