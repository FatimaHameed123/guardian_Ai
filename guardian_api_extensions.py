"""
New API routes for heatmap, analytics, and enhanced prediction.
Register on existing Flask app — does not modify security/auth modules.
"""

from __future__ import annotations

from pathlib import Path

from flask import jsonify, request

ROOT = Path(__file__).resolve().parent
ML_DIR = ROOT / "ml"
DB_PATH = ROOT / "CriminalInvestigation_Secured.db"


def register_extension_routes(app, sanitize_input, limiter=None):
    """Attach heatmap + analytics routes to the secured Flask app."""

    import sys
    if str(ML_DIR) not in sys.path:
        sys.path.insert(0, str(ML_DIR))

    from heatmap_service import get_analytics_summary, get_heatmap_points, invalidate_heatmap_cache

    def _apply_limit(rule):
        return limiter.limit(rule) if limiter else lambda f: f

    @_apply_limit("60 per minute")
    @app.route("/api/heatmap", methods=["GET"])
    def api_heatmap():
        area = sanitize_input(request.args.get("area", ""), 50) or None
        crime_type = sanitize_input(request.args.get("crime_type", ""), 80) or None
        date_from = sanitize_input(request.args.get("date_from", ""), 20) or None
        date_to = sanitize_input(request.args.get("date_to", ""), 20) or None
        refresh = request.args.get("refresh", "").lower() in ("1", "true", "yes")
        data = get_heatmap_points(
            db_path=DB_PATH,
            area=area,
            crime_type=crime_type,
            date_from=date_from,
            date_to=date_to,
            refresh=refresh,
        )
        return jsonify(data)

    @_apply_limit("60 per minute")
    @app.route("/api/analytics/dashboard", methods=["GET"])
    def api_analytics_dashboard():
        return jsonify(get_analytics_summary(db_path=DB_PATH))

    @_apply_limit("60 per minute")
    @app.route("/api/analytics/trends", methods=["GET"])
    def api_analytics_trends():
        summary = get_analytics_summary(db_path=DB_PATH)
        return jsonify({
            "status": "ok",
            "monthly_trend": summary.get("monthly_trend", []),
        })

    @_apply_limit("60 per minute")
    @app.route("/api/analytics/areas", methods=["GET"])
    def api_analytics_areas():
        summary = get_analytics_summary(db_path=DB_PATH)
        return jsonify({
            "status": "ok",
            "top_areas": summary.get("top_areas", []),
            "crime_distribution": summary.get("crime_distribution", []),
        })

    @_apply_limit("30 per minute")
    @app.route("/api/heatmap/invalidate", methods=["POST"])
    def api_heatmap_invalidate():
        """Optional hook after new cases are added (no schema change)."""
        invalidate_heatmap_cache()
        return jsonify({"status": "ok", "message": "Heatmap cache cleared"})

    print("[OK] Extension APIs registered: /api/heatmap, /api/analytics/*")
