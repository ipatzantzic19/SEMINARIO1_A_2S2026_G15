import { z } from 'zod';
import type { Cloud } from '../shared/types.ts';

const publicUrl = z.string().trim().default('').transform((value, context) => {
  if (!value) return '';
  try {
    const url = new URL(value);
    const local = ['localhost', '127.0.0.1', '[::1]'].includes(url.hostname);
    if (url.protocol !== 'https:' && !(local && url.protocol === 'http:')) throw new Error('Los servicios públicos deben usar HTTPS; HTTP solo se admite en localhost.');
    if (url.username || url.password || url.search || url.hash) throw new Error('Las URLs no deben incluir claves, consultas ni fragmentos.');
    return url.href.replace(/\/+$/, '');
  } catch (cause) {
    context.addIssue({ code: 'custom', message: cause instanceof Error ? cause.message : 'URL inválida.' });
    return z.NEVER;
  }
});
const mode = z.enum(['mock', 'real'], { error: 'El modo debe ser mock o real.' });
const cloud = z.enum(['aws', 'azure'], { error: 'La nube inicial debe ser aws o azure.' });
const endpoints = z.object({ apiBaseUrl: publicUrl, uploadBaseUrl: publicUrl }).strict();
const configSchema = z.object({
  mode: mode.default('mock'), defaultCloud: cloud.default('aws'),
  timeoutMs: z.number().int().min(1000).max(60000).default(20000),
  aws: endpoints.default({ apiBaseUrl: '', uploadBaseUrl: '' }),
  azure: endpoints.default({ apiBaseUrl: '', uploadBaseUrl: '' }),
}).strict();
const envSchema = z.object({
  VITE_APP_MODE: mode.default('mock'),
  VITE_DEFAULT_CLOUD: cloud.default('aws'),
  VITE_API_TIMEOUT_MS: z.preprocess(value => value === undefined || value === '' ? 20000 : value, z.coerce.number().int().min(1000).max(60000)),
  VITE_AWS_API_BASE_URL: publicUrl,
  VITE_AWS_UPLOAD_BASE_URL: publicUrl,
  VITE_AZURE_API_BASE_URL: publicUrl,
  VITE_AZURE_UPLOAD_BASE_URL: publicUrl,
});
export type Config = z.output<typeof configSchema>;
declare global { interface Window { TASKFLOW_CONFIG?: unknown } }

function parse<T>(schema: z.ZodType<T>, source: unknown): T {
  const result = schema.safeParse(source);
  if (!result.success) throw new Error(`Configuración inválida: ${result.error.issues.map(issue => `${issue.path.join('.') || 'config'}: ${issue.message}`).join(' · ')}`);
  return result.data;
}
export function parseEnv(source: Record<string, unknown>) {
  const known = Object.fromEntries(Object.keys(envSchema.shape).map(key => [key, source[key]]));
  return parse(envSchema, known);
}
export function parseConfig(source: unknown): Config { return parse(configSchema, source); }

export function loadConfig(source: Record<string, unknown>, runtime: unknown): Config {
  const env = parseEnv(source);
  const base = {
    mode: env.VITE_APP_MODE, defaultCloud: env.VITE_DEFAULT_CLOUD, timeoutMs: env.VITE_API_TIMEOUT_MS,
    aws: { apiBaseUrl: env.VITE_AWS_API_BASE_URL, uploadBaseUrl: env.VITE_AWS_UPLOAD_BASE_URL },
    azure: { apiBaseUrl: env.VITE_AZURE_API_BASE_URL, uploadBaseUrl: env.VITE_AZURE_UPLOAD_BASE_URL },
  };
  if (runtime === undefined) return parseConfig(base);
  if (!runtime || typeof runtime !== 'object' || Array.isArray(runtime)) throw new Error('config.js debe declarar un objeto de configuración.');
  const overrides = runtime as Record<string, unknown>;
  for (const provider of ['aws', 'azure']) {
    if (overrides[provider] !== undefined && (!overrides[provider] || typeof overrides[provider] !== 'object' || Array.isArray(overrides[provider]))) throw new Error(`La configuración de ${provider} debe ser un objeto.`);
  }
  return parseConfig({ ...base, ...overrides,
    aws: { ...base.aws, ...(overrides.aws as object | undefined) },
    azure: { ...base.azure, ...(overrides.azure as object | undefined) },
  });
}
export function assertCloudReady(config: Config, provider: Cloud) {
  if (config.mode === 'real' && (!config[provider].apiBaseUrl || !config[provider].uploadBaseUrl)) throw new Error(`Faltan las URLs de backend y carga de ${provider.toUpperCase()} en .env/config.js. No se usará un mock como respaldo.`);
}
