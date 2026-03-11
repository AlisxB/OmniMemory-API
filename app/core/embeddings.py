"""
Serviço de Embeddings — versão refatorada.

Usa FastEmbed (inference local) com suporte futuro a Gemini via flag.
Modelo: paraphrase-multilingual-mpnet-base-v2 (768 dims, multilingual).
"""
import logging
from typing import List

from ..config import settings

logger = logging.getLogger(__name__)

EMBEDDING_DIM = 768


class EmbeddingService:
    """Geração de embeddings vetoriais para busca semântica."""

    _model = None

    @classmethod
    def _get_model(cls):
        if cls._model is None:
            try:
                from fastembed import TextEmbedding
                logger.info("Inicializando FastEmbed (paraphrase-multilingual-mpnet-base-v2)...")
                cls._model = TextEmbedding(
                    model_name="sentence-transformers/paraphrase-multilingual-mpnet-base-v2"
                )
                logger.info("FastEmbed pronto.")
            except Exception as e:
                logger.error(f"Falha ao carregar FastEmbed: {e}")
        return cls._model

    @classmethod
    def get_embedding(cls, text: str) -> List[float]:
        """
        Gera embedding de 768 dimensões para o texto fornecido.
        Retorna vetor zero se o texto estiver vazio ou ocorrer erro.
        """
        if not settings.enable_embeddings:
            return [0.0] * EMBEDDING_DIM

        if not text or not text.strip():
            return [0.0] * EMBEDDING_DIM

        try:
            model = cls._get_model()
            if not model:
                return [0.0] * EMBEDDING_DIM

            embeddings = list(model.embed([text.strip()]))
            if not embeddings:
                return [0.0] * EMBEDDING_DIM

            emb = embeddings[0].tolist()

            # Garantir exatamente 768 dimensões
            if len(emb) > EMBEDDING_DIM:
                return emb[:EMBEDDING_DIM]
            elif len(emb) < EMBEDDING_DIM:
                return emb + [0.0] * (EMBEDDING_DIM - len(emb))
            return emb

        except Exception as e:
            logger.error(f"Embedding generation failed: {e}")
            return [0.0] * EMBEDDING_DIM

    @staticmethod
    def is_zero_vector(vec: List[float]) -> bool:
        """Verifica se o vetor é o vetor zero (sem embedding real)."""
        return all(v == 0.0 for v in vec)
