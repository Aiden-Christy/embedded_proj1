"""
dialog_routes.py
================
Drop-in Flask blueprint that adds a /dialog endpoint to your existing server.

HOW TO INTEGRATE
────────────────
In your existing flask_server.py, add these lines:

    from dialog_routes import dialog_bp, init_dialog

    def touch_cmd_time():
        global last_cmd_time
        last_cmd_time = time.time()

    app.register_blueprint(dialog_bp)
    init_dialog(robot, script_path="dialog_script.rug", keep_alive_fn=touch_cmd_time)

That's it.  The /dialog endpoint will be live immediately.

ENDPOINT
────────
POST /dialog
    Body (JSON):  { "text": "hello robot" }
    Response:     { "speak": "Hey!", "actions": ["arm_raise"] }

POST /dialog/reset
    Resets conversation scope and variables.
    Response:     { "reset": true }
"""

from flask import Blueprint, request, jsonify
from dialog_engine import DialogEngine
from action_runner import ActionRunner
import logging

logger = logging.getLogger(__name__)

dialog_bp = Blueprint("dialog", __name__)

_engine: DialogEngine | None = None
_runner: ActionRunner | None = None


def init_dialog(robot, script_path: str = "dialog_script.rug", keep_alive_fn=None):
    """
    Call once at startup, after creating your Tango instance.

        init_dialog(robot, "dialog_script.rug", keep_alive_fn=touch_cmd_time)

    keep_alive_fn should reset app.py's last_cmd_time so the watchdog
    doesn't kill the wheels during dance/drive actions.
    """
    global _engine, _runner
    _engine = DialogEngine()
    _engine.load(script_path)
    _runner = ActionRunner(robot, keep_alive_fn=keep_alive_fn)
    _runner.start()
    logger.info("Dialog system ready (script=%s).", script_path)


# ── Routes ────────────────────────────────────────────────────────────────────

@dialog_bp.route("/dialog", methods=["POST"])
def dialog():
    if _engine is None or _runner is None:
        return jsonify(error="Dialog system not initialised."), 503

    data = request.json or {}
    text = str(data.get("text", "")).strip()
    if not text:
        return jsonify(error="Empty 'text' field."), 400

    speak, actions = _engine.process(text)

    # enqueue speak + actions — never blocks the route
    _runner.enqueue_speak(speak)
    _runner.enqueue(actions)

    return jsonify(speak=speak, actions=actions)


@dialog_bp.route("/dialog/reset", methods=["POST"])
def dialog_reset():
    if _engine is None:
        return jsonify(error="Dialog system not initialised."), 503
    _engine.reset_all()
    return jsonify(reset=True)


@dialog_bp.route("/dialog/state", methods=["GET"])
def dialog_state():
    """Debug endpoint — returns current scope and captured variables."""
    if _engine is None:
        return jsonify(error="Dialog system not initialised."), 503
    return jsonify(
        scope=_engine.scope,
        vars=_engine.vars,
    )
