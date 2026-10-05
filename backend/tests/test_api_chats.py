"""
Integration and isolation tests for Phase 2 Chat API.
Tests CRUD, tenant isolation between cookies, message history, SSE mock streaming, and uploads.
"""
import io
import pytest
from starlette.testclient import TestClient

from backend.app.main import app
from backend.app.config import settings
from backend.app.core.session import hash_token


@pytest.fixture
def client():
    """Default TestClient simulating a browser session."""
    return TestClient(app)


def test_health_check(client):
    """Verify healthcheck endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "version" in data


def test_create_and_list_chats(client):
    """Verify creating a chat and listing it under the caller's anonymous session."""
    # Create chat 1
    r1 = client.post("/api/chats", json={"title": "Digital KYC Onboarding Flow"})
    assert r1.status_code == 201
    chat1 = r1.json()
    assert chat1["title"] == "Digital KYC Onboarding Flow"
    assert "id" in chat1
    assert chat1["state"] == "INTAKE"

    # Create chat 2
    r2 = client.post("/api/chats", json={"title": "Retail Loan Application"})
    assert r2.status_code == 201
    chat2 = r2.json()

    # List chats
    r_list = client.get("/api/chats")
    assert r_list.status_code == 200
    chat_list = r_list.json()
    chat_ids = [c["id"] for c in chat_list]
    assert chat1["id"] in chat_ids
    assert chat2["id"] in chat_ids


def test_update_and_delete_chat(client):
    """Verify updating a chat title and soft-deleting it."""
    # Create
    r = client.post("/api/chats", json={"title": "Initial Title"})
    assert r.status_code == 201
    chat_id = r.json()["id"]

    # Update
    r_patch = client.patch(f"/api/chats/{chat_id}", json={"title": "Updated Title"})
    assert r_patch.status_code == 200
    assert r_patch.json()["title"] == "Updated Title"

    # Soft Delete
    r_del = client.delete(f"/api/chats/{chat_id}")
    assert r_del.status_code == 204

    # Verify not listed
    r_list = client.get("/api/chats")
    chat_ids = [c["id"] for c in r_list.json()]
    assert chat_id not in chat_ids

    # Verify 404 on direct fetch
    r_get = client.get(f"/api/chats/{chat_id}")
    assert r_get.status_code == 404


def test_multi_tenant_isolation():
    """
    CRITICAL TEST: Verify two browsers/tokens CANNOT access each other's chats.
    Client A with token A must be completely isolated from Client B with token B.
    """
    client_a = TestClient(app, cookies={settings.SESSION_COOKIE_NAME: "user_a_secret_token_12345"})
    client_b = TestClient(app, cookies={settings.SESSION_COOKIE_NAME: "user_b_secret_token_67890"})

    # Client A creates chat
    r_a = client_a.post("/api/chats", json={"title": "Confidential Project A"})
    assert r_a.status_code == 201
    chat_a_id = r_a.json()["id"]

    # Client B lists chats: must NOT see chat A
    r_b_list = client_b.get("/api/chats")
    assert r_b_list.status_code == 200
    b_chat_ids = [c["id"] for c in r_b_list.json()]
    assert chat_a_id not in b_chat_ids

    # Client B tries to GET chat A directly: must receive 404
    r_b_get = client_b.get(f"/api/chats/{chat_a_id}")
    assert r_b_get.status_code == 404

    # Client B tries to PATCH chat A: must receive 404
    r_b_patch = client_b.patch(f"/api/chats/{chat_a_id}", json={"title": "Hacked Title"})
    assert r_b_patch.status_code == 404

    # Client B tries to DELETE chat A: must receive 404
    r_b_del = client_b.delete(f"/api/chats/{chat_a_id}")
    assert r_b_del.status_code == 404

    # Client A can still fetch their own chat intact
    r_a_verify = client_a.get(f"/api/chats/{chat_a_id}")
    assert r_a_verify.status_code == 200
    assert r_a_verify.json()["title"] == "Confidential Project A"


def test_messages_and_sse_streaming(client):
    """Verify sending a message, receiving SSE streamed tokens, and verifying DB history."""
    # Create chat
    r_chat = client.post("/api/chats", json={"title": "Streaming Test Chat"})
    chat_id = r_chat.json()["id"]

    # Send message and consume SSE stream
    payload = {"content": "We need customer Aadhaar and PAN verification"}
    response = client.post(f"/api/chats/{chat_id}/messages", json=payload)
    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]

    # Parse stream lines
    stream_content = response.text
    assert "event: start" in stream_content
    assert "event: token" in stream_content
    assert "event: action_cards" in stream_content
    assert "event: done" in stream_content

    # Verify messages persisted in DB
    r_msgs = client.get(f"/api/chats/{chat_id}/messages")
    assert r_msgs.status_code == 200
    msgs = r_msgs.json()
    assert len(msgs) == 2  # 1 user message + 1 assistant message

    user_msg = msgs[0]
    assert user_msg["role"] == "user"
    assert user_msg["content_masked"] == "We need customer Aadhaar and PAN verification"

    asst_msg = msgs[1]
    assert asst_msg["role"] == "assistant"
    assert "AI Requirement Engineer" in asst_msg["content_masked"]
    assert len(asst_msg["action_cards"]) == 1
    assert asst_msg["action_cards"][0]["card_type"] == "question_group"


def test_file_upload(client):
    """Verify paperclip file upload stores file and creates metadata record."""
    r_chat = client.post("/api/chats", json={"title": "Upload Test Chat"})
    chat_id = r_chat.json()["id"]

    file_content = b"Sample policy document for KYC verification."
    files = {"file": ("kyc_policy.txt", io.BytesIO(file_content), "text/plain")}

    response = client.post(f"/api/chats/{chat_id}/upload", files=files)
    assert response.status_code == 200
    data = response.json()
    assert data["filename"] == "kyc_policy.txt"
    assert data["file_size"] == len(file_content)
    assert data["mime_type"] == "text/plain"
    assert data["chat_id"] == chat_id
