"""书籍 CRUD 路由(详见 v6 plan §Phase B)。

代理到 book-service:
- GET    /api/books                       → book-service /internal/books
- POST   /api/books                       → book-service /internal/books
- GET    /api/books/{id}                 → book-service /internal/books/{id}
- PUT    /api/books/{id}                 → book-service /internal/books/{id}
- DELETE /api/books/{id}                 → book-service /internal/books/{id}
- GET    /api/books/{id}/chapters        → book-service /internal/books/{id}/chapters
- POST   /api/books/{id}/chapters/import → book-service /internal/books/{id}/chapters/import
- GET    /api/books/{id}/export          → book-service /internal/books/{id}/export

⚠️ 注意路由顺序:`/chapters` 必须在 `/{book_id}` 之前,否则会被 book_id 吞掉。
"""
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response
from minbook_common.http_client import SignedHTTPClient
from minbook_common.middleware import verify_user_token

from ..config import get_settings

router = APIRouter()
settings = get_settings()


@router.get("")
async def list_books(request: Request, user=Depends(verify_user_token)):
    qs = str(request.url.query) if request.url.query else ""
    async with SignedHTTPClient("gateway") as client:
        r = await client.get(f"{settings.book_service_url}/internal/books?{qs}")
    return Response(content=r.content, status_code=r.status_code,
                    media_type=r.headers.get("content-type", "application/json"))


@router.post("", status_code=201)
async def create_book(request: Request, user=Depends(verify_user_token)):
    body = await request.body()
    async with SignedHTTPClient("gateway") as client:
        r = await client.post(
            f"{settings.book_service_url}/internal/books",
            content=body,
            headers={"Content-Type": "application/json"},
        )
    return Response(content=r.content, status_code=r.status_code,
                    media_type=r.headers.get("content-type", "application/json"))


# ⚠️ 必须在 /{book_id} 之前(否则被吞)
@router.get("/{book_id}/chapters")
async def list_chapters(book_id: UUID, request: Request, user=Depends(verify_user_token)):
    qs = str(request.url.query) if request.url.query else ""
    async with SignedHTTPClient("gateway") as client:
        r = await client.get(
            f"{settings.book_service_url}/internal/books/{book_id}/chapters?{qs}"
        )
    return Response(content=r.content, status_code=r.status_code,
                    media_type=r.headers.get("content-type", "application/json"))


@router.post("/{book_id}/chapters/import", status_code=201)
async def import_chapters(book_id: UUID, request: Request, user=Depends(verify_user_token)):
    # multipart 上传:把整个 multipart 透传过去
    body = await request.body()
    async with SignedHTTPClient("gateway") as client:
        r = await client.post(
            f"{settings.book_service_url}/internal/books/{book_id}/chapters/import",
            content=body,
            headers={"Content-Type": request.headers.get("content-type", "multipart/form-data")},
        )
    return Response(content=r.content, status_code=r.status_code,
                    media_type=r.headers.get("content-type", "application/json"))


@router.get("/{book_id}/export")
async def export_book(book_id: UUID, request: Request, user=Depends(verify_user_token)):
    qs = str(request.url.query) if request.url.query else ""
    async with SignedHTTPClient("gateway") as client:
        r = await client.get(
            f"{settings.book_service_url}/internal/books/{book_id}/export?{qs}"
        )
    return Response(content=r.content, status_code=r.status_code,
                    media_type=r.headers.get("content-type", "application/octet-stream"))


@router.get("/{book_id}")
async def get_book(book_id: UUID, user=Depends(verify_user_token)):
    async with SignedHTTPClient("gateway") as client:
        r = await client.get(f"{settings.book_service_url}/internal/books/{book_id}")
    return Response(content=r.content, status_code=r.status_code,
                    media_type=r.headers.get("content-type", "application/json"))


@router.put("/{book_id}")
async def update_book(book_id: UUID, request: Request, user=Depends(verify_user_token)):
    body = await request.body()
    async with SignedHTTPClient("gateway") as client:
        r = await client.put(
            f"{settings.book_service_url}/internal/books/{book_id}",
            content=body,
            headers={"Content-Type": "application/json"},
        )
    return Response(content=r.content, status_code=r.status_code,
                    media_type=r.headers.get("content-type", "application/json"))


@router.delete("/{book_id}", status_code=204)
async def delete_book(book_id: UUID, user=Depends(verify_user_token)):
    async with SignedHTTPClient("gateway") as client:
        r = await client.delete(f"{settings.book_service_url}/internal/books/{book_id}")
    if r.status_code == 204:
        return Response(status_code=204)
    return Response(content=r.content, status_code=r.status_code,
                    media_type=r.headers.get("content-type", "application/json"))
