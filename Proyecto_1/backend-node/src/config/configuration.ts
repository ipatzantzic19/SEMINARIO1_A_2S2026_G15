export interface AppConfig {
  port: number;
  nodeEnv: string;
  awsRegion: string;
  apiBasePath: string;
  mockMode: boolean;
  cognito: {
    userPoolId: string;
    appClientId: string;
  };
  rds: {
    host: string;
    port: number;
    database: string;
    user: string;
    password?: string;
    sslMode: string;
  };
  s3: {
    imagesBucket: string;
    profilePrefix: string;
    faceReferencePrefix: string;
    faceCapturePrefix: string;
    postsPrefix: string;
  };
}

export default (): AppConfig => {
  const port = parseInt(process.env.PORT || '3000', 10);
  const rdsPort = parseInt(process.env.RDS_PORT || '5432', 10);
  const mockMode = process.env.MOCK_MODE === 'true' || process.env.NODE_ENV !== 'production';

  // Validaciones críticas en modo producción
  if (process.env.NODE_ENV === 'production' && !mockMode) {
    const requiredEnv = [
      'COGNITO_USER_POOL_ID',
      'COGNITO_APP_CLIENT_ID',
      'RDS_HOST',
      'RDS_DATABASE',
      'RDS_USER',
    ];
    for (const envName of requiredEnv) {
      if (!process.env[envName]) {
        throw new Error(`[CONFIG ERROR] Variable crítica faltante: ${envName}`);
      }
    }
  }

  return {
    port,
    nodeEnv: process.env.NODE_ENV || 'development',
    awsRegion: process.env.AWS_REGION || 'us-east-1',
    apiBasePath: process.env.API_BASE_PATH || '/api/v1',
    mockMode,
    cognito: {
      userPoolId: process.env.COGNITO_USER_POOL_ID || 'us-east-1_4UrrCPt8Z',
      appClientId: process.env.COGNITO_APP_CLIENT_ID || '1feavcj8qvobr4ltshlgnolg5f',
    },
    rds: {
      host: process.env.RDS_HOST || 'localhost',
      port: rdsPort,
      database: process.env.RDS_DATABASE || 'semisocial',
      user: process.env.RDS_USER || 'postgres',
      password: process.env.RDS_PASSWORD,
      sslMode: process.env.RDS_SSLMODE || 'disable',
    },
    s3: {
      imagesBucket: process.env.S3_IMAGES_BUCKET || 'semisocial-g15-images-581117996165',
      profilePrefix: process.env.S3_PROFILE_PREFIX || 'Fotos_Perfil/public/',
      faceReferencePrefix: process.env.S3_FACE_REFERENCE_PREFIX || 'Fotos_Perfil/references/',
      faceCapturePrefix: process.env.S3_FACE_CAPTURE_PREFIX || 'Fotos_Perfil/captures/',
      postsPrefix: process.env.S3_POSTS_PREFIX || 'Fotos_Publicadas/',
    },
  };
};
