export type User = {
  id: number;
  nombreUsuario: string;
  correoElectronico: string;
  urlImagenPerfil?: string | null;
};
export type Registration = {
  nombreUsuario: string;
  correoElectronico: string;
  contrasena: string;
  confirmacionContrasena: string;
  urlImagenPerfil?: string;
};
export type Login = { nombreUsuario: string; contrasena: string };
export type LoginResult = { token: string; tipoToken: 'Bearer'; expiraEn: number; usuario: User };
export type Session = { token: string; usuario: User; expiresAt: number };
