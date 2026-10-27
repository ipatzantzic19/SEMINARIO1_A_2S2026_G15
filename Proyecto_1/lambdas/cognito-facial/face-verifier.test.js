const test = require('node:test');
const assert = require('node:assert/strict');
const { verifyFaceChallenge } = require('./face-verifier');
const { buildHandlers } = require('./index');

function scenario(compareFaces) {
  const deleted = [];
  const warnings = [];
  const args = {
    subject: 'subject',
    challenge: { subject: 'subject', challengeId: 'challenge', expiresAt: 2000 },
    captureKey: 'Fotos_Perfil/captures/challenge/capture.png',
    referenceKey: 'Fotos_Perfil/references/subject/reference.png',
    s3: 'bucket', rekognition: { compareFaces },
    deleteCapture: async key => deleted.push(key),
    now: () => 1000,
    logger: { warn: value => warnings.push(JSON.parse(value)) },
  };
  return { args, deleted, warnings };
}

for (const name of ['InvalidParameterException', 'InvalidImageFormatException', 'ImageTooLargeException']) {
  test(`${name}: rechaza la imagen sin lanzar error y elimina la captura`, async () => {
    const error = Object.assign(new Error('No divulgar información interna'), { name });
    const { args, deleted, warnings } = scenario(async () => { throw error; });
    assert.equal(await verifyFaceChallenge(args), false);
    assert.deepEqual(deleted, [args.captureKey]);
    assert.deepEqual(warnings, [{ event: 'face.image_rejected', reason: name }]);
    assert.ok(!JSON.stringify(warnings).includes(args.referenceKey));
  });
}

for (const name of ['AccessDeniedException', 'InvalidS3ObjectException', 'ThrottlingException', 'InternalServerError', 'UnexpectedError']) {
  test(`${name}: conserva el fallo de infraestructura y elimina la captura`, async () => {
    const error = Object.assign(new Error('Error de prueba'), { name });
    const { args, deleted, warnings } = scenario(async () => { throw error; });
    await assert.rejects(verifyFaceChallenge(args), error);
    assert.deepEqual(deleted, [args.captureKey]);
    assert.deepEqual(warnings, []);
  });
}

test('una coincidencia válida sigue aceptándose y la captura se elimina', async () => {
  const { args, deleted } = scenario(async () => ({ FaceMatches: [{ Similarity: 99 }] }));
  assert.equal(await verifyFaceChallenge(args), true);
  assert.deepEqual(deleted, [args.captureKey]);
});

test('una similitud insuficiente sigue rechazándose', async () => {
  const { args } = scenario(async () => ({ FaceMatches: [{ Similarity: 70 }] }));
  assert.equal(await verifyFaceChallenge(args), false);
});

test('un error al eliminar la captura no queda oculto por el rechazo de imagen', async () => {
  const { args } = scenario(async () => { throw Object.assign(new Error(), { name: 'InvalidParameterException' }); });
  const error = new Error('Falló la eliminación');
  args.deleteCapture = async () => { throw error; };
  await assert.rejects(verifyFaceChallenge(args), error);
});

test('una captura ajena nunca se compara ni se elimina', async () => {
  let calls = 0;
  const { args, deleted } = scenario(async () => { calls++; return {}; });
  args.captureKey = 'Fotos_Perfil/captures/other/capture.png';
  assert.equal(await verifyFaceChallenge(args), false);
  assert.equal(calls, 0);
  assert.deepEqual(deleted, []);
});

test('el rechazo por ausencia de rostro llega a Cognito como answerCorrect=false', async () => {
  const { args } = scenario(async () => { throw Object.assign(new Error(), { name: 'InvalidParameterException' }); });
  const handlers = buildHandlers({
    now: () => 1000,
    verifyFace: input => verifyFaceChallenge({ ...args, ...input }),
  });
  const event = await handlers.verifyAuthChallengeResponse({ request: {
    privateChallengeParameters: { challenge: JSON.stringify({ ...args.challenge, referenceKey: args.referenceKey }) },
    challengeAnswer: JSON.stringify({ challengeId: 'challenge', purpose: 'faceCapture', captureKey: args.captureKey }),
  } });
  assert.equal(event.response.answerCorrect, false);
});
