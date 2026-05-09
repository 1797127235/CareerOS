"""对话服务模块 —— 路由导出

使用方式:
    from backend.services import chat
    app.include_router(chat.router, prefix="/api")
"""

from backend.services.chat.routes import router

__all__ = ["router"]
