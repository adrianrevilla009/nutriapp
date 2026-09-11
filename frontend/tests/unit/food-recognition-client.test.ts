// Stays on this file's default jsdom environment (not Node) deliberately:
// analyzeFoodPhoto calls fetch("/api/...") with a RELATIVE URL, which only
// resolves against jsdom's window.location -- under Node there is no such
// base and the fetch itself fails before ever reaching MSW. The one test
// below that needs to inspect the multipart body reads it via
// request.text() rather than request.formData() specifically to avoid a
// separate, empirically-discovered jsdom issue: its File/Blob
// implementation hangs (not throws) when read back via .formData() inside
// an MSW handler.
import { describe, expect, it } from "vitest";
import { http, HttpResponse } from "msw";
import { server } from "../msw-server";
import { analyzeFoodPhoto, ANALYZE_PHOTO_TIMEOUT_MS } from "@/lib/api/food-recognition";
import { AppError, TimeoutError } from "@/lib/api/http-client";
import { analyzePhotoDetectedFixture } from "../fixtures/food-recognition.fixtures";

function makeFile(): File {
  return new File(["fake-image-bytes"], "meal.jpg", { type: "image/jpeg" });
}

describe("analyzeFoodPhoto", () => {
  it("uses a longer default timeout than http-client's shared 8000ms default", () => {
    expect(ANALYZE_PHOTO_TIMEOUT_MS).toBeGreaterThan(8000);
  });

  it("sends a multipart Content-Type, never JSON -- never sets one manually", async () => {
    // Deliberately does NOT read the request body in this handler (not
    // even via .text()): jsdom's File/Blob implementation hangs, not
    // throws, when a real File-bearing request body is read back inside
    // an MSW handler under this suite's jsdom environment (discovered
    // empirically -- every variant touching the body here timed out at
    // exactly the default 5000ms). The actual field-name/content
    // round-trip through a real FormData IS exercised, under Node's
    // native (non-jsdom) File/Blob/fetch, by
    // tests/integration/route-handlers.test.ts's food-recognition Route
    // Handler cases -- this test only needs to prove the browser-side
    // Content-Type, which reading headers alone (no body access) proves
    // safely.
    let capturedContentType: string | null = null;
    server.use(
      http.post("/api/food-recognition/photos/analyze", ({ request }) => {
        capturedContentType = request.headers.get("Content-Type");
        return HttpResponse.json(analyzePhotoDetectedFixture);
      }),
    );
    await analyzeFoodPhoto(makeFile(), "token-abc");

    // The browser sets its own multipart boundary -- never
    // "application/json" and never omitted entirely.
    expect(capturedContentType).toMatch(/^multipart\/form-data/);
  });

  it("attaches Authorization only when a token is supplied", async () => {
    let capturedAuth: string | null | undefined;
    server.use(
      http.post("/api/food-recognition/photos/analyze", ({ request }) => {
        capturedAuth = request.headers.get("Authorization");
        return HttpResponse.json(analyzePhotoDetectedFixture);
      }),
    );
    await analyzeFoodPhoto(makeFile(), "token-abc");
    expect(capturedAuth).toBe("Bearer token-abc");
  });

  it("parses a successful response against AnalyzePhotoResponseSchema", async () => {
    server.use(
      http.post("/api/food-recognition/photos/analyze", () =>
        HttpResponse.json(analyzePhotoDetectedFixture),
      ),
    );
    const result = await analyzeFoodPhoto(makeFile(), "token-abc");
    expect(result).toEqual(analyzePhotoDetectedFixture);
  });

  it("parses a {error, code} error body into a typed AppError, preserving status", async () => {
    server.use(
      http.post("/api/food-recognition/photos/analyze", () =>
        HttpResponse.json(
          { error: "Photo is too large.", code: "PHOTO_TOO_LARGE" },
          { status: 413 },
        ),
      ),
    );
    await expect(analyzeFoodPhoto(makeFile(), "token-abc")).rejects.toMatchObject({
      message: "Photo is too large.",
      code: "PHOTO_TOO_LARGE",
      status: 413,
    });
  });

  it("falls back to a generic AppError for a non-JSON error body", async () => {
    server.use(
      http.post(
        "/api/food-recognition/photos/analyze",
        () => new HttpResponse("<html>502</html>", { status: 502 }),
      ),
    );
    const error = await analyzeFoodPhoto(makeFile(), "token-abc").catch((e) => e);
    expect(error).toBeInstanceOf(AppError);
    expect((error as AppError).code).toBe("UNKNOWN_ERROR");
  });

  it("aborts and throws TimeoutError when the request exceeds its own configured timeout", async () => {
    server.use(
      http.post("/api/food-recognition/photos/analyze", async () => {
        await new Promise((resolve) => setTimeout(resolve, 50));
        return HttpResponse.json(analyzePhotoDetectedFixture);
      }),
    );
    await expect(analyzeFoodPhoto(makeFile(), "token-abc", 5)).rejects.toBeInstanceOf(TimeoutError);
  });
});
