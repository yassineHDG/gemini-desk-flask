import io
import unittest
from unittest.mock import patch

from app import create_app
from app.extensions import db
from app.services.gemini_service import GeminiResult
from app.services.gemini_service import _thinking_config
from app.markdown_utils import render_markdown
from google.genai import types


class GeminiDeskTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app(
            {
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
                "GEMINI_API_KEY": "test-key",
                "SECRET_KEY": "test",
            }
        )
        self.client = self.app.test_client()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def create_conversation(self, category="default"):
        response = self.client.post("/api/conversations", json={"category": category})
        self.assertEqual(response.status_code, 201)
        return response.get_json()["conversation"]

    def test_home_and_conversation_lifecycle(self):
        self.assertEqual(self.client.get("/").status_code, 200)
        conversation = self.create_conversation("education")
        response = self.client.patch(
            f"/api/conversations/{conversation['id']}/category",
            json={"category": "programming"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["conversation"]["category"], "programming")

    def test_response_mode_thinking_priority(self):
        self.assertEqual(
            _thinking_config(["instant"]).thinking_level,
            types.ThinkingLevel.LOW,
        )
        self.assertEqual(
            _thinking_config(["instant", "analyzed"]).thinking_level,
            types.ThinkingLevel.LOW,
        )
        self.assertEqual(
            _thinking_config(["concise"]).thinking_level,
            types.ThinkingLevel.LOW,
        )

    def test_markdown_is_rendered_and_sanitized(self):
        rendered = str(
            render_markdown(
                "## Titre\n\n**Important** et [lien](javascript:alert(1))."
                "\n\n<script>alert('x')</script>"
            )
        )
        self.assertIn("<h2>Titre</h2>", rendered)
        self.assertIn("<strong>Important</strong>", rendered)
        self.assertIn("<ul>", str(render_markdown("Introduction :\n* Élément 1\n* Élément 2")))
        self.assertNotIn("<script", rendered)
        self.assertNotIn("javascript:", rendered)

    @patch("app.routes.generate_reply")
    def test_sql_upload_metrics_export_and_clear(self, mock_generate):
        mock_generate.return_value = GeminiResult(
            text="Le script nécessite une clause WHERE.",
            input_tokens=22,
            output_tokens=9,
            total_tokens=31,
            confidence_segments=[
                {
                    "text": "Le script nécessite une clause WHERE.",
                    "confidence": "sure",
                }
            ],
        )
        conversation = self.create_conversation()
        sql_file = io.BytesIO(b"DELETE FROM users;")
        response = self.client.post(
            f"/api/conversations/{conversation['id']}/messages",
            data={
                "message": "Verifie ce SQL",
                "response_modes": ["concise", "analyzed", "invalid"],
                "file": (sql_file, "audit.sql"),
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["assistant_message"]["total_tokens"], 31)
        self.assertIn("<p>Le script", payload["assistant_message"]["content_html"])
        self.assertEqual(
            payload["assistant_message"]["confidence_segments"][0]["confidence"],
            "sure",
        )
        self.assertIsNotNone(payload["sql_report"])
        self.assertLess(payload["sql_report"]["score"], 100)
        self.assertEqual(
            mock_generate.call_args.kwargs["response_modes"],
            ["concise", "analyzed"],
        )

        export = self.client.get(f"/conversations/{conversation['id']}/export.txt")
        self.assertEqual(export.status_code, 200)
        self.assertIn("user : Verifie ce SQL", export.get_data(as_text=True))
        self.assertIn("assistant : Le script", export.get_data(as_text=True))
        self.assertIn("[SÛR] Le script", export.get_data(as_text=True))

        cleared = self.client.delete(f"/api/conversations/{conversation['id']}/messages")
        self.assertEqual(cleared.status_code, 200)
        detail = self.client.get(f"/api/conversations/{conversation['id']}").get_json()
        self.assertEqual(detail["conversation"]["messages"], [])


if __name__ == "__main__":
    unittest.main()
