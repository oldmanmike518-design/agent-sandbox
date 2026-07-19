from __future__ import annotations

import html as html_mod
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.models.agent import Agent
from app.models.verification import (
    VerificationReport,
    VerificationReportPublication,
)
from app.services.auth import get_current_agent
from app.services.verification.evaluators import CHECK_IDS
from app.utils.time import utc_now

router = APIRouter(prefix="/reports")
STALE_AFTER_DAYS = 90


def badge_payload(report: VerificationReport) -> dict:
    stale = (
        utc_now() - report.verified_at
        > timedelta(days=STALE_AFTER_DAYS)
    )
    if not report.complete:
        message, color = "incomplete", "lightgrey"
    else:
        message = (
            f"{report.passed}/{report.passed + report.failed} · "
            f"{report.verified_at.date().isoformat()}"
        )
        color = (
            "lightgrey"
            if stale
            else ("brightgreen" if report.failed == 0 else "orange")
        )
    return {
        "schemaVersion": 1,
        "label": (
            f"interop {report.profile} v{report.spec_version}"
        ),
        "message": message,
        "color": color,
        "cacheSeconds": 3600,
    }


def badge_svg(report: VerificationReport) -> str:
    payload = badge_payload(report)
    label = payload["label"]
    message = payload["message"]
    color = payload["color"]
    colors = {
        "brightgreen": "#4c1",
        "orange": "#fe7d37",
        "lightgrey": "#9f9f9f",
    }
    left_width = 6 * len(label) + 10
    right_width = 6 * len(message) + 10
    total = left_width + right_width
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{total}" '
        'height="20" role="img">'
        f'<rect width="{left_width}" height="20" fill="#555"/>'
        f'<rect x="{left_width}" width="{right_width}" height="20" '
        f'fill="{colors[color]}"/>'
        '<g fill="#fff" font-family="Verdana,sans-serif" font-size="11">'
        f'<text x="{left_width / 2}" y="14" text-anchor="middle">'
        f"{html_mod.escape(label)}</text>"
        f'<text x="{left_width + right_width / 2}" y="14" '
        f'text-anchor="middle">{html_mod.escape(message)}</text>'
        "</g></svg>"
    )


def render_report_html(report: VerificationReport) -> str:
    name = html_mod.escape(report.agent_name_snapshot)
    framework = html_mod.escape(
        report.framework_self_reported or "not reported"
    )
    rows = "".join(
        "<tr><td><code>"
        f"{html_mod.escape(check)}</code></td><td>"
        f"{html_mod.escape(report.results[check]['state'])}</td></tr>"
        for check in CHECK_IDS
        if check in report.results
    )
    if report.complete:
        summary = (
            f"{report.passed}/{report.passed + report.failed} "
            "checks passed"
        )
    else:
        summary = (
            f"{report.passed} PASS · {report.failed} FAIL · "
            f"{report.not_observed} NOT_OBSERVED — INCOMPLETE"
        )
    fault = (
        "<p><strong>Verifier fault:</strong> this run was affected by a "
        "verifier-side failure; it does not count against the agent.</p>"
        if report.verifier_fault
        else ""
    )
    return (
        "<!doctype html><html><head><meta charset=\"utf-8\">"
        f"<title>Interop Report — {name}</title></head><body>"
        "<h1>Agent Sandbox Interop Report</h1>"
        f"<p><strong>Agent:</strong> {name} · "
        "<strong>Framework (self-reported):</strong> "
        f"{framework}</p><p><strong>Profile:</strong> "
        f"{html_mod.escape(report.profile)} v"
        f"{html_mod.escape(report.spec_version)} · "
        f"<strong>Verified:</strong> "
        f"{report.verified_at.date().isoformat()}</p>"
        f"<p><strong>Result:</strong> {summary}</p>{fault}"
        "<table border=\"1\" cellpadding=\"6\"><tr><th>Check</th>"
        f"<th>State</th></tr>{rows}</table><p><small>"
        f"Spec SHA-256: <code>{report.spec_sha256}</code> · "
        f"Engine: <code>{html_mod.escape(report.engine_commit)}</code> · "
        f"Report schema v{report.report_schema_version}. Independence of "
        "any observed counterparties is presumed, not verified."
        "</small></p></body></html>"
    )


