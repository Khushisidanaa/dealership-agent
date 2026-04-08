# Voice call setup (Twilio + Nova Sonic)

To make outbound AI voice calls to dealers you need:

## 1. Twilio

- **Trial accounts**: You can only call **verified** numbers.
  - Twilio Console → [Phone Numbers → Manage → Verified Caller IDs](https://console.twilio.com/us1/develop/phone-numbers/manage/verified)
  - Add the dealer number (or your own for testing), verify via SMS or call.
- **Paid accounts**: Can call any number (no verification needed).
- Set in `.env`: `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_PHONE_NUMBER`.

## 2. Public URL (ngrok when local)

Twilio must reach your server to get TwiML and open the WebSocket for the call. If the server is on your machine, Twilio can’t use `http://127.0.0.1:8000`.

1. Start your backend: `uvicorn app.main:app --host 0.0.0.0 --port 8000`
2. In another terminal: `ngrok http 8000`
3. Copy the **HTTPS** URL ngrok shows (e.g. `https://abc123.ngrok-free.app`)
4. In `backend/.env` set:
   ```bash
   SERVER_BASE_URL=https://abc123.ngrok-free.app
   ```
   (No trailing slash.)

After restarting the backend, `POST /api/voice/call` will use this URL in the TwiML so Twilio can connect the call to your server.

## 3. Voice agent (Nova Sonic or Deepgram)

- **Nova Sonic**: Set AWS credentials in `.env` (`ACCESS_KEY`, `SECRET_ACCRESS_KEY`). Same as Nova Act.
  - **Required for speech**: Install the Bedrock runtime SDK (Python 3.12+):  
    `pip install aws_sdk_bedrock_runtime`  
    If your pip index doesn’t have it:  
    `pip install --index-url https://pypi.org/simple aws_sdk_bedrock_runtime`
- **Deepgram**: Set `DEEPGRAM_API_KEY` if you’re not using Nova Sonic.

## Quick checklist

- [ ] Twilio credentials and phone number in `.env`
- [ ] Dealer (or test) number **verified** in Twilio if you’re on a trial account
- [ ] `SERVER_BASE_URL` set to your **public** URL (e.g. ngrok HTTPS URL when local)
- [ ] AWS credentials (for Nova Sonic) or Deepgram API key in `.env`
