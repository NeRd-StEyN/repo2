import os
import threading
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from lang import app  # your LangGraph workflow
from chat_handler import init_chat_from_base64, chat_with_pdf


# -------------------------------------------------------------------
# Flask App Config (⚙️ Serving React dist folder)
# -------------------------------------------------------------------
server = Flask(__name__, static_folder="build", static_url_path="/")
CORS(server)

# -------------------------------------------------------------------
# Report generation state
# -------------------------------------------------------------------
progress_state = {}
generated_reports = {}
generation_status = {}

# -------------------------------------------------------------------
# Background PDF Report Generation (LangGraph)
# -------------------------------------------------------------------
def background_generate(cache_key, topic, language="English", pages=3):
    """Run LangGraph workflow in a background thread."""
    try:
        generation_status[cache_key] = "in_progress"

        # 👇 Pass all parameters to LangGraph
        for state in app.stream({"topic": topic, "language": language, "pages": pages}):
            if "intro" in state or "planner" in state:
                progress_state[cache_key]["topicAnalysis"] = True
            elif "retriever" in state:
                progress_state[cache_key]["dataGathering"] = True
            elif "summarizer" in state or "analyzer" in state or "conclusion" in state:
                progress_state[cache_key]["draftingReport"] = True
            elif "visualizer" in state or "report_generator" in state:
                progress_state[cache_key]["finalizing"] = True

            # ✅ Capture Base64 PDF
            if "report_generator" in state:
                pdf_base64 = state["report_generator"].get("pdf_base64")
                if pdf_base64:
                    generated_reports[cache_key] = pdf_base64
                    generation_status[cache_key] = "completed"
                break

        progress_state[cache_key] = {
            "topicAnalysis": True,
            "dataGathering": True,
            "draftingReport": True,
            "finalizing": True,
        }

        if cache_key not in generation_status or generation_status[cache_key] != "completed":
            generation_status[cache_key] = "completed"

    except Exception as e:
        print(f"[ERROR] Background generation failed for {topic} (pages={pages}, lang={language}): {e}")
        progress_state[cache_key] = {
            "topicAnalysis": False,
            "dataGathering": False,
            "draftingReport": False,
            "finalizing": False,
            "error": str(e)
        }
        generation_status[cache_key] = "failed"


# -------------------------------------------------------------------
# Report Generation API
# -------------------------------------------------------------------
def create_report_key(topic, language, pages):
    """Create a unique cache key for topic + language + pages combination."""
    return f"{topic}||{language}||{pages}"


@server.route("/generate_report", methods=["POST"])
def generate_report():
    """Start background report generation for a topic."""
    data = request.get_json()
    topic = data.get("topic", "").strip()
    language = data.get("language", "English").strip()
    pages = int(data.get("pages", 3))

    if not topic:
        return jsonify({"error": "Missing topic"}), 400

    # Optional: validate pages
    if pages < 2 or pages > 10:
        return jsonify({"error": "Page count must be between 2 and 10"}), 400

    # Optional: validate language (optional safety)
    allowed_languages = [
        "English",
        # Indian Languages
        "Hindi", "Tamil", "Telugu", "Kannada", "Malayalam", "Marathi", "Bengali", "Gujarati", "Punjabi",
        # International Languages
        "Spanish", "French", "German", "Portuguese", "Italian", "Chinese (Simplified)", "Japanese", "Korean"
    ]
    if language not in allowed_languages:
        return jsonify({"error": f"Unsupported language: {language}"}), 400

    print(f"🚀 Starting report generation for topic='{topic}', "
          f"language='{language}', pages={pages}")

    # Create unique cache key for this combination
    cache_key = create_report_key(topic, language, pages)

    if cache_key in generated_reports:
        return jsonify({"pdf_base64": generated_reports[cache_key]})

    if cache_key in generation_status and generation_status[cache_key] == "in_progress":
        return jsonify({"message": "Report generation already in progress"})

    progress_state[cache_key] = {
        "topicAnalysis": False,
        "dataGathering": False,
        "draftingReport": False,
        "finalizing": False,
    }
    generation_status[cache_key] = "in_progress"

    # Pass language and pages to your background process
    thread = threading.Thread(target=background_generate, args=(cache_key, topic, language, pages))
    thread.daemon = True
    thread.start()

    return jsonify({"message": "Report generation started", "topic": topic})


@server.route("/progress/<cache_key>", methods=["GET"])
def get_progress(cache_key):
    """Return current progress for frontend polling."""
    status = generation_status.get(cache_key, "not_started")
    progress = progress_state.get(cache_key, {
        "topicAnalysis": False,
        "dataGathering": False,
        "draftingReport": False,
        "finalizing": False,
    })
    return jsonify({
        "progress": progress,
        "status": status,
        "is_complete": status == "completed"
    })


@server.route("/report/<cache_key>", methods=["GET"])
def get_report(cache_key):
    """Return generated PDF (Base64) for display."""
    if cache_key not in generated_reports:
        return jsonify({"error": "Report not found"}), 404

    pdf_data = generated_reports.get(cache_key)
    if not pdf_data:
        return jsonify({"error": "PDF data is empty"}), 404

    return jsonify({
        "pdf_base64": pdf_data,
        "status": "success"
    })


# -------------------------------------------------------------------
# 🧠 Chat APIs — Calls chat_handler.py
# -------------------------------------------------------------------
@server.route("/chat/init", methods=["POST"])
def chat_init():
    """Initialize chat session with Base64 PDF."""
    try:
        data = request.get_json()
        session_id = data.get("session_id")
        pdf_base64 = data.get("pdf_base64")
        language = data.get("language", "English")  # 🆕 Add language

        if not session_id or not pdf_base64:
            return jsonify({"error": "Missing session_id or pdf_base64"}), 400

        # Pass language into chat init
        result = init_chat_from_base64(session_id, pdf_base64, language)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@server.route("/chat/message", methods=["POST"])
def chat_message():
    """Send a message and get AI response."""
    try:
        data = request.get_json()
        session_id = data.get("session_id")
        message = data.get("message")
        language = data.get("language", "English")  # 🆕 Add language

        if not session_id or not message:
            return jsonify({"error": "Missing session_id or message"}), 400

        result = chat_with_pdf(session_id, message, language)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500



# -------------------------------------------------------------------
# 🩺 Health Check
# -------------------------------------------------------------------
@server.route("/health")
def health():
    return jsonify({"status": "healthy"})


# -------------------------------------------------------------------
# 🌐 Serve React Frontend (Vite dist folder)
# -------------------------------------------------------------------
@server.route("/")
def serve_react():
    """Serve main React app."""
    return send_from_directory(server.static_folder, "index.html")

@server.errorhandler(404)
def not_found(e):
    """Fallback to React router for unknown routes."""
    return send_from_directory(server.static_folder, "index.html")


# -------------------------------------------------------------------
# 🏁 Run Server
# -------------------------------------------------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    server.run(host="0.0.0.0", port=port)
