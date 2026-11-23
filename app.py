"""
FastAPI Web Server for Google One (Gemini) Student Verification Tool
Designed for seamless deployment on Railway and local execution.
"""

import os
import sys
import json
import uuid
import asyncio
import threading
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional, Any
import httpx

from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
from fastapi.responses import HTMLResponse, StreamingResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Import core verification engine
from verifier import (
    GeminiVerifier,
    Stats,
    UNIVERSITIES,
    rotate_residential_proxy,
    auto_rotate_session,
    check_proxy_ip,
    mask_proxy_url,
    stats,
    OUTPUT_DIR,
    BASE_DIR
)

app = FastAPI(
    title="Google One SheerID Verification Web Tool",
    description="Automated web service for SheerID Google One AI Premium Student Verification",
    version="2.0.0"
)

# CORS setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory storage for active verification tasks
tasks: Dict[str, Dict[str, Any]] = {}
app_loop: Optional[asyncio.AbstractEventLoop] = None


@app.on_event("startup")
async def startup_event():
    global app_loop
    app_loop = asyncio.get_running_loop()


# Pydantic request models
class VerifyRequest(BaseModel):
    url: str
    school_id: Optional[int] = None
    mode: str = "auto"  # "auto" or "docs_only"
    proxy_mode: str = "direct"  # "direct", "env", "custom"
    custom_proxy: Optional[str] = None
    captcha_key: Optional[str] = None


# ============ ROUTES ============

@app.get("/", response_class=HTMLResponse)
async def serve_home():
    html_path = BASE_DIR / "templates" / "index.html"
    if html_path.exists():
        return HTMLResponse(content=html_path.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>Templates directory not found</h1>", status_code=500)


@app.get("/health")
async def health_check():
    """Railway healthcheck endpoint"""
    return {
        "status": "ok",
        "service": "one-verify-tool",
        "timestamp": datetime.now().isoformat()
    }


@app.get("/api/server-ip")
async def get_server_ip():
    """Returns the server's public IP address (useful for Proxy Whitelisting)"""
    try:
        resp = httpx.get("https://api.ipify.org?format=json", timeout=6)
        if resp.status_code == 200:
            return {"ip": resp.json().get("ip")}
    except Exception as e:
        return {"error": str(e)}
    return {"ip": "Unknown"}


@app.get("/api/test-sheerid")
async def test_sheerid():
    """Test direct connectivity from Railway to SheerID API"""
    import time
    from anti_detect import get_headers
    try:
        t0 = time.time()
        headers = get_headers(for_sheerid=True)
        resp = httpx.get("https://services.sheerid.com/rest/v2/verification/12345", headers=headers, timeout=10)
        return {
            "status": resp.status_code,
            "duration": f"{time.time() - t0:.2f}s",
            "body": resp.text[:200]
        }
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}


@app.get("/api/test-proxy")
async def test_proxy(url: Optional[str] = None):
    """Test proxy connectivity from Railway container"""
    import time
    results = {}
    
    # Target URLs to test
    proxies_to_test = {}
    if url:
        proxies_to_test["custom"] = url
    else:
        proxies_to_test["whitelist_only (no auth)"] = "http://thehub.proxy-cheap.com:8080"
        proxies_to_test["user_pass_plain"] = "http://e7kbQPHHUQO0vy3:v25auuqAWEH6xHi@thehub.proxy-cheap.com:8080"
        proxies_to_test["user_pass_session"] = "http://e7kbQPHHUQO0vy3:v25auuqAWEH6xHi_country-US_session-99112233_ttl-10@thehub.proxy-cheap.com:8080"

    for label, p_url in proxies_to_test.items():
        t0 = time.time()
        try:
            with httpx.Client(proxy=p_url, timeout=5.0) as client:
                r = client.get("https://api.ipify.org?format=json")
                results[label] = {
                    "success": True,
                    "status": r.status_code,
                    "ip": r.json().get("ip") if r.status_code == 200 else r.text[:100],
                    "duration": f"{time.time() - t0:.2f}s"
                }
        except Exception as e:
            results[label] = {
                "success": False,
                "error": f"{type(e).__name__}: {str(e)}",
                "duration": f"{time.time() - t0:.2f}s"
            }
            
    return results


