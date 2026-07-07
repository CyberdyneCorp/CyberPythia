import { env } from '$env/dynamic/public';

export const config = {
  apiBaseUrl: env.PUBLIC_API_BASE_URL ?? 'http://localhost:8000',
  authIssuer: env.PUBLIC_AUTH_ISSUER ?? 'https://auth.backend.coolify.cyberdynecorp.ai',
  authClientId: env.PUBLIC_AUTH_CLIENT_ID ?? 'mnemosyne-web',
  requiredEntitlement: env.PUBLIC_REQUIRED_ENTITLEMENT ?? 'mnemosyne'
};
