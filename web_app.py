import json
from queue import Queue
from threading import Thread

from flask import Flask, Response, jsonify, render_template, request, stream_with_context

from app import run_master_with_steps

app = Flask(__name__)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/chat", methods=["POST"])
def chat():
    payload = request.get_json(silent=True) or {}
    query = (payload.get("query") or "").strip()

    if not query:
        return jsonify({"error": "Please enter a question."}), 400

    events = Queue()

    def run_request():
        try:
            answer, _ = run_master_with_steps(query, on_step=lambda step: events.put({"type": "step", "step": step}))
            events.put({"type": "answer", "answer": answer})
        except Exception as exc:  # pragma: no cover - defensive guard
            events.put({"type": "error", "error": f"Something went wrong: {exc}"})
        finally:
            events.put(None)

    Thread(target=run_request, daemon=True).start()

    @stream_with_context
    def generate_events():
        while True:
            event = events.get()
            if event is None:
                break
            yield json.dumps(event) + "\n"

    return Response(generate_events(), mimetype="application/x-ndjson")


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
