import * as dotenv from 'dotenv';

// Local gateway settings take precedence; the project-level file is a fallback.
dotenv.config();
dotenv.config({ path: '../.env', override: false });

export const config = {
  PORT: Number(process.env.PORT || 8001),
  REDIS_URL: process.env.REDIS_URL || 'redis://localhost:6379/0',
  REDIS_HOST: process.env.REDIS_HOST || 'localhost',
  REDIS_PORT: Number(process.env.REDIS_PORT || 6379),
  JWT_SECRET_KEY: process.env.JWT_SECRET_KEY || 'dev_insecure_jwt_secret_healthcare_platform_2026_change_in_prod',
  JWT_ALGORITHM: process.env.JWT_ALGORITHM || 'HS256',
};
