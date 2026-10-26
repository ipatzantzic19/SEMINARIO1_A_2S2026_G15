'use strict';

const { CognitoJwtVerifier } = require('aws-jwt-verify');
const {
  JwtInvalidClaimError,
  JwtInvalidSignatureAlgorithmError,
  JwtInvalidSignatureError,
  JwtParseError,
  ParameterValidationError,
  JwtWithoutValidKidError,
  KidNotFoundInJwksError,
  WaitPeriodNotYetEndedJwkError,
} = require('aws-jwt-verify/error');
const { CONFIG } = require('./config');

function createJwtVerifier({
  userPoolId = CONFIG.userPoolId,
  appClientId = CONFIG.appClientId,
} = {}) {
  if (!userPoolId || !appClientId) return null;

  try {
    // La instancia conserva la caché JWKS entre invocaciones de la misma Lambda.
    return CognitoJwtVerifier.create({
      userPoolId,
      clientId: appClientId,
      tokenUse: 'access',
      graceSeconds: 0,
    });
  } catch {
    // Una configuración inválida no debe impedir OPTIONS ni habilitar un bypass.
    return null;
  }
}

function isInvalidJwtError(error) {
  return [
    JwtInvalidClaimError,
    JwtInvalidSignatureAlgorithmError,
    JwtInvalidSignatureError,
    JwtParseError,
    // Con la configuración ya validada, la biblioteca utiliza este error
    // para un issuer ausente o que no corresponde al pool configurado.
    ParameterValidationError,
    JwtWithoutValidKidError,
    KidNotFoundInJwksError,
    WaitPeriodNotYetEndedJwkError,
  ].some((ErrorType) => error instanceof ErrorType);
}

module.exports = { createJwtVerifier, isInvalidJwtError };
