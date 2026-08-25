export default () => ({
  port: parseInt(process.env.PORT || '3000', 10),
  database: {
    host: process.env.BD_HOST,
    port: parseInt(process.env.BD_PUERTO || '5432', 10),
    name: process.env.BD_NOMBRE || 'cloudcinema',
    user: process.env.BD_USUARIO || 'usuario_cloudcinema_node',
    password: process.env.BD_CONTRASENA,
    sslMode: process.env.BD_SSL_MODO || 'disable',
    caPath: process.env.BD_CERTIFICADO_CA,
  },
  aws: {
    region: process.env.REGION_AWS || 'us-east-1',
    bucket: process.env.BUCKET_IMAGENES || 'practica1-images-g15',
    prefijoFotosPerfil: process.env.PREFIJO_FOTOS_PERFIL || 'Fotos_Perfil/',
    prefijoFotosPeliculas: process.env.PREFIJO_FOTOS_PELICULAS || 'Fotos_Peliculas/',
  },
  jwtSecret: process.env.SECRETO_JWT || 'default_secret',
});
