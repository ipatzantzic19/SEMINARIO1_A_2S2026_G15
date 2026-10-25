import { BadgeCheck, LockKeyhole, LogOut, Mail } from "lucide-react";
import { errorMessage } from "../../lib/api/client";
import { Avatar, Button, Notice } from "../../shared/ui";
import { useSession } from "../auth/session";
import { ProfileForm } from "./ProfileForm";
import { ProfileSkeleton } from "./ProfileSkeleton";
import { useProfile } from "./useProfile";

export function ProfilePage() {
  const clear = useSession((state) => state.clear);
  const me = useProfile();
  if (me.isPending) return <ProfileSkeleton />;
  if (me.isError)
    return (
      <div className="content-narrow">
        <Notice kind="error">{errorMessage(me.error)}</Notice>
      </div>
    );

  return (
    <div className="content-narrow">
      <header className="page-heading">
        <h1>Mi perfil</h1>
        <p>Controla la información que identifica tu cuenta.</p>
      </header>
      <div className="profile-grid">
        <aside className="profile-summary panel">
          <div className="profile-identity">
            <Avatar
              name={me.data.fullName}
              src={me.data.profileImageUrl}
              size="large"
            />
            <span className="profile-status">
              <BadgeCheck size={15} aria-hidden="true" />
              Perfil completo
            </span>
            <h2>{me.data.fullName}</h2>
          </div>
          <div className="profile-details">
            <p>
              <Mail size={16} aria-hidden="true" />
              <span>{me.data.email}</span>
            </p>
            <p>
              <LockKeyhole size={16} aria-hidden="true" />
              <span>Tu DPI y referencia facial se mantienen privados.</span>
            </p>
          </div>
          <Button variant="ghost" onClick={clear}>
            <LogOut size={18} />
            Cerrar sesión
          </Button>
        </aside>
        <ProfileForm profile={me.data} />
      </div>
    </div>
  );
}
