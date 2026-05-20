"""
memory.py — Memoria dual del agente.

Corto plazo:  ConversationBufferMemory (LangChain)
              Persiste solo durante la sesión activa.
              Mantiene el historial de mensajes para coherencia entre turnos.

Largo plazo:  Índice FAISS de casos anteriores anonimizados.
              Se actualiza al cierre de cada sesión mediante el pipeline
              de anonimización. Permite recuperar casos similares por
              similitud semántica.
"""

import os
import json
import pickle
from datetime import datetime
from typing import Optional

from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from config import CONFIG
from anonymizer import anonimizar


# ---------------------------------------------------------------------------
# Memoria de corto plazo
# ---------------------------------------------------------------------------

class MemoriaCortoplazo:
    """
    Buffer de mensajes de la sesión activa.
    Usa BaseMessage de langchain_core para compatibilidad con LangGraph.
    """

    def __init__(self):
        self._mensajes: list[BaseMessage] = []

    def agregar_turno(self, consulta: str, respuesta: str) -> None:
        """Registra un par consulta/respuesta en el buffer."""
        self._mensajes.append(HumanMessage(content=consulta))
        self._mensajes.append(AIMessage(content=respuesta))

    def obtener_historial(self) -> list[BaseMessage]:
        """Retorna la lista de mensajes acumulados en la sesión."""
        return self._mensajes

    def obtener_historial_texto(self) -> str:
        """Retorna el historial como texto plano para inyectar en prompts."""
        if not self._mensajes:
            return ""
        lineas = []
        for msg in self._mensajes:
            rol = "Usuario" if msg.type == "human" else "Agente"
            lineas.append(f"{rol}: {msg.content}")
        return "\n".join(lineas)

    def limpiar(self) -> None:
        """Limpia el buffer al cerrar sesión."""
        self._mensajes = []

    def esta_vacia(self) -> bool:
        return len(self._mensajes) == 0


# ---------------------------------------------------------------------------
# Memoria de largo plazo
# ---------------------------------------------------------------------------

def _get_embeddings() -> OpenAIEmbeddings:
    return OpenAIEmbeddings(
        model=CONFIG.embedding_model,
        base_url=CONFIG.api_base_url,
        api_key=os.getenv("GH_TOKEN") or os.getenv("GITHUB_TOKEN"),
    )


class MemoriaLargoplazo:
    """
    Índice FAISS de casos anteriores anonimizados.
    Persiste entre sesiones en casos/casos.index y casos/casos.pkl.
    """

    def __init__(self):
        self._embeddings = _get_embeddings()
        self._store: Optional[FAISS] = None
        self._metadatos: list[dict] = []   # metadatos de cada caso persistido
        self._cargar()

    def _cargar(self) -> None:
        """Carga el índice desde disco si existe."""
        if os.path.exists(CONFIG.casos_index):
            try:
                self._store = FAISS.load_local(
                    CONFIG.casos_dir,
                    self._embeddings,
                    index_name="casos",
                    allow_dangerous_deserialization=True,
                )
                pkl_path = CONFIG.casos_pkl
                if os.path.exists(pkl_path):
                    with open(pkl_path, "rb") as f:
                        self._metadatos = pickle.load(f)
            except Exception as e:
                print(f"[memory] No se pudo cargar el índice de casos: {e}")
                self._store = None
                self._metadatos = []

    def _guardar(self) -> None:
        """Persiste el índice y metadatos a disco."""
        os.makedirs(CONFIG.casos_dir, exist_ok=True)
        if self._store:
            self._store.save_local(CONFIG.casos_dir, index_name="casos")
        with open(CONFIG.casos_pkl, "wb") as f:
            pickle.dump(self._metadatos, f)

    def persistir_caso(self, texto_caso: str, metadata: dict = None) -> dict:
        """
        Anonimiza y persiste un caso en el índice de largo plazo.

        Args:
            texto_caso: texto completo del caso (consultas + respuestas)
            metadata:   datos adicionales (fecha, modo, etc.)

        Returns:
            dict con texto anonimizado y mapa de reemplazos
        """
        texto_anonimizado, mapa = anonimizar(texto_caso)

        meta = {
            "fecha": datetime.now().isoformat(),
            "longitud_original": len(texto_caso),
            **(metadata or {}),
        }

        doc = Document(
            page_content=texto_anonimizado,
            metadata=meta,
        )

        if self._store is None:
            self._store = FAISS.from_documents([doc], self._embeddings)
        else:
            self._store.add_documents([doc])

        self._metadatos.append(meta)
        self._guardar()

        return {"texto_anonimizado": texto_anonimizado, "mapa": mapa}

    def buscar_casos_similares(self, query: str, k: int = 3) -> list[Document]:
        """
        Recupera los k casos más similares a la consulta.

        Args:
            query: consulta del usuario
            k:     número de casos a recuperar

        Returns:
            lista de Documents con los casos similares
        """
        if self._store is None:
            return []
        try:
            return self._store.similarity_search(query, k=k)
        except Exception as e:
            print(f"[memory] Error en búsqueda de casos: {e}")
            return []

    def tiene_casos(self) -> bool:
        return self._store is not None and len(self._metadatos) > 0

    def total_casos(self) -> int:
        return len(self._metadatos)


# ---------------------------------------------------------------------------
# Fábrica — una instancia de largo plazo compartida entre sesiones
# ---------------------------------------------------------------------------

_largo_plazo_instance: Optional[MemoriaLargoplazo] = None


def get_memoria_largo_plazo() -> MemoriaLargoplazo:
    """Retorna la instancia singleton de memoria de largo plazo."""
    global _largo_plazo_instance
    if _largo_plazo_instance is None:
        _largo_plazo_instance = MemoriaLargoplazo()
    return _largo_plazo_instance


def nueva_sesion() -> MemoriaCortoplazo:
    """Crea y retorna una nueva instancia de memoria de corto plazo."""
    return MemoriaCortoplazo()
