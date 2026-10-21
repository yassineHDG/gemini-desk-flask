from datetime import datetime, timezone
from time import perf_counter

from flask import Blueprint, Response, current_app, jsonify, render_template, request
from sqlalchemy import text

from .categories import CATEGORIES, get_category
from .extensions import db
from .models import Conversation, ErrorLog, Message
from .services.file_service import FileExtractionError, extract_file
from .services.gemini_service import SUPPORTED_RESPONSE_MODES, generate_reply


bp = Blueprint("main", __name__)


def _conversation_or_none(conversation_id):
    if not conversation_id:
        return None
    return db.session.get(Conversation, conversation_id)


def _not_found():
    return jsonify({"error": "Conversation introuvable."}), 404


@bp.get("/")
def index():
    conversations = Conversation.query.order_by(Conversation.updated_at.desc()).all()
    selected_id = request.args.get("conversation_id", type=int)
    current = _conversation_or_none(selected_id)
    if selected_id and current is None:
        current = conversations[0] if conversations else None
    return render_template(
        "chat.html",
        conversations=conversations,
        current=current,
        categories=CATEGORIES,
        model=current_app.config["GEMINI_MODEL"],
    )


@bp.get("/journal")
def journal():
    errors = ErrorLog.query.order_by(ErrorLog.created_at.desc()).limit(250).all()
    return render_template("logs.html", errors=errors)


@bp.get("/health")
def health():
    db.session.execute(text("SELECT 1"))
    return jsonify({"status": "ok", "database": "connected"})


@bp.post("/api/conversations")
def create_conversation():
    data = request.get_json(silent=True) or {}
    category = data.get("category", "default")
    if category not in CATEGORIES:
        category = "default"
    conversation = Conversation(category=category)
    db.session.add(conversation)
    db.session.commit()
    return jsonify({"conversation": conversation.to_dict(include_messages=True)}), 201


@bp.get("/api/conversations/<int:conversation_id>")
def get_conversation(conversation_id):
    conversation = db.session.get(Conversation, conversation_id)
    if not conversation:
        return _not_found()
    return jsonify({"conversation": conversation.to_dict(include_messages=True)})


@bp.patch("/api/conversations/<int:conversation_id>/category")
def set_category(conversation_id):
    conversation = db.session.get(Conversation, conversation_id)
    if not conversation:
        return _not_found()
    data = request.get_json(silent=True) or {}
    category = data.get("category", "default")
    if category not in CATEGORIES:
        return jsonify({"error": "Catégorie inconnue."}), 400
    conversation.category = category
    conversation.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.session.commit()
    return jsonify({"conversation": conversation.to_dict()})


@bp.delete("/api/conversations/<int:conversation_id>/messages")
def clear_conversation(conversation_id):
    conversation = db.session.get(Conversation, conversation_id)
    if not conversation:
        return _not_found()
    Message.query.filter_by(conversation_id=conversation_id).delete()
    conversation.title = "Nouvelle conversation"
    conversation.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.session.commit()
    return jsonify({"ok": True, "conversation": conversation.to_dict()})


@bp.delete("/api/conversations/<int:conversation_id>")
def delete_conversation(conversation_id):
    conversation = db.session.get(Conversation, conversation_id)
    if not conversation:
        return _not_found()
    db.session.delete(conversation)
    db.session.commit()
    return jsonify({"ok": True})


@bp.post("/api/conversations/<int:conversation_id>/messages")
def send_message(conversation_id):
    conversation = db.session.get(Conversation, conversation_id)
    if not conversation:
        return _not_found()

    message_text = (request.form.get("message") or "").strip()
    upload = request.files.get("file")
    response_modes = [
        mode
        for mode in request.form.getlist("response_modes")
        if mode in SUPPORTED_RESPONSE_MODES
    ]

    try:
        extraction = extract_file(upload) if upload and upload.filename else None
    except FileExtractionError as error:
        return jsonify({"error": str(error)}), 400

    if not message_text and not extraction:
        return jsonify({"error": "Écrivez un message ou joignez un fichier."}), 400

    if not message_text and extraction:
        message_text = (
            "Analyse la conformité de ce fichier SQL et donne des recommandations précises."
            if extraction.sql_report
            else "Analyse ce fichier, identifie la demande qu'il contient et réponds-y clairement."
        )

    history = list(conversation.messages)
    user_message = Message(
        conversation=conversation,
        role="user",
        content=message_text,
        attachment_name=extraction.filename if extraction else None,
        attachment_text=extraction.text if extraction else None,
        sql_report=extraction.sql_report if extraction else None,
    )
    db.session.add(user_message)

    if not history:
        title_source = message_text or (extraction.filename if extraction else "Nouvelle conversation")
        conversation.title = title_source.replace("\n", " ")[:80]
    conversation.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.session.commit()

    prompt = message_text
    if extraction:
        prompt += f"\n\n--- Fichier: {extraction.filename} ---\n{extraction.text}"

    started = perf_counter()
    result = generate_reply(
        api_key=current_app.config["GEMINI_API_KEY"],
        model=current_app.config["GEMINI_MODEL"],
        system_instruction=get_category(conversation.category)["instruction"],
        history=history,
        user_prompt=prompt,
        binary_data=extraction.binary_data if extraction else None,
        mime_type=extraction.mime_type if extraction else None,
        response_modes=response_modes,
    )
    response_time_ms = round((perf_counter() - started) * 1000)

    assistant_message = Message(
        conversation=conversation,
        role="assistant",
        content=result.text,
        confidence_segments=result.confidence_segments,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        total_tokens=result.total_tokens,
        response_time_ms=response_time_ms,
    )
    db.session.add(assistant_message)
    conversation.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.session.commit()

    return jsonify(
        {
            "conversation": conversation.to_dict(),
            "user_message": user_message.to_dict(),
            "assistant_message": assistant_message.to_dict(),
            "sql_report": extraction.sql_report if extraction else None,
        }
    )


@bp.get("/conversations/<int:conversation_id>/export.txt")
def export_conversation(conversation_id):
    conversation = db.session.get(Conversation, conversation_id)
    if not conversation:
        return render_template("error.html", status_code=404, message="Conversation introuvable."), 404

    lines = [
        f"Conversation: {conversation.title}",
        f"Catégorie: {get_category(conversation.category)['label']}",
        "=" * 72,
        "",
    ]
    for message in conversation.messages:
        label = "user" if message.role == "user" else "assistant"
        lines.append(f"{label} : {message.content}")
        if message.attachment_name:
            lines.append(f"fichier : {message.attachment_name}")
        if message.role == "assistant" and message.total_tokens is not None:
            lines.append(
                f"métriques : {message.total_tokens} tokens "
                f"({message.input_tokens or 0} entrée / {message.output_tokens or 0} sortie), "
                f"{message.response_time_ms or 0} ms"
            )
        if message.role == "assistant" and message.confidence_segments:
            lines.append("confiance déclarée par Gemini :")
            for segment in message.confidence_segments:
                label = "SÛR" if segment.get("confidence") == "sure" else "À VÉRIFIER"
                lines.append(f"[{label}] {segment.get('text', '')}")
        lines.append("")

    content = "\r\n".join(lines)
    filename = f"conversation-{conversation.id}.txt"
    return Response(
        content,
        mimetype="text/plain; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