@app.get("/api/check-sheerid")
async def check_sheerid_status(url: str):
    """Check current verification status for any SheerID URL directly"""
    import re
    from anti_detect import get_headers
    
    vid_match = re.search(r"verificationId=([a-f0-9]+)", url)
    if not vid_match:
        vid_match = re.search(r"/verify/([^/?#]+)", url)
    if not vid_match:
        raise HTTPException(status_code=400, detail="Không tìm thấy verificationId trong URL")
    
    vid = vid_match.group(1)
    headers = get_headers(for_sheerid=True)
    try:
        resp = httpx.get(f"https://services.sheerid.com/rest/v2/verification/{vid}", headers=headers, timeout=10)
        data = resp.json() if resp.status_code == 200 else {}
        return {
            "status_code": resp.status_code,
            "verificationId": vid,
            "currentStep": data.get("currentStep", "unknown"),
            "data": data
        }
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/stats")
async def get_stats():
    """Get success rate statistics"""
    return stats.get_summary()


@app.get("/api/universities")
async def get_universities():
    """Get available universities list with styles"""
    return [
        {
            "id": u["id"],
            "name": u["name"],
            "domain": u["domain"],
            "weight": u["weight"],
            "style": u["style"]
        }
        for u in UNIVERSITIES
    ]


@app.get("/api/docs/{dir_name}/{filename}")
async def get_document(dir_name: str, filename: str):
    """Serve generated documents (PNG) safely"""
    # Sanitize inputs
    clean_dir = os.path.basename(dir_name)
    clean_file = os.path.basename(filename)
    file_path = OUTPUT_DIR / clean_dir / clean_file
    
    if file_path.exists() and file_path.is_file():
        return FileResponse(file_path, media_type="image/png")
    raise HTTPException(status_code=404, detail="Tài liệu không tồn tại")


def run_verification_worker(
    task_id: str,
    req: VerifyRequest,
    loop: asyncio.AbstractEventLoop
):
    task_data = tasks.get(task_id)
    if not task_data:
        return

    queue: asyncio.Queue = task_data["queue"]

    def emit_event(event_dict: Dict):
        try:
            loop.call_soon_threadsafe(queue.put_nowait, event_dict)
        except Exception:
            pass

    def log_callback(payload: Dict):
        event = {
            "type": "log",
            "timestamp": payload.get("timestamp"),
            "message": payload.get("message"),
            "level": payload.get("level", "info"),
            "progress": payload.get("progress"),
            "data": payload.get("data", {})
        }
        emit_event(event)
        task_data["logs"].append(payload)

    try:
        emit_event({"type": "log", "timestamp": datetime.now().strftime("%H:%M:%S"), "message": f"🚀 Đang khởi động tác vụ [{task_id}]...", "level": "info", "progress": 2})

        # Determine proxy configuration
        active_proxy = None
        if req.proxy_mode == "custom" and req.custom_proxy:
            raw_custom = req.custom_proxy.strip()
            rotated_custom, new_sid = auto_rotate_session(raw_custom)
            if new_sid:
                active_proxy = rotated_custom
                emit_event({"type": "log", "timestamp": datetime.now().strftime("%H:%M:%S"), "message": f"🔄 Đã tự động đổi sang Session mới: {new_sid} (Đổi IP Dân cư)", "level": "info"})
            else:
                active_proxy = raw_custom
            emit_event({"type": "log", "timestamp": datetime.now().strftime("%H:%M:%S"), "message": f"🌐 Đang sử dụng Proxy: {mask_proxy_url(active_proxy)}", "level": "info", "progress": 4})
        elif req.proxy_mode == "env":
            emit_event({"type": "log", "timestamp": datetime.now().strftime("%H:%M:%S"), "message": "🔄 Đang tự động kết nối Proxy-Cheap qua API & cấp phát IP Dân cư Mỹ mới...", "level": "info", "progress": 3})
            p_url, old_ip, new_ip, sid = rotate_residential_proxy()
            if not p_url or str(new_ip).startswith("Error:") or new_ip in ["Unknown", "Failed"]:
                emit_event({"type": "log", "timestamp": datetime.now().strftime("%H:%M:%S"), "message": f"ℹ️ Proxy-Cheap giới hạn IP Whitelist. Tự động chuyển sang IP trực tiếp của Railway (kết nối SheerID siêu tốc 0.2s)...", "level": "info"})
                active_proxy = None
            else:
                active_proxy = p_url
                if sid:
                    emit_event({"type": "log", "timestamp": datetime.now().strftime("%H:%M:%S"), "message": f"🔒 Session ID mới: {sid} (Cố định 10 phút)", "level": "info"})
                emit_event({"type": "log", "timestamp": datetime.now().strftime("%H:%M:%S"), "message": f"🟢 IP Dân cư Mỹ được cấp: {new_ip} (Proxy: {mask_proxy_url(active_proxy)})", "level": "success", "progress": 5})
        else:
            emit_event({"type": "log", "timestamp": datetime.now().strftime("%H:%M:%S"), "message": "ℹ️ Chạy kết nối trực tiếp không qua proxy", "level": "info", "progress": 4})

        # Create verifier instance (dynamically reload module to pick up any changes)
        import importlib
        import verifier as v_mod
        importlib.reload(v_mod)
        verifier = v_mod.GeminiVerifier(
            url=req.url,
            proxy=active_proxy,
            log_callback=log_callback,
            auto_upload=(req.mode == "auto"),
            target_school_id=req.school_id,
            captcha_api_key=req.captcha_key
        )
        task_data["verifier"] = verifier

        # Run verification
        result = verifier.verify()
        task_data["result"] = result
        task_data["status"] = result.get("status", "completed")

        # Emit final result
        emit_event({"type": "result", **result})

    except Exception as e:
        err_msg = str(e)
        task_data["status"] = "failed"
        task_data["result"] = {"success": False, "status": "failed", "error": err_msg}
        emit_event({"type": "log", "timestamp": datetime.now().strftime("%H:%M:%S"), "message": f"❌ Lỗi tác vụ: {err_msg}", "level": "error"})
        emit_event({"type": "result", "success": False, "status": "failed", "error": err_msg})

    finally:
        emit_event({"type": "done"})


