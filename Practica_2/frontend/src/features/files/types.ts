export type FileMetadata = {
  nombreOriginal: string;
  tipoMime: string;
  tamanoBytes: number;
  proveedorAlmacenamiento: 'S3' | 'BLOB';
  claveObjeto: string;
  urlObjeto: string;
};
export type CloudFile = FileMetadata & { id: number; usuarioId: number; creadoEn: string };
export type UploadInput = {
  nombreOriginal: string;
  tipoMime: string;
  contenidoBase64: string;
  destino: 'archivo' | 'perfil';
};
export type UploadRoute = '/upload/image' | '/upload/text' | '/upload/file';
