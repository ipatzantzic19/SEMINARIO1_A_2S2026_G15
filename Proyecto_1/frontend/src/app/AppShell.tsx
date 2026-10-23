import {
  Bot,
  House,
  LogOut,
  MessageCircle,
  UsersRound,
  UserRound,
} from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { useRegistration } from "../features/auth/registration";
import { useSession } from "../features/auth/session";
import { FloatingChat } from "../features/chat/FloatingChat";
import { useFeedState } from "../features/feed/feedState";
import { useBotState } from "../features/bot/botState";

const links = [
  { to: "/", label: "Inicio", mobileLabel: "Inicio", Icon: House, end: true },
  {
    to: "/people",
    label: "Personas",
    mobileLabel: "Personas",
    Icon: UsersRound,
  },
  {
    to: "/chat",
    label: "Chat",
    mobileLabel: "Chat",
    Icon: MessageCircle,
  },
  {
    to: "/profile",
    label: "Mi perfil",
    mobileLabel: "Perfil",
    Icon: UserRound,
  },
];

export function AppShell() {
  const location = useLocation();
  const clearSession = useSession((state) => state.clear);
  const clearPhoto = useRegistration((state) => state.setPhoto);
  const resetFeed = useFeedState((state) => state.reset);
  const resetBot = useBotState((state) => state.reset);
  const queryClient = useQueryClient();

  function logout() {
    clearSession();
    clearPhoto(null);
    resetFeed();
    resetBot();
    queryClient.clear();
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <NavLink className="brand" to="/">
          semi<span>social</span>
        </NavLink>
        <nav aria-label="Navegación principal">
          {links.map(({ to, label, Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                isActive ? "nav-link active" : "nav-link"
              }
            >
              <Icon size={20} aria-hidden="true" />
              {label}
            </NavLink>
          ))}
          <NavLink
            to="/bot"
            className={({ isActive }) =>
              isActive ? "nav-link active" : "nav-link"
            }
          >
            <Bot size={20} aria-hidden="true" />
            Bot de la Facultad
          </NavLink>
        </nav>
        <button className="nav-link signout" onClick={logout}>
          <LogOut size={20} aria-hidden="true" />
          Cerrar sesión
        </button>
      </aside>

      <div className="app-content">
        <header className="mobile-header">
          <NavLink className="brand" to="/">
            semi<span>social</span>
          </NavLink>
          <NavLink to="/bot" aria-label="Bot de la Facultad">
            <Bot size={22} aria-hidden="true" />
          </NavLink>
        </header>
        <main id="main-content">
          <Outlet />
        </main>
      </div>

      <nav className="mobile-nav" aria-label="Navegación móvil">
        {links.map(({ to, mobileLabel, Icon, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            className={({ isActive }) =>
              isActive ? "mobile-link active" : "mobile-link"
            }
          >
            <Icon size={20} aria-hidden="true" />
            <span>{mobileLabel}</span>
          </NavLink>
        ))}
      </nav>

      {location.pathname === "/" && <FloatingChat />}
    </div>
  );
}
