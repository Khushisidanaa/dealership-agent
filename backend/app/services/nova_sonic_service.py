"""
Amazon Nova Sonic voice bridge for Twilio calls.

Same flow as Deepgram: Twilio streams mulaw 8kHz to us; we bridge to Nova Sonic
(bidirectional Bedrock stream), convert mulaw<->PCM 8kHz, and stream TTS back to Twilio.
Uses AWS credentials (ACCESS_KEY / SECRET_ACCRESS_KEY or AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY).

Uses the experimental aws_sdk_bedrock_runtime package when available (pip install aws_sdk_bedrock_runtime)
for invoke_model_with_bidirectional_stream; otherwise falls back to boto3 (which does not support it yet).
"""

import asyncio
import audioop
import base64
import json
import logging
import os
import uuid
from typing import Iterator

from app.config import get_settings

log = logging.getLogger(__name__)
# Use uvicorn's logger so Nova Sonic diagnostics show in the same console
voice_log = logging.getLogger("uvicorn.error")

# Twilio and Nova Sonic use 8kHz; Nova accepts 8000 in audioInputConfiguration
SAMPLE_RATE = 8000
# ~20ms at 8kHz mulaw: 160 bytes; we buffer and send as PCM (320 bytes per 20ms)
CHUNK_BYTES_MULAW = 20 * (SAMPLE_RATE // 50)

# Lazy check for experimental SDK (has invoke_model_with_bidirectional_stream)
_has_bedrock_sdk: bool | None = None


def _has_experimental_sdk() -> bool:
    global _has_bedrock_sdk
    if _has_bedrock_sdk is not None:
        return _has_bedrock_sdk
    try:
        from aws_sdk_bedrock_runtime.client import BedrockRuntimeClient  # noqa: F401
        from aws_sdk_bedrock_runtime.models import (  # noqa: F401
            BidirectionalInputPayloadPart,
            InvokeModelWithBidirectionalStreamInputChunk,
        )
        _has_bedrock_sdk = True
    except ImportError:
        _has_bedrock_sdk = False
    return _has_bedrock_sdk


def _get_aws_credentials() -> tuple[str, str]:
    """Return (access_key_id, secret_access_key) from config or env."""
    s = get_settings()
    ak = (s.aws_access_key_id or os.environ.get("ACCESS_KEY") or "").strip()
    sk = (s.aws_secret_access_key or os.environ.get("SECRET_ACCRESS_KEY") or "").strip()
    if not ak:
        ak = (os.environ.get("AWS_ACCESS_KEY_ID") or "").strip()
    if not sk:
        sk = (os.environ.get("AWS_SECRET_ACCESS_KEY") or "").strip()
    return ak, sk


def has_nova_sonic_configured() -> bool:
    """True if we have AWS credentials to call Bedrock Nova Sonic."""
    ak, sk = _get_aws_credentials()
    return bool(ak and sk)


# Sample width in bytes for 16-bit PCM (required by audioop; width=1 would corrupt conversion and cause static)
_PCM_WIDTH = 2


def _mulaw_to_pcm(mulaw_bytes: bytes) -> bytes:
    """Convert 8kHz mulaw to 16-bit mono PCM (8kHz). ulaw2lin width = output sample width in bytes."""
    return audioop.ulaw2lin(mulaw_bytes, _PCM_WIDTH)


def _pcm_to_mulaw(pcm_bytes: bytes) -> bytes:
    """Convert 16-bit mono PCM to 8kHz mulaw. lin2ulaw width = input sample width in bytes (2 for 16-bit)."""
    return audioop.lin2ulaw(pcm_bytes, _PCM_WIDTH)


def _event_dict(prompt_name: str, content_name: str, audio_content_name: str, agent_prompt: str, greeting: str) -> list[dict]:
    """Build the initial event sequence (session + prompt + system + audio contentStart)."""
    system_text = f"{agent_prompt}\n\nStart the call by saying exactly: {greeting}"
    return [
        {"event": {"sessionStart": {"inferenceConfiguration": {"maxTokens": 1024, "topP": 0.9, "temperature": 0.7}}}},
        {
            "event": {
                "promptStart": {
                    "promptName": prompt_name,
                    "textOutputConfiguration": {"mediaType": "text/plain"},
                    "audioOutputConfiguration": {
                        "mediaType": "audio/lpcm",
                        "sampleRateHertz": SAMPLE_RATE,
                        "sampleSizeBits": 16,
                        "channelCount": 1,
                        "voiceId": "matthew",
                        "encoding": "base64",
                        "audioType": "SPEECH",
                    },
                }
            }
        },
        {"event": {"contentStart": {"promptName": prompt_name, "contentName": content_name, "type": "TEXT", "interactive": False, "role": "SYSTEM", "textInputConfiguration": {"mediaType": "text/plain"}}}},
        {"event": {"textInput": {"promptName": prompt_name, "contentName": content_name, "content": system_text}}},
        {"event": {"contentEnd": {"promptName": prompt_name, "contentName": content_name}}},
        {
            "event": {
                "contentStart": {
                    "promptName": prompt_name,
                    "contentName": audio_content_name,
                    "type": "AUDIO",
                    "interactive": True,
                    "role": "USER",
                    "audioInputConfiguration": {
                        "mediaType": "audio/lpcm",
                        "sampleRateHertz": SAMPLE_RATE,
                        "sampleSizeBits": 16,
                        "channelCount": 1,
                        "audioType": "SPEECH",
                        "encoding": "base64",
                    },
                }
            }
        },
    ]


async def _run_nova_sonic_bridge_async(
    agent_prompt: str,
    greeting: str,
    audio_in_queue: asyncio.Queue,
    audio_out_queue: asyncio.Queue,
    transcript: list,
    end_event: asyncio.Event,
) -> None:
    """Use experimental aws_sdk_bedrock_runtime for bidirectional stream (async, no thread)."""
    from aws_sdk_bedrock_runtime.client import BedrockRuntimeClient, InvokeModelWithBidirectionalStreamOperationInput
    from aws_sdk_bedrock_runtime.config import Config, HTTPAuthSchemeResolver, SigV4AuthScheme
    from aws_sdk_bedrock_runtime.models import BidirectionalInputPayloadPart, InvokeModelWithBidirectionalStreamInputChunk
    try:
        from smithy_aws_core.credentials_resolvers.environment import EnvironmentCredentialsResolver
    except ImportError:
        from smithy_aws_core.identity import EnvironmentCredentialsResolver
    try:
        from smithy_http.aio.crt import AWSCRTHTTPClient, AWSCRTHTTPClientConfig
    except ImportError:
        AWSCRTHTTPClient = None  # type: ignore[misc, assignment]
        AWSCRTHTTPClientConfig = None  # type: ignore[misc, assignment]

    settings = get_settings()
    model_id = settings.nova_sonic_model_id or "amazon.nova-sonic-v1:0"
    region = settings.nova_sonic_region or "us-east-1"
    voice_log.info("Nova Sonic: model_id=%s region=%s", model_id, region)
    ak, sk = _get_aws_credentials()
    if not ak or not sk:
        log.error("Nova Sonic: missing AWS credentials")
        await audio_out_queue.put(None)
        end_event.set()
        return

    # Experimental SDK reads credentials from env
    prev_ak = os.environ.get("AWS_ACCESS_KEY_ID")
    prev_sk = os.environ.get("AWS_SECRET_ACCESS_KEY")
    prev_region = os.environ.get("AWS_DEFAULT_REGION")
    os.environ["AWS_ACCESS_KEY_ID"] = ak
    os.environ["AWS_SECRET_ACCESS_KEY"] = sk
    os.environ["AWS_DEFAULT_REGION"] = region
    # Bedrock bidirectional stream requires HTTP/2 (see Node sample NodeHttp2Handler)
    transport = None
    if AWSCRTHTTPClient and AWSCRTHTTPClientConfig:
        try:
            transport = AWSCRTHTTPClient(client_config=AWSCRTHTTPClientConfig(force_http_2=True))
        except Exception as tr_ex:
            voice_log.warning("Nova Sonic: could not enable HTTP/2 transport: %s", tr_ex)
    try:
        # Config API varies by smithy/aws_sdk version; try full then minimal
        try:
            config = Config(
                endpoint_uri=f"https://bedrock-runtime.{region}.amazonaws.com",
                region=region,
                aws_credentials_identity_resolver=EnvironmentCredentialsResolver(),
                auth_scheme_resolver=HTTPAuthSchemeResolver(),
                auth_schemes={"aws.auth#sigv4": SigV4AuthScheme(service="bedrock")},
                transport=transport,
            )
        except TypeError:
            config = Config(
                endpoint_uri=f"https://bedrock-runtime.{region}.amazonaws.com",
                region=region,
                aws_credentials_identity_resolver=EnvironmentCredentialsResolver(),
            )
            if transport is not None:
                config.transport = transport
        client = BedrockRuntimeClient(config)
        prompt_name = str(uuid.uuid4())
        content_name = str(uuid.uuid4())
        audio_content_name = str(uuid.uuid4())

        async def send_event(event_json: dict) -> None:
            chunk = InvokeModelWithBidirectionalStreamInputChunk(
                value=BidirectionalInputPayloadPart(bytes_=json.dumps(event_json).encode("utf-8"))
            )
            await stream.input_stream.send(chunk)

        STREAM_OPEN_TIMEOUT = 30.0  # seconds; Bedrock may hang if IAM/network/region wrong
        try:
            voice_log.info("Nova Sonic: opening bidirectional stream to Bedrock (timeout=%ss)...", STREAM_OPEN_TIMEOUT)
            stream = await asyncio.wait_for(
                client.invoke_model_with_bidirectional_stream(
                    InvokeModelWithBidirectionalStreamOperationInput(model_id=model_id)
                ),
                timeout=STREAM_OPEN_TIMEOUT,
            )
            voice_log.info("Nova Sonic: stream open, sending initial events (session + prompt + system + audio contentStart)")
            # Send first event immediately so server can respond (Node sample sends body stream at invoke time)
            initial_events = _event_dict(prompt_name, content_name, audio_content_name, agent_prompt, greeting)
            first_chunk = InvokeModelWithBidirectionalStreamInputChunk(
                value=BidirectionalInputPayloadPart(bytes_=json.dumps(initial_events[0]).encode("utf-8"))
            )
            await stream.input_stream.send(first_chunk)
            voice_log.info("Nova Sonic: sent sessionStart, sending remaining initial events")
        except asyncio.TimeoutError:
            voice_log.error(
                "Nova Sonic: stream open timed out after %ss. Check: IAM permission bedrock:InvokeModel, region=%s, "
                "model %s in Bedrock console, and network/firewall to bedrock-runtime.%s.amazonaws.com",
                STREAM_OPEN_TIMEOUT, region, model_id, region,
            )
            await audio_out_queue.put(None)
            end_event.set()
            return
        except Exception as e:
            voice_log.exception("Nova Sonic: failed to open bidirectional stream: %s", e)
            await audio_out_queue.put(None)
            end_event.set()
            return

        for i, ev in enumerate(initial_events[1:], start=1):
            await send_event(ev)
        voice_log.info("Nova Sonic: sent %d initial events, starting sender/receiver", len(initial_events))

        async def sender() -> None:
            audio_chunk_count = 0
            try:
                while True:
                    chunk = await audio_in_queue.get()
                    if chunk is None:
                        voice_log.info("Nova Sonic sender: received None, stream ending (sent %d audio chunks)", audio_chunk_count)
                        break
                    if audio_chunk_count == 0:
                        voice_log.info("Nova Sonic sender: first inbound audio chunk from Twilio (%d bytes)", len(chunk))
                    audio_chunk_count += 1
                    if audio_chunk_count % 100 == 0:
                        voice_log.info("Nova Sonic sender: sent %d audio chunks to Bedrock", audio_chunk_count)
                    pcm = _mulaw_to_pcm(chunk)
                    b64 = base64.b64encode(pcm).decode("ascii")
                    await send_event({"event": {"audioInput": {"promptName": prompt_name, "contentName": audio_content_name, "content": b64}}})
            except asyncio.CancelledError:
                voice_log.info("Nova Sonic sender: cancelled after %d chunks", audio_chunk_count)
                pass
            except Exception as e:
                log.warning("Nova Sonic sender: %s (after %d chunks)", e, audio_chunk_count)
            finally:
                voice_log.info("Nova Sonic sender: sending contentEnd, promptEnd, sessionEnd and closing input stream")
                try:
                    await send_event({"event": {"contentEnd": {"promptName": prompt_name, "contentName": audio_content_name}}})
                    await send_event({"event": {"promptEnd": {"promptName": prompt_name}}})
                    await send_event({"event": {"sessionEnd": {}}})
                    await stream.input_stream.close()
                except asyncio.CancelledError:
                    pass
                except Exception as ex:
                    # Expected when stream is already closed (awscrt HTTP_STREAM_HAS_COMPLETED, InvalidStateError)
                    if "HTTP_STREAM" in str(ex) or "CANCELLED" in str(ex) or "stream" in str(ex).lower():
                        voice_log.debug("Nova Sonic sender: stream already closed (%s)", ex)
                    else:
                        log.warning("Nova Sonic sender: close input_stream: %s", ex)

        async def receiver() -> None:
            out_chunk_count = 0
            first_output = True
            event_types_seen: set[str] = set()
            try:
                while True:
                    output = await stream.await_output()
                    result = await output[1].receive()
                    if not result.value:
                        continue
                    raw_bytes = getattr(result.value, "bytes_", None) or getattr(result.value, "bytes", None)
                    if not raw_bytes:
                        continue
                    data = raw_bytes.decode("utf-8")
                    try:
                        obj = json.loads(data)
                    except json.JSONDecodeError:
                        log.warning("Nova Sonic receiver: invalid JSON from stream (len=%d)", len(data))
                        continue
                    # Bedrock may send error payload (e.g. "Invalid input request" when stream is closed)
                    if not obj.get("event"):
                        err_msg = obj.get("message") or obj.get("error") or data[:200]
                        if err_msg and ("invalid" in str(err_msg).lower() or "error" in str(err_msg).lower()):
                            voice_log.info(
                                "Nova Sonic receiver: stream error from Bedrock, treating as end (event_types_seen=%s, out_audio_chunks=%d)",
                                event_types_seen,
                                out_chunk_count,
                            )
                            break
                    ev = obj.get("event", {})
                    for key in ev:
                        event_types_seen.add(key)
                    if first_output:
                        voice_log.info("Nova Sonic receiver: first output from Bedrock, keys=%s", list(ev.keys()))
                        first_output = False
                    if "textOutput" in ev:
                        to = ev["textOutput"]
                        role = (to.get("role") or "ASSISTANT").lower()
                        content = (to.get("content") or "").strip()
                        if content and "{ \"interrupted\" : true }" not in content:
                            transcript.append((role if role in ("user", "agent") else "agent", content))
                            snippet = content[:60] + "..." if len(content) > 60 else content
                            voice_log.info("Nova Sonic receiver: textOutput role=%s snippet=%r", role, snippet)
                    if "audioOutput" in ev:
                        b64 = (ev["audioOutput"].get("content") or "").strip()
                        if b64:
                            try:
                                pcm = base64.b64decode(b64)
                                mulaw = _pcm_to_mulaw(pcm)
                                await audio_out_queue.put(mulaw)
                                out_chunk_count += 1
                                if out_chunk_count == 1:
                                    voice_log.info("Nova Sonic receiver: first audio chunk to Twilio (%d bytes mulaw)", len(mulaw))
                                if out_chunk_count % 50 == 0:
                                    voice_log.info("Nova Sonic receiver: %d audio chunks sent to Twilio", out_chunk_count)
                            except Exception as e:
                                log.warning("Nova Sonic audio decode: %s", e)
            except StopAsyncIteration:
                voice_log.info("Nova Sonic receiver: stream ended (StopAsyncIteration), event_types_seen=%s, out_audio_chunks=%d", event_types_seen, out_chunk_count)
            except asyncio.CancelledError:
                voice_log.info("Nova Sonic receiver: cancelled, event_types_seen=%s, out_audio_chunks=%d", event_types_seen, out_chunk_count)
            except Exception as e:
                log.warning("Nova Sonic receiver: %s (event_types_seen=%s, out_audio_chunks=%d)", e, event_types_seen, out_chunk_count)
            finally:
                if out_chunk_count == 0 and first_output:
                    voice_log.warning("Nova Sonic receiver: no output received from Bedrock before exit (model may not be responding)")
                end_event.set()
                await audio_out_queue.put(None)

        recv_task = asyncio.create_task(receiver())
        try:
            await sender()
            # Let receiver drain remaining events (transcript, etc.) after we closed the input stream
            try:
                await asyncio.wait_for(recv_task, timeout=15.0)
            except asyncio.TimeoutError:
                voice_log.info("Nova Sonic: receiver drain timed out after 15s")
                recv_task.cancel()
                try:
                    await recv_task
                except asyncio.CancelledError:
                    pass
        finally:
            if not recv_task.done():
                recv_task.cancel()
                try:
                    await recv_task
                except asyncio.CancelledError:
                    pass
    finally:
        if prev_ak is not None:
            os.environ["AWS_ACCESS_KEY_ID"] = prev_ak
        elif "AWS_ACCESS_KEY_ID" in os.environ:
            del os.environ["AWS_ACCESS_KEY_ID"]
        if prev_sk is not None:
            os.environ["AWS_SECRET_ACCESS_KEY"] = prev_sk
        elif "AWS_SECRET_ACCESS_KEY" in os.environ:
            del os.environ["AWS_SECRET_ACCESS_KEY"]
        if prev_region is not None:
            os.environ["AWS_DEFAULT_REGION"] = prev_region
        elif "AWS_DEFAULT_REGION" in os.environ:
            del os.environ["AWS_DEFAULT_REGION"]


def _build_request_stream(
    agent_prompt: str,
    greeting: str,
    audio_in_queue: asyncio.Queue,
    loop: asyncio.AbstractEventLoop,
) -> Iterator[dict]:
    """Build the bidirectional input stream for boto3 path: session + prompt + system + audio chunks."""

    prompt_name = str(uuid.uuid4())
    content_name = str(uuid.uuid4())
    audio_content_name = str(uuid.uuid4())

    # 1) sessionStart
    yield {"event": {"sessionStart": {"inferenceConfiguration": {"maxTokens": 1024, "topP": 0.9, "temperature": 0.7}}}}

    # 2) promptStart (output: 8kHz PCM to match Twilio)
    yield {
        "event": {
            "promptStart": {
                "promptName": prompt_name,
                "textOutputConfiguration": {"mediaType": "text/plain"},
                "audioOutputConfiguration": {
                    "mediaType": "audio/lpcm",
                    "sampleRateHertz": SAMPLE_RATE,
                    "sampleSizeBits": 16,
                    "channelCount": 1,
                    "voiceId": "matthew",
                    "encoding": "base64",
                    "audioType": "SPEECH",
                },
            }
        }
    }

    # 3) System prompt
    system_text = f"{agent_prompt}\n\nStart the call by saying exactly: {greeting}"
    yield {"event": {"contentStart": {"promptName": prompt_name, "contentName": content_name, "type": "TEXT", "interactive": False, "role": "SYSTEM", "textInputConfiguration": {"mediaType": "text/plain"}}}}
    yield {"event": {"textInput": {"promptName": prompt_name, "contentName": content_name, "content": system_text}}}
    yield {"event": {"contentEnd": {"promptName": prompt_name, "contentName": content_name}}}

    # 4) Audio input stream
    yield {
        "event": {
            "contentStart": {
                "promptName": prompt_name,
                "contentName": audio_content_name,
                "type": "AUDIO",
                "interactive": True,
                "role": "USER",
                "audioInputConfiguration": {
                    "mediaType": "audio/lpcm",
                    "sampleRateHertz": SAMPLE_RATE,
                    "sampleSizeBits": 16,
                    "channelCount": 1,
                    "audioType": "SPEECH",
                    "encoding": "base64",
                },
            }
        }
    }

    def get_audio_chunk():
        return asyncio.run_coroutine_threadsafe(audio_in_queue.get(), loop).result()

    while True:
        chunk = get_audio_chunk()
        if chunk is None:
            break
        pcm = _mulaw_to_pcm(chunk)
        b64 = base64.b64encode(pcm).decode("ascii")
        yield {"event": {"audioInput": {"promptName": prompt_name, "contentName": audio_content_name, "content": b64}}}

    yield {"event": {"contentEnd": {"promptName": prompt_name, "contentName": audio_content_name}}}
    yield {"event": {"promptEnd": {"promptName": prompt_name}}}
    yield {"event": {"sessionEnd": {}}}


def _run_bedrock_stream_sync(
    agent_prompt: str,
    greeting: str,
    audio_in_queue: asyncio.Queue,
    audio_out_queue: asyncio.Queue,
    transcript: list,
    end_event: asyncio.Event,
    loop: asyncio.AbstractEventLoop,
) -> None:
    """Fallback: run via boto3 in executor (boto3 does not support bidirectional stream yet)."""
    import boto3

    settings = get_settings()
    model_id = settings.nova_sonic_model_id or "amazon.nova-sonic-v1:0"
    region = settings.nova_sonic_region or "us-east-1"
    ak, sk = _get_aws_credentials()
    if not ak or not sk:
        log.error("Nova Sonic: missing AWS credentials")
        asyncio.run_coroutine_threadsafe(audio_out_queue.put(None), loop).result()
        end_event.set()
        return

    client = boto3.client("bedrock-runtime", region_name=region, aws_access_key_id=ak, aws_secret_access_key=sk)
    invoke_bidi = getattr(client, "invoke_model_with_bidirectional_stream", None)
    if not invoke_bidi:
        log.error(
            "Nova Sonic: invoke_model_with_bidirectional_stream not found. "
            "Install: pip install aws_sdk_bedrock_runtime (Python 3.12+)."
        )
        asyncio.run_coroutine_threadsafe(audio_out_queue.put(None), loop).result()
        end_event.set()
        return

    def body_with_chunk_format():
        for event in _build_request_stream(agent_prompt, greeting, audio_in_queue, loop):
            yield {"chunk": {"bytes": json.dumps(event).encode("utf-8")}}

    try:
        response = invoke_bidi(modelId=model_id, body=body_with_chunk_format())
        response_body = response.get("body") or []
        for event in response_body:
            if not event.get("chunk") or not event["chunk"].get("bytes"):
                continue
            raw = event["chunk"]["bytes"]
            data = raw.decode("utf-8") if isinstance(raw, (bytes, bytearray)) else str(raw)
            try:
                obj = json.loads(data)
            except json.JSONDecodeError:
                continue
            ev = obj.get("event", {})
            if "textOutput" in ev:
                to = ev["textOutput"]
                role = (to.get("role") or "ASSISTANT").lower()
                content = (to.get("content") or "").strip()
                if content and "{ \"interrupted\" : true }" not in content:
                    transcript.append((role if role in ("user", "agent") else "agent", content))
            if "audioOutput" in ev:
                b64 = (ev["audioOutput"].get("content") or "").strip()
                if b64:
                    try:
                        pcm = base64.b64decode(b64)
                        mulaw = _pcm_to_mulaw(pcm)
                        asyncio.run_coroutine_threadsafe(audio_out_queue.put(mulaw), loop).result()
                    except Exception as e:
                        log.warning("Nova Sonic audio decode: %s", e)
    except Exception as e:
        log.exception("Nova Sonic bridge error: %s", e)
    finally:
        asyncio.run_coroutine_threadsafe(audio_out_queue.put(None), loop).result()
        end_event.set()


async def run_nova_sonic_bridge(
    agent_prompt: str,
    greeting: str,
    audio_in_queue: asyncio.Queue,
    audio_out_queue: asyncio.Queue,
    transcript: list,
    end_event: asyncio.Event,
) -> None:
    """
    Run the Bedrock Nova Sonic bidirectional stream. Uses aws_sdk_bedrock_runtime when
    available (recommended); otherwise falls back to boto3 (which does not support the API yet).
    """
    if _has_experimental_sdk():
        voice_log.info("Nova Sonic: using experimental SDK (async bridge)")
        await _run_nova_sonic_bridge_async(
            agent_prompt, greeting, audio_in_queue, audio_out_queue, transcript, end_event
        )
    else:
        voice_log.info("Nova Sonic: using boto3 fallback (bidirectional stream not supported)")
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: _run_bedrock_stream_sync(
                agent_prompt, greeting, audio_in_queue, audio_out_queue, transcript, end_event, loop
            ),
        )
