"""Choose a backend explicitly; the gateway defaults to no long-term memory."""

from .base import MemoryGateway, NoneMemory
from .livingmemory import LivingMemoryAdapter
from .local_lite import LocalLiteMemory
from .local_vector import LocalVectorMemory

__all__ = ["LivingMemoryAdapter", "LocalLiteMemory", "LocalVectorMemory",
           "MemoryGateway", "NoneMemory"]
