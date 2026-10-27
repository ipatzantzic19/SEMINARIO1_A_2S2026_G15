import { lazy, Suspense } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { useSession } from "../features/auth/session";
import { AppShell } from "./AppShell";

const LoginPage = lazy(() =>
  import("../features/auth/LoginPage").then((module) => ({
    default: module.LoginPage,
  })),
);
const RegisterPage = lazy(() =>
  import("../features/auth/RegisterPage").then((module) => ({
    default: module.RegisterPage,
  })),
);
const ConfirmPage = lazy(() =>
  import("../features/auth/ConfirmPage").then((module) => ({
    default: module.ConfirmPage,
  })),
);
const CompleteProfilePage = lazy(() =>
  import("../features/auth/CompleteProfilePage").then((module) => ({
    default: module.CompleteProfilePage,
  })),
);
const FaceLoginPage = lazy(() =>
  import("../features/auth/FaceLoginPage").then((module) => ({
    default: module.FaceLoginPage,
  })),
);
const FeedPage = lazy(() =>
  import("../features/feed/FeedPage").then((module) => ({
    default: module.FeedPage,
  })),
);
const PeoplePage = lazy(() =>
  import("../features/people/PeoplePage").then((module) => ({
    default: module.PeoplePage,
  })),
);
const ChatPage = lazy(() =>
  import("../features/chat/ChatPage").then((module) => ({
    default: module.ChatPage,
  })),
);
const ProfilePage = lazy(() =>
  import("../features/profile/ProfilePage").then((module) => ({
    default: module.ProfilePage,
  })),
);
const BotPage = lazy(() =>
  import("../features/bot/BotPage").then((module) => ({
    default: module.BotPage,
  })),
);

function Protected() {
  const tokens = useSession((state) => state.tokens);
  if (!tokens) return <Navigate to="/login" replace />;
  if (!tokens.profileComplete)
    return <Navigate to="/complete-profile" replace />;
  return <AppShell />;
}

export function App() {
  const tokens = useSession((state) => state.tokens);
  return (
    <Suspense
      fallback={
        <main className="route-loading" role="status">
          Cargando pantalla…
        </main>
      }
    >
      <Routes>
        <Route
          path="/login"
          element={
            tokens ? (
              <Navigate
                to={tokens.profileComplete ? "/" : "/complete-profile"}
                replace
              />
            ) : (
              <LoginPage />
            )
          }
        />
        <Route path="/login/face" element={<FaceLoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route path="/confirm" element={<ConfirmPage />} />
        <Route
          path="/complete-profile"
          element={
            tokens ? <CompleteProfilePage /> : <Navigate to="/login" replace />
          }
        />
        <Route path="/" element={<Protected />}>
          <Route index element={<FeedPage />} />
          <Route path="people" element={<PeoplePage />} />
          <Route path="chat" element={<ChatPage />} />
          <Route path="profile" element={<ProfilePage />} />
          <Route path="bot" element={<BotPage />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Suspense>
  );
}
