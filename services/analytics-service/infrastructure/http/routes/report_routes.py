"""`GET /api/v1/analytics/reports/{report_type}` -- **Pro-gated**
(implementation plan section 1 acceptance criterion 4). Response is a CSV
document (resolution 4: CSV only for v1), never JSON, with a leading
manifest comment line stating row count/date range (resolution to the
CSV-manifest question, approved 2026-09-07)."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from application.queries.get_report import GetReportHandler, GetReportQuery
from infrastructure.composition_root import Container, build_repositories
from infrastructure.http.dependencies import get_authenticated_user_id, get_container, get_session
from infrastructure.http.error_mapping import map_exception
from infrastructure.http.schemas.analytics_schemas import ReportRequest

router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])


@router.get(
    "/reports/{report_type}",
    response_model=None,
    summary="Generate/export a CSV report for a date range (Pro-gated)",
)
async def get_report(
    report_type: str,
    user_id: Annotated[uuid.UUID, Depends(get_authenticated_user_id)],
    session: Annotated[AsyncSession, Depends(get_session)],
    container: Annotated[Container, Depends(get_container)],
    request: Annotated[ReportRequest, Query()],
) -> Response | JSONResponse:
    (
        daily_log_summary,
        micronutrient_window,
        _anomaly_alerts,
        entitlement_cache,
        export_audit,
        _outbox,
    ) = build_repositories(session)
    handler = GetReportHandler(
        daily_log_summary,
        micronutrient_window,
        entitlement_cache,
        container.entitlement_check,
        export_audit,
    )
    try:
        result = await handler.handle(
            GetReportQuery(
                user_id=user_id,
                report_type=report_type,
                start_date=request.start_date,
                end_date=request.end_date,
            )
        )
        await session.commit()
    except Exception as exc:  # noqa: BLE001
        return map_exception(exc)
    return Response(
        content=result.csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="analytics_{report_type}.csv"'},
    )
