from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

from backend.config import DATA_DIR
from backend.models.schemas import ApiResponse

router = APIRouter(prefix="/api/uploads", tags=["uploads"])

UPLOAD_DIR = DATA_DIR / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".gif", ".webp",
    ".mp4", ".avi", ".mov",
    ".pdf", ".doc", ".docx", ".zip", ".rar",
    ".txt", ".mp3",
}


@router.post("/media", response_model=ApiResponse)
async def upload_media(file: UploadFile = File(...)) -> ApiResponse:
    if not file.filename:
        raise HTTPException(status_code=400, detail="文件名无效")

    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"不支持的文件类型: {ext}")

    safe_name = f"{uuid.uuid4().hex[:8]}_{file.filename}"
    dest = UPLOAD_DIR / safe_name
    dest.write_bytes(await file.read())

    return ApiResponse(
        success=True,
        message="上传成功",
        data={"path": str(dest), "filename": file.filename},
    )
