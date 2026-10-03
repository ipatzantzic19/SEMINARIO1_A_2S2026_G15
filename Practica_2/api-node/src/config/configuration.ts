export default () => ({
  port: parseInt(process.env.PORT || '3000', 10),
  database: {
    host: process.env.DB_HOST || 'localhost',
    port: parseInt(process.env.DB_PORT || '5432', 10),
    name: process.env.DB_NAME || 'taskflow',
    user: process.env.DB_USER || 'postgres',
    password: process.env.DB_PASSWORD || 'postgres',
    sslMode: process.env.DB_SSLMODE || 'disable',
    sslRootCert: process.env.DB_SSLROOTCERT || '',
  },
  jwt: {
    secret: process.env.JWT_SECRET || 'secret-key-change-me',
    expiresIn: parseInt(process.env.JWT_EXPIRES_IN || '3600', 10),
  },
  corsOrigins: process.env.CORS_ORIGINS
    ? process.env.CORS_ORIGINS.split(',').map((o) => o.trim()).filter(Boolean)
    : ['http://localhost:5173'],
});
