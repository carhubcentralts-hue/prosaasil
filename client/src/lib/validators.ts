import { z } from "zod";

export const emailSchema = z.string().trim().toLowerCase().email("אימייל לא חוקי");
export const passwordSchema = z.string().min(8, "סיסמה חייבת 8 תווים ומעלה");