import { z } from "zod";

export const imageSchema = z
  .custom<File>((value) => value instanceof File, "Selecciona una imagen.")
  .refine(
    (file) => ["image/jpeg", "image/png", "image/webp"].includes(file.type),
    "Usa JPEG, PNG o WebP.",
  )
  .refine(
    (file) => file.size <= 5_242_880,
    "La imagen debe pesar 5 MiB o menos.",
  );
