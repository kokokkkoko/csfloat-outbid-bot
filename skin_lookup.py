"""
Skin name lookup utility for CS2/CSGO items
Uses CSFloat API as the single source of truth
"""
import aiohttp
import asyncio
import json
import os
from typing import Optional, Tuple
from loguru import logger

# Persistent cache file path
CACHE_FILE = os.path.join(os.path.dirname(__file__), "data", "skin_cache.json")

# In-memory cache (loaded from file on startup)
_skin_cache: dict = {}
_session: Optional[aiohttp.ClientSession] = None
_session_lock = asyncio.Lock()


def _load_cache():
    """Load cache from file"""
    global _skin_cache
    try:
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                _skin_cache = json.load(f)
            logger.info(f"Loaded {len(_skin_cache)} skins from cache")
    except Exception as e:
        logger.warning(f"Could not load skin cache: {e}")
        _skin_cache = {}


def _save_cache():
    """Save cache to file"""
    try:
        os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
        with open(CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(_skin_cache, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning(f"Could not save skin cache: {e}")


# Load cache on module import
_load_cache()


# Weapon DefIndex -> Name mapping
WEAPON_NAMES = {
    1: "Desert Eagle", 2: "Dual Berettas", 3: "Five-SeveN", 4: "Glock-18",
    7: "AK-47", 8: "AUG", 9: "AWP", 10: "FAMAS", 11: "G3SG1", 13: "Galil AR",
    14: "M249", 16: "M4A4", 17: "MAC-10", 19: "P90", 23: "MP5-SD", 24: "UMP-45",
    25: "XM1014", 26: "PP-Bizon", 27: "MAG-7", 28: "Negev", 29: "Sawed-Off",
    30: "Tec-9", 31: "Zeus x27", 32: "P2000", 33: "MP7", 34: "MP9", 35: "Nova",
    36: "P250", 38: "SCAR-20", 39: "SG 553", 40: "SSG 08", 60: "M4A1-S",
    61: "USP-S", 63: "CZ75-Auto", 64: "R8 Revolver",
    500: "Bayonet", 503: "Flip Knife", 505: "Gut Knife", 506: "Karambit",
    507: "M9 Bayonet", 508: "Huntsman Knife", 509: "Falchion Knife",
    512: "Bowie Knife", 514: "Butterfly Knife", 515: "Shadow Daggers",
    516: "Paracord Knife", 517: "Survival Knife", 518: "Ursus Knife",
    519: "Navaja Knife", 520: "Nomad Knife", 521: "Stiletto Knife",
    522: "Talon Knife", 523: "Classic Knife", 525: "Skeleton Knife", 526: "Kukri Knife",
}


def get_wear_name(float_min: Optional[float], float_max: Optional[float]) -> str:
    """Get wear name from float range"""
    if float_min is None and float_max is None:
        return ""

    # Use center of range
    if float_min is not None and float_max is not None:
        center = (float_min + float_max) / 2
    elif float_min is not None:
        center = float_min
    else:
        center = float_max

    if center < 0.07:
        return "Factory New"
    elif center < 0.15:
        return "Minimal Wear"
    elif center < 0.38:
        return "Field-Tested"
    elif center < 0.45:
        return "Well-Worn"
    else:
        return "Battle-Scarred"


async def _get_session() -> aiohttp.ClientSession:
    """Get or create HTTP session"""
    global _session
    async with _session_lock:
        if _session is None or _session.closed:
            import ssl
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE

            connector = aiohttp.TCPConnector(
                limit=10,
                force_close=True,
                ssl=ssl_context
            )
            _session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=15),
                connector=connector
            )
            logger.info("Created new aiohttp session for skin lookup")
        return _session


async def fetch_from_csfloat(def_index: int, paint_index: int) -> Tuple[Optional[str], Optional[str]]:
    """
    Fetch skin name and icon from CSFloat API
    Returns: (base_name without wear, icon_url) or (None, None)
    """
    url = (
        f"https://csfloat.com/api/v1/listings"
        f"?def_index={def_index}"
        f"&paint_index={paint_index}"
        f"&limit=1"
    )

    try:
        session = await _get_session()
        logger.info(f"Fetching from CSFloat: {url}")

        async with session.get(url) as response:
            logger.info(f"CSFloat response status: {response.status}")

            if response.status == 200:
                data = await response.json()
                logger.info(f"CSFloat response keys: {list(data.keys())}")

                listings = data.get("data") or []
                logger.info(f"Found {len(listings)} listings")

                if listings:
                    listing = listings[0]
                    item = listing.get("item", {})
                    logger.info(f"Item keys: {list(item.keys())}")

                    # Get name - try multiple fields
                    name = item.get("item_name") or item.get("name")
                    if not name:
                        mhn = item.get("market_hash_name", "")
                        logger.info(f"market_hash_name: {mhn}")
                        if " (" in mhn:
                            name = mhn.rsplit(" (", 1)[0]
                        else:
                            name = mhn

                    # Get icon
                    icon = item.get("icon_url")

                    logger.info(f"Extracted: name={name}, icon={'yes' if icon else 'no'}")

                    if name:
                        return name, icon
                else:
                    logger.warning(f"No listings found for def={def_index}, paint={paint_index}")

            elif response.status == 429:
                logger.warning("CSFloat rate limit hit!")
            else:
                text = await response.text()
                logger.error(f"CSFloat error {response.status}: {text[:200]}")

    except asyncio.TimeoutError:
        logger.error(f"Timeout fetching def={def_index}, paint={paint_index}")
    except Exception as e:
        logger.error(f"API error for def={def_index}, paint={paint_index}: {type(e).__name__}: {e}")

    return None, None


async def get_skin_info(
    def_index: int,
    paint_index: int,
    float_min: Optional[float] = None,
    float_max: Optional[float] = None
) -> Tuple[str, Optional[str]]:
    """
    Get skin name and icon URL.
    Uses cache first, then CSFloat API.
    Returns: (full_name with wear, icon_url)
    """
    # Cache key: "def_paint" (without float, so same skin different floats share cache)
    cache_key = f"{def_index}_{paint_index}"

    # Check cache for base name + icon
    cached = _skin_cache.get(cache_key)
    if cached:
        base_name = cached.get("name")
        icon = cached.get("icon")
        if base_name:
            wear = get_wear_name(float_min, float_max)
            full_name = f"{base_name} ({wear})" if wear else base_name
            return full_name, icon

    # Fetch from API
    base_name, icon = await fetch_from_csfloat(def_index, paint_index)

    if base_name:
        # Save to cache
        _skin_cache[cache_key] = {"name": base_name, "icon": icon}
        _save_cache()
        logger.info(f"Cached: {base_name}")

        wear = get_wear_name(float_min, float_max)
        full_name = f"{base_name} ({wear})" if wear else base_name
        return full_name, icon

    # Fallback: construct name from weapon + paint index
    weapon = WEAPON_NAMES.get(def_index, f"Weapon #{def_index}")
    wear = get_wear_name(float_min, float_max)
    fallback_name = f"{weapon} | Skin #{paint_index}"
    if wear:
        fallback_name = f"{fallback_name} ({wear})"

    return fallback_name, None