TAKEDOWN_HTML = (
    "<!doctype html><html><head><meta charset=\"utf-8\">"
    "<title>Report unavailable</title></head><body>"
    "<h1>Report unavailable</h1><p>This verification report was removed "
    "by the operator.</p></body></html>"
)


async def _report_with_publication(
    session: AsyncSession, slug: str
) -> tuple[VerificationReport, VerificationReportPublication]:
    row = (
        await session.execute(
            select(
                VerificationReport,
                VerificationReportPublication,
            )
            .join(
                VerificationReportPublication,
                VerificationReportPublication.report_id
                == VerificationReport.id,
            )
            .where(VerificationReport.slug == slug)
        )
    ).one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Report not found")
    return row[0], row[1]


async def _visible_report(
    session: AsyncSession, slug: str
) -> VerificationReport:
    report, publication = await _report_with_publication(session, slug)
    if publication.disabled:
        raise HTTPException(
            status_code=410,
            detail="Report removed by the operator",
        )
    return report


@router.get("")
async def report_index(
    session: AsyncSession = Depends(get_session),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    rows = (
        (
            await session.execute(
                select(VerificationReport)
                .join(
                    VerificationReportPublication,
                    VerificationReportPublication.report_id
                    == VerificationReport.id,
                )
                .where(
                    VerificationReportPublication.listed.is_(True),
                    VerificationReportPublication.disabled.is_(False),
                )
                .order_by(VerificationReport.verified_at.desc())
                .offset(offset)
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )
    return {
        "items": [
            {
                "slug": report.slug,
                "agent_name": report.agent_name_snapshot,
                "profile": report.profile,
                "spec_version": report.spec_version,
                "passed": report.passed,
                "failed": report.failed,
                "complete": report.complete,
                "verified_at": report.verified_at,
            }
            for report in rows
        ]
    }


@router.get("/{slug}.json")
async def report_json(
    slug: str, session: AsyncSession = Depends(get_session)
):
    report = await _visible_report(session, slug)
    return {
        "slug": report.slug,
        "agent_name": report.agent_name_snapshot,
        "framework_self_reported": report.framework_self_reported,
        "profile": report.profile,
        "spec_version": report.spec_version,
        "spec_sha256": report.spec_sha256,
        "engine_commit": report.engine_commit,
        "report_schema_version": report.report_schema_version,
        "results": report.results,
        "passed": report.passed,
        "failed": report.failed,
        "not_observed": report.not_observed,
        "complete": report.complete,
        "verifier_fault": report.verifier_fault,
        "verified_at": report.verified_at,
    }


@router.get("/{slug}/badge.json")
async def report_badge(
    slug: str, session: AsyncSession = Depends(get_session)
):
    return badge_payload(await _visible_report(session, slug))


@router.get("/{slug}/badge.svg")
async def report_badge_svg(
    slug: str, session: AsyncSession = Depends(get_session)
):
    svg = badge_svg(await _visible_report(session, slug))
    return Response(content=svg, media_type="image/svg+xml")


@router.put("/{slug}/listing")
async def list_report(
    slug: str,
    agent: Agent = Depends(get_current_agent),
    session: AsyncSession = Depends(get_session),
):
    report, publication = await _report_with_publication(session, slug)
    if report.agent_id != agent.id:
        raise HTTPException(status_code=404, detail="Report not found")
    if publication.disabled:
        raise HTTPException(
            status_code=410,
            detail="Report removed by the operator",
        )
    publication.listed = True
    publication.updated_at = utc_now()
    await session.commit()
    return {"slug": slug, "listed": True}


@router.delete("/{slug}/listing")
async def unlist_report(
    slug: str,
    agent: Agent = Depends(get_current_agent),
    session: AsyncSession = Depends(get_session),
):
    report, publication = await _report_with_publication(session, slug)
    if report.agent_id != agent.id:
        raise HTTPException(status_code=404, detail="Report not found")
    publication.listed = False
    publication.updated_at = utc_now()
    await session.commit()
    return {"slug": slug, "listed": False}


@router.get("/{slug}", response_class=HTMLResponse)
async def report_page(
    slug: str, session: AsyncSession = Depends(get_session)
):
    report, publication = await _report_with_publication(session, slug)
    if publication.disabled:
        return HTMLResponse(TAKEDOWN_HTML, status_code=410)
    return HTMLResponse(render_report_html(report))
