from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import httpx
import os

router = APIRouter()

# Set these via environment variables or replace with your actual values
CLAIM_REGISTRATION_URL = os.getenv("CLAIM_REGISTRATION_URL", "https://your-backend/claim_registration")
ELEVENLAB_WEBHOOK_URL = os.getenv("ELEVENLAB_WEBHOOK_URL", "https://api.elevenlabs.io/webhook")
ELEVENLAB_AGENT_ID = os.getenv("ELEVENLAB_AGENT_ID", "Conf_user_agent")

class RegistrationRequest(BaseModel):
    registration_id: str

class WebhookPayload(BaseModel):
    registration_id: str
    agent_id: str

@router.post("/webhook/agent-login")
async def agent_login_via_webhook(request: RegistrationRequest):
    if not request.registration_id:
        raise HTTPException(status_code=400, detail="Registration ID is required.")

    #claim the registration id
    try:
        async with httpx.AsyncClient() as client:
            claim_response = await client.post(CLAIM_REGISTRATION_URL, json={"registration_id": request.registration_id})
            claim_response.raise_for_status()
            claim_data = claim_response.json()
            if not claim_data.get("success", False):
                raise HTTPException(status_code=404, detail="Registration ID not found or already claimed.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to claim registration: {e}")

    #Trigger ElevenLabs webhook with static agent_id
    webhook_payload = WebhookPayload(registration_id=request.registration_id, agent_id=ELEVENLAB_AGENT_ID)
    try:
        async with httpx.AsyncClient() as client:
            webhook_response = await client.post(ELEVENLAB_WEBHOOK_URL, json=webhook_payload.model_dump())
            webhook_response.raise_for_status()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to trigger ElevenLabs webhook: {e}")

    return {"registration_id": request.registration_id, "agent_id": ELEVENLAB_AGENT_ID, "status": "Agent assigned and webhook triggered successfully."} 
