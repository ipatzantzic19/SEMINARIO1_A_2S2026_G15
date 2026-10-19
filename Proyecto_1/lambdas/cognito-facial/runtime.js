const { S3Client, DeleteObjectCommand } = require('@aws-sdk/client-s3');
const { RekognitionClient, CompareFacesCommand } = require('@aws-sdk/client-rekognition');
const { buildHandlers } = require('./index');
const { verifyFaceChallenge } = require('./face-verifier');

const bucket = process.env.S3_IMAGES_BUCKET || 'semisocial-g15-images-581117996165';
const region = process.env.AWS_REGION || 'us-east-1';
const s3Client = new S3Client({ region });
const rekognitionClient = new RekognitionClient({ region });

async function verifyFace(args) {
  return verifyFaceChallenge({
    ...args,
    s3: bucket,
    rekognition: {
      compareFaces: async (input) => rekognitionClient.send(new CompareFacesCommand(input)),
    },
    deleteCapture: (key) => s3Client.send(new DeleteObjectCommand({ Bucket: bucket, Key: key })),
  });
}

const handlers = buildHandlers({ verifyFace });

module.exports = {
  defineAuthChallenge: handlers.defineAuthChallenge,
  createAuthChallenge: handlers.createAuthChallenge,
  verifyAuthChallengeResponse: handlers.verifyAuthChallengeResponse,
};
