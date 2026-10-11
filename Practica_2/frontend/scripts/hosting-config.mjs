import { parseConfig, assertCloudReady } from '../src/config/env.ts';

// Configuración pública: no agregar JWT, contraseñas ni claves de proveedores.
const gateway = 'https://oaxm8gpqm0.execute-api.us-east-1.amazonaws.com';
const apim = 'https://taskflow-g15-apim.azure-api.net';

export function hostingConfig(cloud) {
  const config = parseConfig({
    mode: 'real',
    defaultCloud: cloud,
    timeoutMs: 20000,
    aws: { apiBaseUrl: gateway, uploadBaseUrl: gateway },
    azure: { apiBaseUrl: `${apim}/backend`, uploadBaseUrl: apim },
  });
  assertCloudReady(config, 'aws');
  assertCloudReady(config, 'azure');
  return config;
}

export function hostingConfigScript(cloud) {
  return '// Configuración PÚBLICA. Sin credenciales. Generada por build:hosting.\n'
    + `window.TASKFLOW_CONFIG = ${JSON.stringify(hostingConfig(cloud), null, 2)};\n`;
}
