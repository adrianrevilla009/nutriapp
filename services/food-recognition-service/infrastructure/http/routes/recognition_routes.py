"""POST /api/v1/recognition/photos/analyze and
POST /api/v1/recognition/barcodes/decode -- the two public HTTP routes
this service exposes (implementation plan section 1, acceptance criteria
1 and 3).

Media retention (implementation plan section 1, acceptance criterion 6):
the uploaded image is read into memory (`await file.read()`) and passed
directly to the handler as `bytes` -- it is NEVER written to disk, S3, or
any other blob storage, and goes out of scope (eligible for garbage
collection) the moment this request function returns. No middleware in
this service logs the raw multipart request body (security review point
(a) in implementation plan section 6).
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from application.commands.analyze_food_photo import (
    AnalyzeFoodPhotoCommand,
    AnalyzeFoodPhotoHandler,
)
from application.commands.decode_barcode import DecodeBarcodeCommand, DecodeBarcodeHandler
from application.errors import InvalidImageError
from infrastructure.composition_root import Container, build_repositories
from infrastructure.http.dependencies import (
    get_authenticated_user_id,
    get_container,
    get_correlation_id,
    get_session,
)
from infrastructure.http.error_mapping import map_exception
from infrastructure.http.schemas.recognition_schemas import (
    AnalyzePhotoResponse,
    DecodeBarcodeResponse,
    analyze_result_to_response,
    decode_result_to_response,
)

router = APIRouter(prefix="/api/v1/recognition", tags=["recognition"])


def _read_image_or_raise_content_type_error(file: UploadFile) -> None:
    if file.content_type is None or not file.content_type.startswith("image/"):
        raise InvalidImageError(f"Unsupported content type: {file.content_type!r}")


@router.post(
    "/photos/analyze",
    response_model=AnalyzePhotoResponse,
    summary="Analyze a food photo -- returns up to 3 candidate items with confidence and a "
    "portion-range estimate for user confirmation, never auto-written to diary-service",
)
async def analyze_photo(
    file: Annotated[UploadFile, File(...)],
    session: Annotated[AsyncSession, Depends(get_session)],
    container: Annotated[Container, Depends(get_container)],
    correlation_id: Annotated[str, Depends(get_correlation_id)],
    user_id: Annotated[uuid.UUID, Depends(get_authenticated_user_id)],
) -> AnalyzePhotoResponse | JSONResponse:
    photo_repo, _barcode_repo, outbox_repo = build_repositories(session)
    handler = AnalyzeFoodPhotoHandler(
        vision_port=container.vision_adapter,
        repository=photo_repo,
        outbox_repository=outbox_repo,
        confidence_threshold=container.settings.confidence_threshold,
        feature_enabled=container.settings.photo_analysis_enabled,
    )
    try:
        _read_image_or_raise_content_type_error(file)
        image_bytes = await file.read()
        result = await handler.handle(
            AnalyzeFoodPhotoCommand(
                user_id=user_id, image_bytes=image_bytes, correlation_id=correlation_id
            )
        )
        await session.commit()
    except Exception as exc:  # noqa: BLE001
        await session.rollback()
        return map_exception(exc)
    return analyze_result_to_response(result)


@router.post(
    "/barcodes/decode",
    response_model=DecodeBarcodeResponse,
    summary="Decode a barcode from a photo and look up the matching catalog-service product",
)
async def decode_barcode(
    file: Annotated[UploadFile, File(...)],
    session: Annotated[AsyncSession, Depends(get_session)],
    container: Annotated[Container, Depends(get_container)],
    correlation_id: Annotated[str, Depends(get_correlation_id)],
    user_id: Annotated[uuid.UUID, Depends(get_authenticated_user_id)],
) -> DecodeBarcodeResponse | JSONResponse:
    _photo_repo, barcode_repo, _outbox_repo = build_repositories(session)
    handler = DecodeBarcodeHandler(
        barcode_decoder=container.barcode_decoder,
        catalog_lookup=container.catalog_lookup_client,
        repository=barcode_repo,
    )
    try:
        _read_image_or_raise_content_type_error(file)
        image_bytes = await file.read()
        result = await handler.handle(
            DecodeBarcodeCommand(
                user_id=user_id, image_bytes=image_bytes, correlation_id=correlation_id
            )
        )
        await session.commit()
    except Exception as exc:  # noqa: BLE001
        await session.rollback()
        return map_exception(exc)
    return decode_result_to_response(result)
