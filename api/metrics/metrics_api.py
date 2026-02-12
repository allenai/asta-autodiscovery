"""Flask blueprint for the metrics dashboard API.

All endpoints require the `enroll:autodiscovery_admin` permission.
"""

from __future__ import annotations

import logging

from flask import Blueprint, jsonify, request

from utils.auth import requires_auth

from .aggregator import (
    compute_aggregated_usage,
    compute_overview,
    compute_run_metrics,
    compute_user_detail,
    compute_users_list,
    get_metrics_cache,
)

logger = logging.getLogger(__name__)

ADMIN_PERMISSION = "enroll:autodiscovery_admin"


def create() -> Blueprint:
    api = Blueprint("metrics_api", __name__)

    @api.route("/health")
    def health():
        return "", 204

    @api.route("/overview")
    @requires_auth(required_permission=ADMIN_PERMISSION)
    def overview():
        start_date = request.args.get("start_date")
        end_date = request.args.get("end_date")
        metrics = compute_overview(start_date, end_date)
        return jsonify(metrics.model_dump())

    @api.route("/users")
    @requires_auth(required_permission=ADMIN_PERMISSION)
    def users_list():
        start_date = request.args.get("start_date")
        end_date = request.args.get("end_date")
        users = compute_users_list(start_date, end_date)
        cache = get_metrics_cache()
        data = cache.get_data()
        return jsonify({
            "users": [u.model_dump() for u in users],
            "cache_refreshed_at": data.refreshed_at,
        })

    @api.route("/users/<userid>")
    @requires_auth(required_permission=ADMIN_PERMISSION)
    def user_detail(userid: str):
        detail = compute_user_detail(userid)
        return jsonify(detail.model_dump())

    @api.route("/runs/<userid>/<runid>")
    @requires_auth(required_permission=ADMIN_PERMISSION)
    def run_metrics(userid: str, runid: str):
        metrics = compute_run_metrics(userid, runid)
        if metrics is None:
            return jsonify({"error": "Run not found"}), 404
        return jsonify(metrics)

    @api.route("/usage/aggregated")
    @requires_auth(required_permission=ADMIN_PERMISSION)
    def aggregated_usage():
        start_date = request.args.get("start_date")
        end_date = request.args.get("end_date")
        usage = compute_aggregated_usage(start_date, end_date)
        return jsonify(usage.model_dump())

    @api.route("/cache/status")
    @requires_auth(required_permission=ADMIN_PERMISSION)
    def cache_status():
        cache = get_metrics_cache()
        data = cache.get_data()
        unique_users = len({j.userid for j in data.jobs})
        return jsonify({
            "refreshed_at": data.refreshed_at,
            "job_count": len(data.jobs),
            "user_count": unique_users,
            "scan_duration_seconds": data.scan_duration_seconds,
            "is_refreshing": cache.is_refreshing,
        })

    @api.route("/cache/refresh", methods=["POST"])
    @requires_auth(required_permission=ADMIN_PERMISSION)
    def cache_refresh():
        cache = get_metrics_cache()
        cache.force_refresh()
        return jsonify({"status": "refresh_triggered"})

    return api
