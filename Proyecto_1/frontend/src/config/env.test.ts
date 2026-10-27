import { describe, expect, it } from "vitest";
import { parsePublicEnvironment } from "./env";

const emptyEnvironment = {
  VITE_API_BASE_URL: undefined,
  VITE_UPLOAD_BASE_URL: undefined,
};

describe("configuración pública", () => {
  it("permite omitir endpoints durante el desarrollo con mocks", () => {
    expect(parsePublicEnvironment(emptyEnvironment)).toEqual({
      apiBaseUrl: undefined,
      uploadBaseUrl: undefined,
    });
  });

  it("normaliza el origen ALB y conserva el stage de API Gateway", () => {
    expect(
      parsePublicEnvironment({
        VITE_API_BASE_URL: "https://api.example.test/",
        VITE_UPLOAD_BASE_URL:
          "https://abc.execute-api.us-east-1.amazonaws.com/v1/",
      }),
    ).toEqual({
      apiBaseUrl: "https://api.example.test",
      uploadBaseUrl: "https://abc.execute-api.us-east-1.amazonaws.com/v1",
    });
  });

  it("rechaza rutas en el ALB, HTTP público y URLs con credenciales", () => {
    for (const invalidUrl of [
      "https://api.example.test/api/v1",
      "http://api.example.test",
      "https://user:password@api.example.test",
    ]) {
      expect(() =>
        parsePublicEnvironment({
          VITE_API_BASE_URL: invalidUrl,
          VITE_UPLOAD_BASE_URL: "https://uploads.example.test/v1",
        }),
      ).toThrow("Revisa VITE_API_BASE_URL");
    }
  });

  it("rechaza query strings y HTTP público en la URL de upload", () => {
    for (const uploadUrl of [
      "http://uploads.example.test/v1",
      "https://uploads.example.test/v1?override=1",
    ]) {
      expect(() =>
        parsePublicEnvironment({
          VITE_API_BASE_URL: "https://api.example.test",
          VITE_UPLOAD_BASE_URL: uploadUrl,
        }),
      ).toThrow("Revisa VITE_API_BASE_URL");
    }
  });
});
