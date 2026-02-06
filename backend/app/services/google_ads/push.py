from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.ad_assets import AdAssets
from app.models.enums import PushStatus, RunStatus
from app.models.google_ads_push import GoogleAdsPush
from app.models.run import Run
from app.services.analysis.qa import qa_rsa_sets

log = logging.getLogger("google_ads")


def _has_google_ads_creds() -> bool:
    return all(
        [
            settings.google_ads_developer_token,
            settings.google_ads_refresh_token,
            settings.google_ads_client_id,
            settings.google_ads_client_secret,
        ]
    )


def _pick_assets(assets: dict[str, Any]) -> tuple[list[str], list[str]]:
    # Expect assets like {"rsa_sets":[{headlines,descriptions,...}], "final": ...}
    rsa_sets = assets.get("rsa_sets") or []
    if not rsa_sets:
        return [], []
    first = rsa_sets[0]
    return list(first.get("headlines") or []), list(first.get("descriptions") or [])


def dry_run_validate(*, run_id: str, req: dict[str, Any]) -> dict[str, Any]:
    headlines, descriptions = _pick_assets(req.get("assets") or {})
    rsa_sets, qa_report = qa_rsa_sets([{"theme": "Selected", "headlines": headlines, "descriptions": descriptions}])
    local_ok = (
        len(rsa_sets[0]["headlines"]) >= 3
        and len(rsa_sets[0]["descriptions"]) >= 2
        and not qa_report["overall"]["has_policy_flags"]
    )

    request_payload = {"validate_only": True, **req}
    response_payload: dict[str, Any] = {"local_validation_ok": local_ok, "qa_report": qa_report}

    message = None
    ok = local_ok
    status = "dry_run_ok" if local_ok else "failed"

    if not _has_google_ads_creds():
        message = "Google Ads credentials not configured; skipped remote validate_only call."
    else:
        try:
            # Remote validate-only call (optional). If it fails, keep local result but surface error.
            _google_ads_mutate_responsive_search_ad(req=req, run_id=run_id, validate_only=True)
            message = "Dry-run validation passed (local + Google Ads validate_only)."
        except Exception as e:  # noqa: BLE001
            ok = False
            status = "failed"
            message = f"Google Ads validate_only failed: {e}"

    _write_push_row(
        run_id=uuid.UUID(run_id),
        req=req,
        status=PushStatus.dry_run_ok if ok else PushStatus.failed,
        request_payload=request_payload,
        response_payload=response_payload,
    )
    return {"ok": ok, "status": status, "message": message, "request_payload": request_payload, "response_payload": response_payload}


def push_live(*, run_id: str, req: dict[str, Any]) -> dict[str, Any]:
    rid = uuid.UUID(run_id)
    if not _has_google_ads_creds():
        _write_push_row(
            run_id=rid,
            req=req,
            status=PushStatus.failed,
            request_payload={"validate_only": False, **req},
            response_payload={"error": "missing Google Ads credentials"},
        )
        return {"ok": False, "status": "failed", "message": "Google Ads credentials not configured."}

    # Gate: record approved selection into ad_assets.final_selection
    db: Session = SessionLocal()
    try:
        run = db.get(Run, rid)
        if not run:
            return {"ok": False, "status": "failed", "message": "run not found"}
        run.status = RunStatus.pushing
        db.add(run)
        db.commit()

        ad_assets = (
            db.query(AdAssets).filter(AdAssets.run_id == rid).order_by(AdAssets.created_at.desc()).first()
        )
        if ad_assets:
            ad_assets.final_selection = req.get("assets") or {}
            db.add(ad_assets)
            db.commit()

        resp = _google_ads_mutate_responsive_search_ad(req=req, run_id=run_id, validate_only=False)
        _write_push_row(
            run_id=rid,
            req=req,
            status=PushStatus.pushed,
            request_payload={"validate_only": False, **req},
            response_payload=resp,
        )
        run.status = RunStatus.complete
        db.add(run)
        db.commit()
        return {"ok": True, "status": "pushed", "message": "Pushed to Google Ads.", "request_payload": req, "response_payload": resp}
    except Exception as e:  # noqa: BLE001
        log.exception("push failed")
        try:
            run = db.get(Run, rid)
            if run:
                run.status = RunStatus.failed
                run.error_json = {**(run.error_json or {}), "google_ads_push_error": str(e)}
                db.add(run)
                db.commit()
        except Exception:  # noqa: BLE001
            pass
        _write_push_row(
            run_id=rid,
            req=req,
            status=PushStatus.failed,
            request_payload={"validate_only": False, **req},
            response_payload={"error": str(e)},
        )
        return {"ok": False, "status": "failed", "message": str(e)}
    finally:
        db.close()


