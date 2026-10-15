import { LogOut } from "lucide-react";
import { errorMessage } from "../../lib/api/client";
import { Avatar, Button, Notice, PageState } from "../../shared/ui";
import { useSession } from "../auth/session";
import { ProfileForm } from "./ProfileForm";
import { useProfile } from "./useProfile";

export function ProfilePage() {
  const clear = useSession((state) => state.clear);
  const me = useProfile();
  if (me.isPending)
    return (
      <div className="content-narrow">
        <PageState title="Cargando perfil…" />
      </div>
    );
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
          <Avatar
            name={me.data.fullName}
            src={me.data.profileImageUrl}
            size="large"
          />
          <h2>{me.data.fullName}</h2>
          <p>{me.data.email}</p>
          <p className="muted">
            Tu foto de perfil es pública; la referencia para acceso facial es
            privada.
          </p>
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
