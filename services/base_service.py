import logging
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)

class BaseService(ABC):
    """服务基类"""

    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    @abstractmethod
    def initialize(self, **kwargs):
        """初始化服务"""
        pass

    def cleanup(self):
        """清理资源"""
        pass