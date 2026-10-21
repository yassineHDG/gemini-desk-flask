import json
from dataclasses import dataclass, field
from typing import Literal

from google import genai
from google.genai import types
from pydantic import BaseModel, Field


SUPPORTED_RESPONSE_MODES = {"concise", "analyzed", "instant"}


class ConfidenceSegment(BaseModel):
    text: str = Field(description="Un fragment cohérent de la réponse, avec sa ponctuation.")
    confidence: Literal["sure", "uncertain"] = Field(
        description="sure si l'information est solidement établie, sinon uncertain."
    )


class ConfidenceAnswer(BaseModel):
    segments: list[ConfidenceSegment]


@dataclass
class GeminiResult:
    text: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    confidence_segments: list[dict] = field(default_factory=list)


def _response_instructions(response_modes):
    selected = set(response_modes or []) & SUPPORTED_RESPONSE_MODES
    instructions = [
        "Réponds en français sauf demande contraire.",
        "Formate chaque fragment en Markdown standard lorsque cela améliore la lecture : titres, "
        "listes, tableaux et blocs de code balisés. N'utilise pas de HTML brut.",
        "Découpe la réponse en fragments cohérents et attribue à chacun un niveau de confiance.",
        "Utilise 'sure' seulement pour une information solidement établie par le contexte fourni, "
        "un calcul vérifiable ou une connaissance stable.",
        "Utilise 'uncertain' pour toute hypothèse, estimation, ambiguïté, information temporelle "
        "non vérifiée ou donnée manquante. Signale clairement ce qu'il faudrait vérifier.",
        "N'invente jamais une source, un fait, un résultat de fichier ou une certitude.",
    ]
    if "analyzed" in selected:
        instructions.append(
            "Mode analysé : vérifie les hypothèses, structure le raisonnement utile et termine par "
            "une conclusion exploitable. Ne révèle pas de raisonnement interne privé détaillé."
        )
    if "concise" in selected:
        instructions.append(
            "Mode concis : va à l'essentiel, supprime les répétitions et limite la réponse à "
            "environ 8 phrases, sauf si la sécurité ou la demande exige davantage."
        )
    if "instant" in selected:
        instructions.append(
            "Mode instantané : donne le résultat ou l'action principale dès la première phrase, "
            "sans préambule, puis ajoute uniquement les précisions indispensables."
        )
    return "\n".join(instructions)


def _normalise_segments(parsed, fallback_text):
    if parsed is None and fallback_text:
        try:
            parsed = json.loads(fallback_text)
        except (TypeError, json.JSONDecodeError):
            parsed = None
    raw_segments = getattr(parsed, "segments", None)
    if raw_segments is None and isinstance(parsed, dict):
        raw_segments = parsed.get("segments")

    segments = []
    for segment in raw_segments or []:
        text_value = getattr(segment, "text", None)
        confidence = getattr(segment, "confidence", None)
        if isinstance(segment, dict):
            text_value = segment.get("text")
            confidence = segment.get("confidence")
        text_value = (text_value or "").strip()
        if text_value:
            segments.append(
                {
                    "text": text_value,
                    "confidence": "sure" if confidence == "sure" else "uncertain",
                }
            )

    if not segments:
        fallback = (fallback_text or "Gemini n'a pas renvoyé de texte.").strip()
        segments = [{"text": fallback, "confidence": "uncertain"}]
    return segments


def _thinking_config(response_modes):
    selected = set(response_modes or []) & SUPPORTED_RESPONSE_MODES
    if "instant" in selected:
        return types.ThinkingConfig(thinking_level=types.ThinkingLevel.LOW)
    if "analyzed" in selected:
        return types.ThinkingConfig(thinking_level=types.ThinkingLevel.MEDIUM)
    return types.ThinkingConfig(
        thinking_level=types.ThinkingLevel.LOW
    )


def generate_reply(
    api_key,
    model,
    system_instruction,
    history,
    user_prompt,
    binary_data=None,
    mime_type=None,
    response_modes=None,
):
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY manque dans le fichier .env.")

    client = genai.Client(
        api_key=api_key,
        http_options=types.HttpOptions(timeout=30_000),
    )
    contents = []
    for message in history[-30:]:
        role = "model" if message.role == "assistant" else "user"
        historical_text = message.content
        if message.attachment_text:
            historical_text += f"\n\nContenu du fichier {message.attachment_name}:\n{message.attachment_text[:20_000]}"
        contents.append(types.Content(role=role, parts=[types.Part.from_text(text=historical_text)]))

    parts = [types.Part.from_text(text=user_prompt)]
    if binary_data and mime_type:
        parts.append(types.Part.from_bytes(data=binary_data, mime_type=mime_type))
    contents.append(types.Content(role="user", parts=parts))

    response = client.models.generate_content(
        model=model,
        contents=contents,
        config=types.GenerateContentConfig(
            system_instruction=f"{system_instruction}\n\n{_response_instructions(response_modes)}",
            response_mime_type="application/json",
            response_schema=ConfidenceAnswer,
            thinking_config=_thinking_config(response_modes),
        ),
    )
    segments = _normalise_segments(getattr(response, "parsed", None), response.text)
    answer_text = "\n\n".join(segment["text"] for segment in segments)
    usage = getattr(response, "usage_metadata", None)
    return GeminiResult(
        text=answer_text,
        input_tokens=int(getattr(usage, "prompt_token_count", 0) or 0),
        output_tokens=int(getattr(usage, "candidates_token_count", 0) or 0),
        total_tokens=int(getattr(usage, "total_token_count", 0) or 0),
        confidence_segments=segments,
    )
