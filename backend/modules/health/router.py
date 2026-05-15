"""健康检查"""

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check():
    # Provider 状态
    provider_info: dict = {"name": "null", "status": "not_initialized", "type": "disabled"}
    try:
        from backend.modules.data_sources.ingestion import get_document_index_provider

        provider = get_document_index_provider()
        if provider is not None:
            status = provider.health_check()
            provider_info = {
                "name": provider.name,
                "status": status.value,
                "type": "vector" if provider.name == "lancedb" else "disabled",
            }
            if status.value == "error":
                provider_info["error"] = getattr(provider, "_error_msg", "未知错误")
    except Exception:
        pass

    return {
        "status": "ok",
        "version": "0.3.0",
        "document_index_provider": provider_info,
    }
