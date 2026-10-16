'use strict';

const CONFIG = {
  bucket: process.env.S3_IMAGES_BUCKET || 'semisocial-g15-images-581117996165',
  region: process.env.AWS_REGION || 'us-east-1',
  profilePublicPrefix: process.env.S3_PROFILE_PREFIX || 'Fotos_Perfil/public/',
  profileReferencePrefix: process.env.S3_FACE_REFERENCE_PREFIX || 'Fotos_Perfil/references/',
  faceCapturePrefix: process.env.S3_FACE_CAPTURE_PREFIX || 'Fotos_Perfil/captures/',
  postsPrefix: process.env.S3_POSTS_PREFIX || 'Fotos_Publicadas/',
  maxSizeBytes: 5 * 1024 * 1024, // 5 MiB (5,242,880 bytes)
  allowedMimes: ['image/jpeg', 'image/png', 'image/webp'],
  allowedPurposes: ['profile', 'post', 'faceCapture'],
};

function getS3BaseUrl(bucket = CONFIG.bucket, region = CONFIG.region) {
  return `https://${bucket}.s3.${region}.amazonaws.com/`;
}

module.exports = {
  CONFIG,
  getS3BaseUrl,
};
