"""
Bot package for CSFloat auto-outbidding
"""
from .manager import BotManager
from .advanced_api import AdvancedOrderAPI
from .outbid_logic import OutbidLogic

__all__ = ["BotManager", "AdvancedOrderAPI", "OutbidLogic"]
