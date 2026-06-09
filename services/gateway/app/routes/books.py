"""书籍 CRUD 路由(本计划 v2 暂未实现 book-service,统一返回 501)。

后续 plan v3 / v4 会补 book-service,本占位符保持路由结构稳定。
"""
from fastapi import APIRouter, HTTPException, status

router = APIRouter()


@router.get("")
async def list_books():
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "book-service not yet implemented")


@router.post("")
async def create_book():
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "book-service not yet implemented")


@router.get("/{book_id}")
async def get_book(book_id: str):
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "book-service not yet implemented")


@router.put("/{book_id}")
async def update_book(book_id: str):
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "book-service not yet implemented")


@router.delete("/{book_id}")
async def delete_book(book_id: str):
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "book-service not yet implemented")
