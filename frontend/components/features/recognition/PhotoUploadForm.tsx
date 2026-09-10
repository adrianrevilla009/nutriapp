"use client";

import { useId, useState, type FormEvent } from "react";
import { useTranslations } from "next-intl";
import { useAnalyzePhoto } from "@/lib/hooks/useAnalyzePhoto";
import {
  ACCEPTED_IMAGE_ACCEPT_ATTR,
  ACCEPTED_IMAGE_TYPES,
  MAX_UPLOAD_BYTES,
} from "@/lib/photo-upload-constraints";
import { Button } from "@/components/ui/Button";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { CandidateList } from "@/components/features/recognition/CandidateList";

/**
 * The upload affordance is a plain, labeled `<input type="file">` --
 * inherently keyboard-operable, no drag-and-drop layered on top this pass
 * (accessibility-standards SKILL.md: a real alternative to drag-and-drop
 * would otherwise be required; the plain input is the only affordance,
 * not a secondary one, so that requirement doesn't apply -- implementation
 * plan section 6).
 */
export function PhotoUploadForm() {
  const t = useTranslations("photoLog");
  const tCommon = useTranslations("common");
  const fileErrorId = useId();

  const [fileError, setFileError] = useState<string | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);

  const mutation = useAnalyzePhoto();

  function handleFileChange(event: React.ChangeEvent<HTMLInputElement>) {
    setFileError(null);
    const file = event.target.files?.[0] ?? null;
    setSelectedFile(file);
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setFileError(null);

    if (!selectedFile) {
      setFileError(t("noFileSelected"));
      return; // Blocked client-side -- no network call.
    }
    if (!ACCEPTED_IMAGE_TYPES.includes(selectedFile.type)) {
      setFileError(t("unsupportedFileType"));
      return; // Blocked client-side -- no network call.
    }
    if (selectedFile.size > MAX_UPLOAD_BYTES) {
      setFileError(t("fileTooLarge"));
      return; // Blocked client-side -- no network call.
    }

    mutation.mutate(selectedFile);
  }

  if (mutation.isSuccess) {
    return <CandidateList result={mutation.data} />;
  }

  return (
    <div className="page">
      <h1>{t("uploadTitle")}</h1>
      <p>{t("uploadIntro")}</p>
      <form onSubmit={handleSubmit} noValidate>
        {mutation.isError ? (
          <ErrorBanner
            message={
              mutation.error instanceof Error ? mutation.error.message : tCommon("genericError")
            }
          />
        ) : null}
        <div className="field">
          <label htmlFor="photo-upload-input">{t("fileInputLabel")}</label>
          <input
            id="photo-upload-input"
            type="file"
            accept={ACCEPTED_IMAGE_ACCEPT_ATTR}
            onChange={handleFileChange}
            aria-describedby={fileError ? fileErrorId : undefined}
            aria-invalid={fileError ? true : undefined}
          />
          {fileError ? (
            <p id={fileErrorId} role="alert" className="field-error">
              {fileError}
            </p>
          ) : null}
        </div>
        <Button type="submit" disabled={mutation.isPending}>
          {mutation.isPending ? t("analyzing") : t("analyzeSubmit")}
        </Button>
      </form>
      <p>
        <a href="/search">{t("searchManually")}</a>
      </p>
    </div>
  );
}
