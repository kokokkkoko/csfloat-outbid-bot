"""
Skin name lookup utility for CS2/CSGO items
Uses CSFloat's public data or cached mappings
"""
import aiohttp
from typing import Optional, Tuple
from loguru import logger

# Cache for skin data
_skin_cache = {}
_items_loaded = False


# Common weapon DefIndex mappings
WEAPON_NAMES = {
    1: "Desert Eagle",
    2: "Dual Berettas",
    3: "Five-SeveN",
    4: "Glock-18",
    7: "AK-47",
    8: "AUG",
    9: "AWP",
    10: "FAMAS",
    11: "G3SG1",
    13: "Galil AR",
    14: "M249",
    16: "M4A4",
    17: "MAC-10",
    19: "P90",
    23: "MP5-SD",
    24: "UMP-45",
    25: "XM1014",
    26: "PP-Bizon",
    27: "MAG-7",
    28: "Negev",
    29: "Sawed-Off",
    30: "Tec-9",
    31: "Zeus x27",
    32: "P2000",
    33: "MP7",
    34: "MP9",
    35: "Nova",
    36: "P250",
    38: "SCAR-20",
    39: "SG 553",
    40: "SSG 08",
    60: "M4A1-S",
    61: "USP-S",
    63: "CZ75-Auto",
    64: "R8 Revolver",
    500: "Bayonet",
    503: "Flip Knife",
    505: "Gut Knife",
    506: "Karambit",
    507: "M9 Bayonet",
    508: "Huntsman Knife",
    509: "Falchion Knife",
    512: "Bowie Knife",
    514: "Butterfly Knife",
    515: "Shadow Daggers",
    516: "Paracord Knife",
    517: "Survival Knife",
    518: "Ursus Knife",
    519: "Navaja Knife",
    520: "Nomad Knife",
    521: "Stiletto Knife",
    522: "Talon Knife",
    523: "Classic Knife",
    525: "Skeleton Knife",
    526: "Kukri Knife",
}

# Popular Paint Index to Skin Name mapping
# Key: (def_index, paint_index) -> skin_name (without weapon prefix)
PAINT_NAMES = {
    # Glock-18 (def_index=4)
    (4, 3): "Fade",
    (4, 38): "Dragon Tattoo",
    (4, 48): "Candy Apple",
    (4, 60): "Water Elemental",
    (4, 680): "Bullet Queen",
    (4, 1208): "Shinobu",
    (4, 1215): "Gold Toof",
    (4, 1162): "Winterized",
    (4, 367): "Twilight Galaxy",

    # FAMAS (def_index=10)
    (10, 178): "Pulse",
    (10, 248): "Styx",
    (10, 294): "Djinn",
    (10, 644): "Mecha Industries",
    (10, 838): "Eye of Athena",
    (10, 1202): "Darkwing",
    (10, 1143): "Rapid Eye Movement",

    # AK-47 (def_index=7)
    (7, 44): "Case Hardened",
    (7, 180): "Fire Serpent",
    (7, 282): "Redline",
    (7, 302): "Wasteland Rebel",
    (7, 380): "Aquamarine Revenge",
    (7, 456): "Fuel Injector",
    (7, 524): "Bloodsport",
    (7, 639): "Neon Rider",
    (7, 675): "The Empress",
    (7, 801): "Asiimov",
    (7, 1019): "Nightwish",

    # AWP (def_index=9)
    (9, 84): "Graphite",
    (9, 174): "Electric Hive",
    (9, 227): "Redline",
    (9, 279): "Asiimov",
    (9, 344): "Man-o'-war",
    (9, 395): "Hyper Beast",
    (9, 662): "Neo-Noir",
    (9, 756): "Wildfire",
    (9, 1095): "Chromatic Aberration",
    (9, 446): "Dragon Lore",

    # M4A4 (def_index=16)
    (16, 255): "Asiimov",
    (16, 309): "Howl",
    (16, 336): "Dragon King",
    (16, 400): "Royal Paladin",
    (16, 471): "Desolate Space",
    (16, 512): "Buzz Kill",
    (16, 632): "Neo-Noir",
    (16, 844): "The Emperor",

    # M4A1-S (def_index=60)
    (60, 254): "Cyrex",
    (60, 301): "Hyper Beast",
    (60, 326): "Icarus Fell",
    (60, 360): "Golden Coil",
    (60, 445): "Mecha Industries",
    (60, 587): "Decimator",
    (60, 631): "Nightmare",
    (60, 1001): "Welcome to the Jungle",

    # USP-S (def_index=61)
    (61, 60): "Dark Water",
    (61, 217): "Caiman",
    (61, 227): "Orion",
    (61, 313): "Kill Confirmed",
    (61, 504): "Neo-Noir",
    (61, 653): "Cortex",
    (61, 1122): "Ticket to Hell",

    # Desert Eagle (def_index=1)
    (1, 27): "Blaze",
    (1, 37): "Golden Koi",
    (1, 277): "Conspiracy",
    (1, 711): "Mecha Industries",
    (1, 831): "Printstream",
}


