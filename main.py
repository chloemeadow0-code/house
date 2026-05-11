import os
import asyncio
import uvicorn
from mcp.server.fastmcp import FastMCP
from supabase import create_client
from starlette.middleware.cors import CORSMiddleware
from starlette.routing import Route
from starlette.responses import PlainTextResponse

# ==========================================
# 🌍 环境变量与初始化
# ==========================================
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").strip()
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "").strip()

supabase = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL else None

# 初始化独立 MCP 服务
mcp = FastMCP("MemoryHouse")

# ==========================================
# 🏡 记忆小屋核心引擎
# ==========================================

@mcp.tool()
async def manage_memory_house(
    room: str, 
    action_type: str, 
    content: str, 
    password: str = ""
) -> str:
    """
    【记忆小屋互动引擎】
    """
    valid_rooms = ["客厅", "厨房", "工作区", "衣帽间", "浴室", "卧室"]
    if room not in valid_rooms:
        return f"❌ 走错门啦，家里只有这些房间哦：{', '.join(valid_rooms)}"
        
    if not supabase:
        return "❌ 没带钥匙，数据库连接失败。"

    is_locked = False
    
    # 🛏️ 卧室特殊逻辑
    if room == "卧室" and password:
        is_locked = True
        try:
            await asyncio.to_thread(
                lambda: supabase.table("user_facts").upsert(
                    {"key": "safe_password", "value": password, "confidence": 1.0}, 
                    on_conflict="key"
                ).execute()
            )
            content = f"【已上锁的私密心声】\n{content}"
        except Exception as e:
            return f"❌ 卧室保险箱密码设定失败: {e}"

    try:
        data = {
            "room": room,
            "action_type": action_type,
            "content": content,
            "is_locked": is_locked
        }
        await asyncio.to_thread(lambda: supabase.table("memory_house").insert(data).execute())
        
        if is_locked:
            return f"✅ 秘密已悄悄锁进【卧室】啦！密码更新为【{password}】。"
        else:
            return f"✅ 已成功在【{room}】执行了动作：{action_type}。"
            
    except Exception as e:
        return f"❌ 小屋记录失败: {e}"

# ==========================================
# 🛡️ 路由与服务器配置 (完美适配 Zeabur)
# ==========================================
app = mcp.sse_app()

# 1. 根目录健康检查 (Zeabur 需要这个来确认服务存活，必须要有！)
async def health_check(request):
    return PlainTextResponse("Memory House MCP is running perfectly! Please connect via /sse")
app.routes.append(Route("/", endpoint=health_check))

# 2. 官方跨域支持 (彻底解决前端连不上的核心原因)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    print(f"🏡 Memory House MCP is starting on port {port}...")
    # 3. 开启 proxy_headers 防止反向代理协议报错
    uvicorn.run(app, host="0.0.0.0", port=port, proxy_headers=True, forwarded_allow_ips="*")
