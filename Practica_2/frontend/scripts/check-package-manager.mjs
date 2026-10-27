if (!process.env.npm_config_user_agent?.startsWith('pnpm/')) {
  console.error('Este frontend usa pnpm. Ejecuta corepack pnpm install.');
  process.exit(1);
}
