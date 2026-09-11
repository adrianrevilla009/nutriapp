import { beforeEach, describe, expect, it } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { axe } from "jest-axe";
import { server } from "../msw-server";
import { renderWithProviders } from "./test-utils";
import { PhotoUploadForm } from "@/components/features/recognition/PhotoUploadForm";
import {
  analyzePhotoDetectedFixture,
  analyzePhotoUnavailableFixture,
} from "../fixtures/food-recognition.fixtures";
import { setAccessToken } from "@/lib/session";

function mockAuthenticatedSession() {
  server.use(
    http.post("/api/auth/refresh", () =>
      HttpResponse.json({ access_token: "fixture-access-token", token_type: "bearer" }),
    ),
  );
}

function jpegFile(name = "meal.jpg", sizeBytes = 100): File {
  return new File([new Uint8Array(sizeBytes)], name, { type: "image/jpeg" });
}

describe("PhotoUploadForm", () => {
  beforeEach(() => {
    setAccessToken(null);
    mockAuthenticatedSession();
  });

  it("renders a real, labeled file input", () => {
    renderWithProviders(<PhotoUploadForm />);
    expect(screen.getByLabelText(/photo of your food/i)).toBeInTheDocument();
  });

  it("blocks submission client-side with no file selected, making zero network calls", async () => {
    let callCount = 0;
    server.use(
      http.post("/api/food-recognition/photos/analyze", () => {
        callCount += 1;
        return HttpResponse.json(analyzePhotoDetectedFixture);
      }),
    );
    const user = userEvent.setup();
    renderWithProviders(<PhotoUploadForm />);
    await user.click(screen.getByRole("button", { name: /analyze photo/i }));

    expect(await screen.findByText(/choose a photo/i)).toBeInTheDocument();
    expect(callCount).toBe(0);
  });

  it("blocks an unsupported file type client-side, making zero network calls", async () => {
    // applyAccept: false -- the OS/browser file picker's own `accept`
    // filtering is a hint, not a guarantee (some pickers offer "All
    // Files", and drag-and-drop bypasses it entirely), so this app's own
    // defensive check must still catch a mismatched file that reaches
    // the input despite the accept attribute -- this test simulates
    // exactly that, bypassing user-event's own default accept-aware
    // filtering to actually exercise it.
    let callCount = 0;
    server.use(
      http.post("/api/food-recognition/photos/analyze", () => {
        callCount += 1;
        return HttpResponse.json(analyzePhotoDetectedFixture);
      }),
    );
    const user = userEvent.setup({ applyAccept: false });
    renderWithProviders(<PhotoUploadForm />);
    const heicFile = new File([new Uint8Array(10)], "meal.heic", { type: "image/heic" });
    await user.upload(screen.getByLabelText(/photo of your food/i), heicFile);
    await user.click(screen.getByRole("button", { name: /analyze photo/i }));

    expect(await screen.findByText(/jpeg, png, or webp/i)).toBeInTheDocument();
    expect(callCount).toBe(0);
  });

  it("blocks an oversized file client-side, making zero network calls", async () => {
    let callCount = 0;
    server.use(
      http.post("/api/food-recognition/photos/analyze", () => {
        callCount += 1;
        return HttpResponse.json(analyzePhotoDetectedFixture);
      }),
    );
    const user = userEvent.setup();
    renderWithProviders(<PhotoUploadForm />);
    const oversized = jpegFile("big.jpg", 8 * 1024 * 1024 + 1);
    await user.upload(screen.getByLabelText(/photo of your food/i), oversized);
    await user.click(screen.getByRole("button", { name: /analyze photo/i }));

    expect(await screen.findByText(/too large/i)).toBeInTheDocument();
    expect(callCount).toBe(0);
  });

  it("happy path: submits the selected photo and renders the detected candidates", async () => {
    server.use(
      http.post("/api/food-recognition/photos/analyze", () =>
        HttpResponse.json(analyzePhotoDetectedFixture),
      ),
    );
    const user = userEvent.setup();
    renderWithProviders(<PhotoUploadForm />);
    await user.upload(screen.getByLabelText(/photo of your food/i), jpegFile());
    await user.click(screen.getByRole("button", { name: /analyze photo/i }));

    expect(await screen.findByRole("heading", { level: 2 })).toHaveTextContent(/possible match/i);
    expect(screen.getAllByRole("listitem")).toHaveLength(3);
  });

  it("a 200 'unavailable' response renders the honest fallback state, not an error banner, plus the manual-search link", async () => {
    server.use(
      http.post("/api/food-recognition/photos/analyze", () =>
        HttpResponse.json(analyzePhotoUnavailableFixture),
      ),
    );
    const user = userEvent.setup();
    renderWithProviders(<PhotoUploadForm />);
    await user.upload(screen.getByLabelText(/photo of your food/i), jpegFile());
    await user.click(screen.getByRole("button", { name: /analyze photo/i }));

    expect(await screen.findByText(/couldn't analyze this photo/i)).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: /search manually/i })).toBeInTheDocument();
  });

  it("a mocked network failure shows a retry-able error state", async () => {
    server.use(http.post("/api/food-recognition/photos/analyze", () => HttpResponse.error()));
    const user = userEvent.setup();
    renderWithProviders(<PhotoUploadForm />);
    await user.upload(screen.getByLabelText(/photo of your food/i), jpegFile());
    await user.click(screen.getByRole("button", { name: /analyze photo/i }));

    expect(await screen.findByRole("alert")).toBeInTheDocument();
  });

  it("has no critical/serious axe violations in the initial state", async () => {
    const { container } = renderWithProviders(<PhotoUploadForm />);
    expect(await axe(container)).toHaveNoViolations();
  });

  it("has no critical/serious axe violations in the detected-candidates state", async () => {
    server.use(
      http.post("/api/food-recognition/photos/analyze", () =>
        HttpResponse.json(analyzePhotoDetectedFixture),
      ),
    );
    const user = userEvent.setup();
    const { container } = renderWithProviders(<PhotoUploadForm />);
    await user.upload(screen.getByLabelText(/photo of your food/i), jpegFile());
    await user.click(screen.getByRole("button", { name: /analyze photo/i }));
    await screen.findByRole("heading", { level: 2 });

    expect(await axe(container)).toHaveNoViolations();
  });
});
