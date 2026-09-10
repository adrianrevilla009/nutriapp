/**
 * Shared between the client-side PhotoUploadForm validation and the
 * app/api/food-recognition/photos/analyze Route Handler's own defense-in-
 * depth check (journey 2 implementation plan resolution 4) -- one source
 * of truth for both, rather than two constants that could silently drift.
 * food-recognition-service itself enforces no upload size limit (confirmed
 * by reading its recognition_routes.py/analyze_food_photo.py -- only a
 * content-type and non-empty check), so this is a frontend-only
 * mitigation, a guessed-reasonable default, not a backend contract.
 */
export const MAX_UPLOAD_BYTES = 8 * 1024 * 1024;

// Deliberately narrower than the backend's bare `content_type.startswith("image/")`
// check -- steers the browser's file picker away from formats (notably
// HEIC, the iPhone camera default) that may pass that check but aren't
// reliably supported by the Claude vision API (implementation plan
// resolution 5). No client-side transcoding is attempted.
export const ACCEPTED_IMAGE_TYPES = ["image/jpeg", "image/png", "image/webp"];
export const ACCEPTED_IMAGE_ACCEPT_ATTR = ACCEPTED_IMAGE_TYPES.join(",");
