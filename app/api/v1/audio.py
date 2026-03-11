"""Endpoint de áudio — transcrição via Groq Whisper."""
import logging
import os
import tempfile
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from ...database import get_db
from ...core.responses import wrap_response
from ...config import settings
from ...redis import RedisManager
from ..deps import validate_tenant_access

logger = logging.getLogger(__name__)
router = APIRouter(tags=["v1 — audio"])


@router.post("/audio/process", summary="Transcrever áudio (Groq Whisper)")
async def process_audio(
    request: Request,
    tenant_id: str,
    file: Optional[UploadFile] = File(None),
    url: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
):
    """
    Recebe um áudio via upload ou URL, converte para MP3 e transcreve usando Groq Whisper v3.
    Suporta: OGG, MP3, WAV, WEBM, M4A.
    """
    if not settings.enable_audio:
        raise HTTPException(status_code=503, detail="Processamento de áudio desabilitado.")

    await validate_tenant_access(tenant_id, request.headers.get("X-API-Key"), db)

    if not file and not url:
        raise HTTPException(status_code=400, detail="Forneça 'file' ou 'url'.")

    if not settings.groq_api_key:
        raise HTTPException(status_code=503, detail="GROQ_API_KEY não configurada.")

    temp_input_path = None
    converted_path = None
    filename = "audio"

    try:
        # Determinar sufixo do arquivo
        if file:
            suffix = f"_{file.filename}" if file.filename else ".tmp"
            filename = file.filename or "audio"
        else:
            suffix = ".tmp"
            filename = (url.split("/")[-1].split("?")[0]) or "audio"

        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            if file:
                content = await file.read()
            else:
                logger.info(f"Downloading audio from URL: {url}")
                async with httpx.AsyncClient(timeout=30.0) as client:
                    resp = await client.get(url)
                    resp.raise_for_status()
                    content = resp.content

            tmp.write(content)
            temp_input_path = tmp.name

        # Converter para MP3 via ffmpeg
        converted_path = temp_input_path.rsplit(".", 1)[0] + "_converted.mp3"
        ret = os.system(f'ffmpeg -y -i "{temp_input_path}" -ar 16000 -ac 1 "{converted_path}" -loglevel quiet')
        if ret != 0:
            converted_path = temp_input_path  # Usar original se conversão falhar

        # Transcrever via Groq
        from groq import AsyncGroq
        client = AsyncGroq(api_key=settings.groq_api_key)
        with open(converted_path, "rb") as audio_file:
            transcription = await client.audio.transcriptions.create(
                file=(filename, audio_file),
                model="whisper-large-v3",
                language="pt",
            )

        text = transcription.text.strip()
        await RedisManager.record_usage(tenant_id, tokens=0)

        return wrap_response(
            {"transcription": text, "filename": filename, "tenant_id": tenant_id},
            request.state.request_id,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Audio processing failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erro ao processar áudio: {str(e)}")
    finally:
        for path in [temp_input_path, converted_path]:
            if path and path != temp_input_path and os.path.exists(path):
                try:
                    os.remove(path)
                except Exception:
                    pass
        if temp_input_path and os.path.exists(temp_input_path):
            try:
                os.remove(temp_input_path)
            except Exception:
                pass