# Float ranges to wear names
def get_wear_name(float_min: Optional[float], float_max: Optional[float]) -> str:
    """Determine wear name from float range"""
    if float_min is None and float_max is None:
        return ""

    # Use the center of the range to determine wear
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


async def fetch_skin_name_from_csfloat(
    def_index: int,
    paint_index: int,
    float_min: Optional[float] = None,
    float_max: Optional[float] = None
) -> Tuple[Optional[str], Optional[str]]:
    """
    Fetch skin name and icon from CSFloat public listings API
    Returns: (market_hash_name, icon_url) or (None, None) if failed
    """
    try:
        # Build the API URL
        url = f"https://csfloat.com/api/v1/listings?def_index={def_index}&paint_index={paint_index}&limit=1"
        if float_min is not None:
            url += f"&min_float={float_min}"
        if float_max is not None:
            url += f"&max_float={float_max}"

        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url, ssl=False) as response:
                if response.status == 200:
                    data = await response.json()
                    if data and "data" in data and len(data["data"]) > 0:
                        item = data["data"][0].get("item", {})
                        name = item.get("market_hash_name")
                        icon = item.get("icon_url")
                        if name:
                            logger.info(f"Fetched skin name from CSFloat: {name}")
                            return name, icon
    except Exception as e:
        logger.debug(f"Failed to fetch skin name from CSFloat: {e}")

    return None, None


def build_fallback_name(
    def_index: Optional[int],
    paint_index: Optional[int],
    float_min: Optional[float] = None,
    float_max: Optional[float] = None
) -> str:
    """
    Build a readable fallback name from DefIndex/PaintIndex
    """
    weapon = WEAPON_NAMES.get(def_index, f"Weapon #{def_index}")
    wear = get_wear_name(float_min, float_max)

    # Try to get skin name from our database
    skin_name = PAINT_NAMES.get((def_index, paint_index))

    if skin_name:
        # Found in our database
        if wear:
            return f"{weapon} | {skin_name} ({wear})"
        else:
            return f"{weapon} | {skin_name}"
    else:
        # Unknown skin - use paint index
        if wear:
            return f"{weapon} | Skin #{paint_index} ({wear})"
        else:
            return f"{weapon} | Skin #{paint_index}"


async def get_skin_info(
    def_index: int,
    paint_index: int,
    float_min: Optional[float] = None,
    float_max: Optional[float] = None
) -> Tuple[str, Optional[str]]:
    """
    Get skin name and icon URL
    Tries CSFloat API first, falls back to constructed name
    Returns: (market_hash_name, icon_url)
    """
    # Check cache first
    cache_key = (def_index, paint_index, float_min, float_max)
    if cache_key in _skin_cache:
        return _skin_cache[cache_key]

    # Try fetching from CSFloat
    name, icon = await fetch_skin_name_from_csfloat(def_index, paint_index, float_min, float_max)

    if not name:
        # Use fallback name
        name = build_fallback_name(def_index, paint_index, float_min, float_max)
        icon = None

    # Cache the result
    _skin_cache[cache_key] = (name, icon)

    return name, icon
