"""Provider 包初始化:暴露 BaseProvider + registry。"""
from .base import BaseProvider
from .registry import get_provider

__all__ = ["BaseProvider", "get_provider"]
