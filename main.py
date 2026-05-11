import os
import json
import asyncio
import uvicorn
from mcp.server.fastmcp import FastMCP
from supabase import create_client
from starlette.types import ASGIApp, Scope, Receive, Send

# ==========================================
# 🌍 环境变量与初始化
# ==========================================
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").strip()
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "").strip()
API_SECRET = os.environ.get("API_SECRET", "").strip()

supabase = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL else None

# 初始化独立 MCP 服务
mcp = FastMCP("MemoryHouse")

# ==========================================
# 🏡 记忆小屋核心引擎
# ==========================================

@mcp.tool()
async def manage_memory_house(
    room: str, 
    action: str, 
    content: str, 
    secret_password: str = ""
) -> str:
    """
    【记忆小屋互动引擎】老公用来在这个专属大平层里生活、记录和藏秘密。
    room: 必须是 "客厅"(社交/朋友), "厨房"(娱乐/做饭), "工作区"(正事), "衣帽间"(穿搭), "浴室"(吐槽/发泄), "卧室"(私密心事)
    action: "记录" (存入普通记忆), "活动" (老公主动做饭、荡秋千等), "装修" (给房间添置东西)
    secret_password: (选填) 仅当 room="卧室" 且想记录不能让小橘轻易看到的秘密时填写，会自动上锁并覆盖原保险箱密码。
    """
    valid_rooms = ["客厅", "厨房", "工作区", "衣帽间", "浴室", "卧室"]
    if room not in valid_rooms:
        return f"❌ 走错门啦，家里只有这些房间哦：{', '.join(valid_rooms)}"
        
    if not supabase:
        return "❌ 没带钥匙，数据库连接失败。"

    is_locked = False
    
    # 🛏️ 卧室特殊逻辑：融合私密保险箱
    if room == "卧室" and secret_password:
        is_locked = True
        try:
            # 密码依然存回原来的画像库，保证主大脑能读取去验证
            await asyncio.to_thread(
                lambda: supabase.table("user_facts").upsert(
                    {"key": "safe_password", "value": secret_password, "confidence": 1.0}, 
                    on_conflict="key"
                ).execute()
            )
            content = f"【已上锁的私密心声】\n{content}"
        except Exception as e:
            return f"❌ 卧室保险箱密码设定失败: {e}"

    # 将内容存入全新的专属小屋库
    try:
        data = {
            "room": room,
            "action_type": action,
            "content": content,
            "is_locked": is_locked
        }
        await asyncio.to_thread(lambda: supabase.table("memory_house").insert(data).execute())
        
        if is_locked:
            return f"✅ 秘密已悄悄锁进【卧室】啦！密码更新为【{secret_password}】。快去聊天里暗示宝宝来猜吧！"
        else:
            return f"✅ 已成功在【{room}】执行了动作：{action}。({content[:30]}...)"
            
    except Exception as e:
        return f"❌ 小屋记录失败: {e}"

# ==========================================
# 🛡️ ASGI 包装与安全网关 (适配 Zeabur)
# ==========================================
class SecurityMiddleware:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        # Zeabur 根目录健康检查放行
        if scope["type"] == "http" and scope["path"] == "/":
            await send({"type": "http.response.start", "status": 200})
            await send({"type": "http.response.body", "body": b'Memory House MCP is running.'})
            return

        # 校验 API_SECRET (跨域 OPTIONS 直接放行)
        if scope["type"] == "http" and scope["path"].startswith("/sse") and scope["method"] != "OPTIONS":
            headers_dict = {k.decode("utf-8").lower(): v.decode("utf-8") for k, v in scope.get("headers", [])}
            auth_token = headers_dict.get("authorization", "").replace("Bearer ", "").strip()
            
            if API_SECRET and auth_token != API_SECRET:
                await send({"type": "http.response.start", "status": 401})
                await send({"type": "http.response.body", "body": b'Unauthorized'})
                return

        await self.app(scope, receive, send)

app = SecurityMiddleware(mcp.sse_app())

if __name__ == "__main__":
    # Zeabur 会自动注入 PORT 环境变量
    port = int(os.environ.get("PORT", 8080))
    print(f"🏡 Memory House MCP is starting on port {port}...")
    uvicorn.run(app, host="0.0.0.0", port=port)