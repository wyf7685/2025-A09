from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import FileResponse

from app.services.datasource import temp_file_service

router = APIRouter(prefix="/files", tags=["Files"])


@router.get("/{file_id}")
async def download_file(file_id: str, token: str = Query()) -> FileResponse:
    entry = temp_file_service.get_entry(file_id)
    if entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

    file_path, metadata = entry
    if metadata.get("token") != token or not (file_name := metadata.get("filename")):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

    return FileResponse(path=file_path, filename=file_name, media_type="application/octet-stream")