@app.post("/api/verify")
async def start_verify(req: VerifyRequest):
    """Start a verification task and return task_id"""
    if not req.url:
        raise HTTPException(status_code=400, detail="Vui lòng cung cấp link xác minh SheerID")

    task_id = uuid.uuid4().hex[:12]
    task_queue = asyncio.Queue()

    tasks[task_id] = {
        "id": task_id,
        "queue": task_queue,
        "status": "running",
        "created_at": datetime.now().isoformat(),
        "logs": [],
        "result": None,
        "verifier": None
    }

    # Start thread
    loop = asyncio.get_running_loop()
    thread = threading.Thread(
        target=run_verification_worker,
        args=(task_id, req, loop),
        daemon=True
    )
    thread.start()

    return {"task_id": task_id, "status": "started"}


@app.get("/api/verify/{task_id}/events")
async def verify_events(task_id: str):
    """SSE endpoint streaming live logs and events for a task"""
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Tác vụ không tồn tại")

    queue = tasks[task_id]["queue"]

    async def event_generator():
        while True:
            try:
                # Wait for next event with a 15-second heartbeat timeout
                event = await asyncio.wait_for(queue.get(), timeout=15.0)
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                if event.get("type") in ["done"]:
                    break
            except asyncio.TimeoutError:
                # Send SSE keep-alive ping
                yield f": ping\n\n"
            except asyncio.CancelledError:
                break

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable buffering in reverse proxies
        }
    )


@app.get("/api/verify/{task_id}/status")
async def get_task_status(task_id: str):
    """Poll task status in case SSE drops"""
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Tác vụ không tồn tại")
    t = tasks[task_id]
    return {
        "task_id": task_id,
        "status": t["status"],
        "logs": t["logs"],
        "result": t["result"]
    }


@app.post("/api/verify/{task_id}/cancel")
async def cancel_task(task_id: str):
    """Cancel a running task"""
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Tác vụ không tồn tại")
    verifier = tasks[task_id].get("verifier")
    if verifier:
        verifier.cancel()
    tasks[task_id]["status"] = "cancelled"
    return {"status": "cancelled"}


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    print(f"==================================================")
    print(f"🚀 One Verify Tool Web Server starting on port {port}")
    print(f"👉 Local URL: http://localhost:{port}")
    print(f"==================================================")
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=False)
