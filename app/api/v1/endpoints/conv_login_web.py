from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import httpx
import os

router = APIRouter()

# Set these via environment variables or replace with your actual values
GET_CONVERSATION_ID_URL = os.getenv("GET_CONVERSATION_ID_URL", "https://your-backend/get_conversation_id")
ELEVENLAB_WEBHOOK_URL = os.getenv("ELEVENLAB_WEBHOOK_URL", "https://api.elevenlabs.io/webhook")

class RegistrationRequest(BaseModel):
    registration_id: str

class WebhookPayload(BaseModel):
    registration_id: str
    conversation_id: str

@router.post("/webhook/conversation-login")
async def conversation_login_via_webhook(request: RegistrationRequest):
    if not request.registration_id:
        raise HTTPException(status_code=400, detail="Registration ID is required.")

    # Step 1: Get conversation_id from PostgreSQL-backed API
    try:
        async with httpx.AsyncClient() as client:
            conv_response = await client.post(GET_CONVERSATION_ID_URL, json={"registration_id": request.registration_id})
            conv_response.raise_for_status()
            conv_data = conv_response.json()
            conversation_id = conv_data.get("conversation_id")
            if not conversation_id:
                raise HTTPException(status_code=404, detail="Conversation ID not found for this registration ID.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get conversation ID: {e}")

    # Step 2: Trigger ElevenLabs webhook with registration_id and conversation_id
    webhook_payload = WebhookPayload(registration_id=request.registration_id, conversation_id=conversation_id)
    try:
        async with httpx.AsyncClient() as client:
            webhook_response = await client.post(ELEVENLAB_WEBHOOK_URL, json=webhook_payload.model_dump())
            webhook_response.raise_for_status()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to trigger ElevenLabs webhook: {e}")

    return {"registration_id": request.registration_id, "conversation_id": conversation_id, "status": "Webhook triggered successfully."} 