def _write_push_row(
    *,
    run_id: uuid.UUID,
    req: dict[str, Any],
    status: PushStatus,
    request_payload: dict[str, Any],
    response_payload: dict[str, Any],
) -> None:
    db: Session = SessionLocal()
    try:
        row = GoogleAdsPush(
            run_id=run_id,
            customer_id=req.get("customer_id", ""),
            campaign_id=req.get("campaign_id", ""),
            ad_group_id=req.get("ad_group_id", ""),
            status=status,
            request_payload=request_payload,
            response_payload=response_payload,
        )
        db.add(row)
        db.commit()
    finally:
        db.close()


def _google_ads_client_config() -> dict[str, Any]:
    return {
        "developer_token": settings.google_ads_developer_token,
        "refresh_token": settings.google_ads_refresh_token,
        "client_id": settings.google_ads_client_id,
        "client_secret": settings.google_ads_client_secret,
        "login_customer_id": settings.google_ads_login_customer_id,
        "use_proto_plus": True,
    }


def _google_ads_mutate_responsive_search_ad(*, req: dict[str, Any], run_id: str, validate_only: bool) -> dict[str, Any]:
    """
    Creates a Responsive Search Ad in the provided ad_group_id.
    Uses validate_only=True for dry-run.
    """
    from google.ads.googleads.client import GoogleAdsClient  # type: ignore
    from google.ads.googleads.errors import GoogleAdsException  # type: ignore

    customer_id = req["customer_id"]
    ad_group_id = req["ad_group_id"]
    final_url = req["final_url"]
    assets = req.get("assets") or {}
    headlines, descriptions = _pick_assets(assets)
    headlines = [h for h in headlines if h][:15]
    descriptions = [d for d in descriptions if d][:4]
    if len(headlines) < 3 or len(descriptions) < 2:
        raise ValueError("Need at least 3 headlines and 2 descriptions for RSA")

    client = GoogleAdsClient.load_from_dict(_google_ads_client_config(), version="v17")
    ad_group_ad_service = client.get_service("AdGroupAdService")
    ad_group_ad_operation = client.get_type("AdGroupAdOperation")

    ad_group_ad = ad_group_ad_operation.create
    ad_group_ad.ad_group = client.get_service("AdGroupService").ad_group_path(customer_id, ad_group_id)
    ad_group_ad.status = client.enums.AdGroupAdStatusEnum.PAUSED

    ad = ad_group_ad.ad
    ad.final_urls.append(final_url)

    rsa = ad.responsive_search_ad
    for h in headlines:
        asset = client.get_type("AdTextAsset")
        asset.text = h
        rsa.headlines.append(asset)
    for d in descriptions:
        asset = client.get_type("AdTextAsset")
        asset.text = d
        rsa.descriptions.append(asset)

    label_resource = _ensure_label(client=client, customer_id=customer_id, label_name=f"run:{run_id}"[:80], validate_only=validate_only)

    try:
        resp = ad_group_ad_service.mutate_ad_group_ads(
            customer_id=customer_id,
            operations=[ad_group_ad_operation],
            validate_only=validate_only,
        )
        ad_group_ad_resource = str(resp.results[0].resource_name) if resp.results else None
        if ad_group_ad_resource and label_resource:
            _apply_label_to_ad_group_ad(
                client=client,
                customer_id=customer_id,
                ad_group_ad_resource=ad_group_ad_resource,
                label_resource=label_resource,
                validate_only=validate_only,
            )
        return {"results": [str(r.resource_name) for r in resp.results], "validate_only": validate_only, "label": label_resource}
    except GoogleAdsException as ex:
        raise RuntimeError(f"{ex.error.code().name}: {ex.failure}") from ex


def _ensure_label(*, client: Any, customer_id: str, label_name: str, validate_only: bool) -> str | None:
    """
    Ensure a Label exists with label_name and return its resource_name.
    In validate_only mode, we still attempt a validate-only create if not found.
    """
    ga_service = client.get_service("GoogleAdsService")
    safe_name = label_name.replace("'", "\\'")
    query = f"SELECT label.resource_name FROM label WHERE label.name = '{safe_name}' LIMIT 1"
    try:
        stream = ga_service.search_stream(customer_id=customer_id, query=query)
        for batch in stream:
            for row in batch.results:
                return str(row.label.resource_name)
    except Exception:
        pass

    try:
        label_service = client.get_service("LabelService")
        op = client.get_type("LabelOperation")
        op.create.name = label_name
        resp = label_service.mutate_labels(customer_id=customer_id, operations=[op], validate_only=validate_only)
        if resp.results:
            return str(resp.results[0].resource_name)
    except Exception:
        return None
    return None


def _apply_label_to_ad_group_ad(
    *,
    client: Any,
    customer_id: str,
    ad_group_ad_resource: str,
    label_resource: str,
    validate_only: bool,
) -> None:
    try:
        svc = client.get_service("AdGroupAdLabelService")
        op = client.get_type("AdGroupAdLabelOperation")
        op.create.ad_group_ad = ad_group_ad_resource
        op.create.label = label_resource
        svc.mutate_ad_group_ad_labels(customer_id=customer_id, operations=[op], validate_only=validate_only)
    except Exception:
        # Label attachment should not block ad creation in validate_only workflows.
        return

