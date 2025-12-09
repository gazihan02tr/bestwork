import base64
from collections import deque
from datetime import datetime
from functools import wraps
import hashlib
import hmac
import os
import random
import string
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote
from uuid import uuid4
from werkzeug.utils import secure_filename

from bson import ObjectId
from flask import (
    Flask,
    abort,
    current_app,
    flash,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from pymongo import MongoClient
from cryptography.fernet import Fernet, InvalidToken


_identity_cipher: Optional[Fernet] = None
_SYS_RANDOM = random.SystemRandom()
_PASSWORD_HASH_CHARS = string.ascii_letters + string.digits
_PASSWORD_HASH_METHOD = "pbkdf2"
_PASSWORD_HASH_NAME = "sha256"
_PASSWORD_DEFAULT_ITERATIONS = 260000
_PASSWORD_SALT_LENGTH = 16

SUPPORTED_LOCALES = ["tr", "en", "de", "ru", "bg"]
DEFAULT_LOCALE = "tr"
LANGUAGE_LABELS = {
    "tr": "Türkçe",
    "en": "English",
    "de": "Deutsch",
    "ru": "Русский",
    "bg": "Български",
}

ALLOWED_AVATAR_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}
DEMO_LOGIN_IDENTIFIER = "000954"
DEMO_LOGIN_PASSWORD = "12345"
_TRANSLATIONS: Dict[str, Dict[str, str]] = {
    "tr": {
        "promo_text": "🎉 Yeni müşterilere özel ilk siparişte %20 indirim!",
        "help": "Yardım",
        "contact": "İletişim",
        "search_placeholder": "Ürün, kategori veya marka ara...",
        "menu_home": "ANASAYFA",
        "menu_personal": "KİŞİSEL",
        "menu_bonus": "PRİM YÖNETİMİ",
        "menu_contact": "İLETİŞİM",
        "orders": "Siparişlerim",
        "cart": "Sepetim",
        "logout": "Çıkış Yap",
        "login": "Giriş Yap",
        "register": "Üye Ol",
        "alert_success": "Başarılı",
        "alert_error": "Hata",
        "alert_warning": "Uyarı",
        "alert_info": "Bilgi",
        "alert_default": "Bilgi",
    },
    "en": {
        "promo_text": "🎉 Enjoy 20% off your first order for new customers!",
        "help": "Help",
        "contact": "Contact",
        "search_placeholder": "Search for products, categories, or brands...",
        "menu_home": "HOME",
        "menu_personal": "PROFILE",
        "menu_bonus": "BONUS MANAGEMENT",
        "menu_contact": "CONTACT",
        "orders": "My Orders",
        "cart": "My Cart",
        "logout": "Log Out",
        "login": "Sign In",
        "register": "Register",
        "alert_success": "Success",
        "alert_error": "Error",
        "alert_warning": "Warning",
        "alert_info": "Info",
        "alert_default": "Info",
    },
    "de": {
        "promo_text": "🎉 20% Rabatt auf Ihre erste Bestellung für Neukunden!",
        "help": "Hilfe",
        "contact": "Kontakt",
        "search_placeholder": "Produkte, Kategorien oder Marken suchen...",
        "menu_home": "STARTSEITE",
        "menu_personal": "PROFIL",
        "menu_bonus": "BONUSVERWALTUNG",
        "menu_contact": "KONTAKT",
        "orders": "Meine Bestellungen",
        "cart": "Mein Warenkorb",
        "logout": "Abmelden",
        "login": "Anmelden",
        "register": "Registrieren",
        "alert_success": "Erfolg",
        "alert_error": "Fehler",
        "alert_warning": "Warnung",
        "alert_info": "Info",
        "alert_default": "Info",
    },
    "ru": {
        "promo_text": "🎉 Скидка 20% на первый заказ для новых клиентов!",
        "help": "Помощь",
        "contact": "Контакты",
        "search_placeholder": "Поиск товаров, категорий или брендов...",
        "menu_home": "ГЛАВНАЯ",
        "menu_personal": "ПРОФИЛЬ",
        "menu_bonus": "УПРАВЛЕНИЕ БОНУСАМИ",
        "menu_contact": "КОНТАКТЫ",
        "orders": "Мои заказы",
        "cart": "Моя корзина",
        "logout": "Выйти",
        "login": "Войти",
        "register": "Создать аккаунт",
        "alert_success": "Успех",
        "alert_error": "Ошибка",
        "alert_warning": "Внимание",
        "alert_info": "Инфо",
        "alert_default": "Инфо",
    },
    "bg": {
        "promo_text": "🎉 20% отстъпка за първа поръчка за нови клиенти!",
        "help": "Помощ",
        "contact": "Контакт",
        "search_placeholder": "Търсене на продукти, категории или марки...",
        "menu_home": "НАЧАЛО",
        "menu_personal": "ПРОФИЛ",
        "menu_bonus": "УПРАВЛЕНИЕ НА БОНУСИ",
        "menu_contact": "КОНТАКТ",
        "orders": "Моите поръчки",
        "cart": "Моята кошница",
        "logout": "Изход",
        "login": "Вход",
        "register": "Регистрация",
        "alert_success": "Успех",
        "alert_error": "Грешка",
        "alert_warning": "Предупреждение",
        "alert_info": "Инфо",
        "alert_default": "Инфо",
    },
}


def build_initials_avatar(initials: str, size: int = 256) -> str:
    """
    Create a data URL with SVG showing the initials on a gradient circle.
    """
    initials_text = (initials or "?")[:2]
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}">'
        f'<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">'
        f'<stop offset="0%" stop-color="#7C3AED"/><stop offset="100%" stop-color="#A855F7"/>'
        f'</linearGradient></defs>'
        f'<rect width="{size}" height="{size}" rx="{size//2}" fill="url(#g)"/>'
        f'<text x="50%" y="55%" dominant-baseline="middle" text-anchor="middle" '
        f'font-family="Roboto,Helvetica,Arial,sans-serif" font-size="{int(size*0.38)}" font-weight="700" fill="#fff">'
        f'{initials_text}'
        f'</text></svg>'
    )
    return f"data:image/svg+xml;utf8,{quote(svg)}"


def generate_initials(name: str, max_letters: int = 2) -> str:
    """
    Return up to `max_letters` initials from the supplied name.
    """
    if not name:
        return ""
    initials: List[str] = []
    for part in name.strip().split():
        if not part:
            continue
        initials.append(part[0].upper())
        if len(initials) >= max_letters:
            break
    return "".join(initials)


def collect_varis_members(user: Dict[str, Any]) -> List[Dict[str, str]]:
    profile = user.get("profile", {})
    varis_members: List[Dict[str, str]] = []

    varis_cursor = app.db.users.find(
        {
            "placement_parent_id": user["_id"],
            "placement_status": "placed",
        },
        {
            "profile.first_name": 1,
            "profile.last_name": 1,
            "phone": 1,
            "email": 1,
            "identity_number_encrypted": 1,
            "profile.address": 1,
            "profile.relation": 1,
        },
    )

    for doc in varis_cursor:
        profile_info = doc.get("profile", {})
        name_parts = [
            profile_info.get("first_name", "").strip(),
            profile_info.get("last_name", "").strip(),
        ]
        full_name = " ".join(part for part in name_parts if part).strip() or doc.get("email", "Üye")
        encrypted_tc = doc.get("identity_number_encrypted") or "Belirtilmedi"
        varis_members.append(
            {
                "entry_id": str(doc["_id"]),
                "source": "placement",
                "name": full_name,
                "tc": encrypted_tc,
                "phone": doc.get("phone") or "Belirtilmedi",
                "email": doc.get("email") or "Belirtilmedi",
                "relation": profile_info.get("relation") or "Belirtilmedi",
                "address": profile_info.get("address") or "Belirtilmedi",
                "can_manage": False,
            }
        )

    manual_varis = profile.get("varis_entries", [])
    for idx, manual in enumerate(manual_varis):
        entry_id = manual.get("entry_id") or f"manual-{uuid4().hex}"
        if not manual.get("entry_id"):
            app.db.users.update_one(
                {"_id": user["_id"]},
                {"$set": {f"profile.varis_entries.{idx}.entry_id": entry_id}},
            )
        varis_members.append(
            {
                "entry_id": entry_id,
                "source": "manual",
                "name": manual.get("name") or "Tanımlı değil",
                "tc": manual.get("tc") or "Belirtilmedi",
                "phone": manual.get("phone") or "Belirtilmedi",
                "email": manual.get("email") or "Belirtilmedi",
                "relation": manual.get("relation") or "Belirtilmedi",
                "address": manual.get("address") or "Belirtilmedi",
                "can_manage": True,
            }
        )

    return varis_members


def allowed_avatar_file(filename: str) -> bool:
    """
    Check whether a filename has an approved image extension.
    """
    if not filename:
        return False
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_AVATAR_EXTENSIONS

def _generate_password_salt(length: int = _PASSWORD_SALT_LENGTH) -> str:
    return "".join(_SYS_RANDOM.choice(_PASSWORD_HASH_CHARS) for _ in range(length))


def _pbkdf2_encode(password: str, salt: str, iterations: int, hash_name: str) -> str:
    digest = hashlib.pbkdf2_hmac(
        hash_name,
        password.encode("utf-8"),
        salt.encode("utf-8"),
        iterations,
    )
    return base64.b64encode(digest).decode("utf-8")


def generate_password_hash(password: str, salt_length: int = _PASSWORD_SALT_LENGTH) -> str:
    """
    Generate a PBKDF2 based password hash compatible with Werkzeug's default output.
    """
    if not isinstance(password, str):
        raise TypeError("password must be a string")
    salt = _generate_password_salt(salt_length)
    iterations = _PASSWORD_DEFAULT_ITERATIONS
    hash_name = _PASSWORD_HASH_NAME
    method = f"{_PASSWORD_HASH_METHOD}:{hash_name}:{iterations}"
    hash_value = _pbkdf2_encode(password, salt, iterations, hash_name)
    return f"{method}${salt}${hash_value}"


def _parse_method_descriptor(descriptor: str) -> Optional[Tuple[str, int]]:
    """Return (hash_name, iterations) for pbkdf2 descriptors."""
    parts = descriptor.split(":")
    if not parts or parts[0] != _PASSWORD_HASH_METHOD:
        return None
    hash_name = parts[1] if len(parts) > 1 else _PASSWORD_HASH_NAME
    try:
        iterations = (
            int(parts[2]) if len(parts) > 2 else _PASSWORD_DEFAULT_ITERATIONS
        )
    except ValueError:
        return None
    return hash_name, iterations


def check_password_hash(pwhash: str, password: str) -> bool:
    """
    Validate a password against an encoded PBKDF2 hash.
    Supports hashes generated by Werkzeug defaults and this module.
    """
    if not pwhash or "$" not in pwhash:
        return False
    try:
        descriptor, salt, stored_hash = pwhash.split("$", 2)
    except ValueError:
        return False

    parsed = _parse_method_descriptor(descriptor)
    if not parsed:
        return False
    hash_name, iterations = parsed
    calculated = _pbkdf2_encode(password, salt, iterations, hash_name)
    return hmac.compare_digest(stored_hash, calculated)


def create_app() -> Flask:
    """Flask uygulamasını oluştur ve yapılandır."""
    app = Flask(__name__)
    app.secret_key = (
        app_config("SECRET_KEY") or "local-dev-secret-change-me"
    )  # Production'da ortam değişkeni kullanılmalı

    app.mongo_client = create_mongo_client()
    app.db = resolve_database(app.mongo_client)

    register_db_helpers(app)
    register_routes(app)

    @app.before_request
    def _load_locale():
        locale = session.get("lang") or request.accept_languages.best_match(SUPPORTED_LOCALES)
        g.locale = locale if locale in SUPPORTED_LOCALES else DEFAULT_LOCALE

    def translate(key: str) -> str:
        locale = getattr(g, "locale", DEFAULT_LOCALE)
        return _TRANSLATIONS.get(locale, _TRANSLATIONS[DEFAULT_LOCALE]).get(key, key)

    app.jinja_env.globals["t"] = translate
    app.jinja_env.globals["supported_languages"] = LANGUAGE_LABELS

    @app.route("/set-language/<lang>")
    def set_language(lang: str):
        if lang not in LANGUAGE_LABELS:
            lang = DEFAULT_LOCALE
        session["lang"] = lang
        next_url = request.headers.get("Referer") or url_for("index")
        return redirect(next_url)

    return app


def app_config(name: str) -> Optional[str]:
    """Ortam değişkeni okuma helper'ı (zsh uyumluluğu için ayrı tutuldu)."""
    return os.environ.get(name)


def create_mongo_client() -> MongoClient:
    """MongoDB istemcisini hazırla."""
    uri = app_config("MONGO_URI") or "mongodb://localhost:27017/bestwork"
    return MongoClient(uri)


def resolve_database(client: MongoClient):
    """
    URI içinde DB adı belirtilmişse onu kullan,
    belirtilmemişse varsayılan 'bestwork' veritabanını döndür.
    """
    default_db_name = "bestwork"
    try:
        # PyMongo 4.x URI içinden db adını otomatik seçer, get_default_database bunu döndürür.
        database = client.get_default_database()
    except Exception:
        database = None

    if database is not None:
        return database
    return client[default_db_name]


def register_db_helpers(app: Flask) -> None:
    """Veri tabanına erişim ve oturum yardımcılarını hazırla."""

    @app.before_request
    def load_logged_in_user() -> None:
        user_id = session.get("user_id")
        g.user = None

        if user_id:
            try:
                g.user = app.db.users.find_one({"_id": ObjectId(user_id)})
            except Exception:
                session.pop("user_id", None)
                g.user = None

    @app.context_processor
    def inject_globals():
        cart: List[Dict] = session.get("cart", [])
        cart_count = sum(item.get("quantity", 0) for item in cart)
        current_user = getattr(g, "user", None)
        return {"current_user": current_user, "cart_count": cart_count}


def login_required(view):
    """Kullanıcı girişi zorunlu rotalar için dekoratör."""

    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if g.get("user") is None:
            flash("Devam etmek için lütfen giriş yapın.", "warning")
            next_url = request.path
            return redirect(url_for("login", next=next_url))
        return view(*args, **kwargs)

    return wrapped_view


def register_routes(app: Flask) -> None:
    """Tüm Flask rotalarını kaydet."""

    COUNTRY_OPTIONS: List[Dict[str, str]] = [
        {"dial_code": "90", "name": "Türkiye"},
    ]

    PROVINCES: Dict[str, List[str]] = {
        "Adana": ["Aladağ", "Ceyhan", "Çukurova", "Feke", "İmamoğlu", "Karaisalı", "Karataş", "Kozan", "Pozantı", "Saimbeyli", "Sarıçam", "Seyhan", "Tufanbeyli", "Yumurtalık", "Yüreğir"],
        "Adıyaman": ["Besni", "Çelikhan", "Gerger", "Gölbaşı", "Kahta", "Merkez", "Samsat", "Sincik", "Tut"],
        "Afyonkarahisar": ["Başmakçı", "Bayat", "Bolvadin", "Çay", "Çobanlar", "Dazkırı", "Dinar", "Emirdağ", "Evciler", "Hocalar", "İhsaniye", "İscehisar", "Kızılören", "Merkez", "Sandıklı", "Sinanpaşa", "Sultandağı", "Şuhut"],
        "Ağrı": ["Diyadin", "Doğubayazıt", "Eleşkirt", "Hamur", "Merkez", "Patnos", "Taşlıçay", "Tutak"],
        "Aksaray": ["Ağaçören", "Aksaray", "Eskil", "Gülağaç", "Güzelyurt", "Ortaköy", "Sarıyahşi"],
        "Amasya": ["Göynücek", "Gümüşhacıköy", "Hamamözü", "Merkez", "Merzifon", "Suluova", "Taşova"],
        "Ankara": ["Akyurt", "Altındağ", "Ayaş", "Balâ", "Beypazarı", "Çamlıdere", "Çankaya", "Çubuk", "Elmadağ", "Etimesgut", "Evren", "Gölbaşı", "Güdül", "Haymana", "Kahramankazan", "Kalecik", "Keçiören", "Kızılcahamam", "Mamak", "Nallıhan", "Polatlı", "Pursaklar", "Sincan", "Şereflikoçhisar", "Yenimahalle"],
        "Antalya": ["Akseki", "Aksu", "Alanya", "Demre", "Döşemealtı", "Elmalı", "Finike", "Gazipaşa", "Gündoğmuş", "İbradı", "Kaş", "Kemer", "Kepez", "Konyaaltı", "Korkuteli", "Kumluca", "Manavgat", "Muratpaşa", "Serik"],
        "Artvin": ["Ardanuç", "Arhavi", "Borçka", "Hopa", "Kemalpaşa", "Merkez", "Murgul", "Şavşat", "Yusufeli"],
        "Ardahan": ["Çıldır", "Damal", "Göle", "Hanak", "Merkez", "Posof"],
        "Aydın": ["Bozdoğan", "Buharkent", "Çine", "Didim", "Efeler", "Germencik", "İncirliova", "Karacasu", "Karpuzlu", "Koçarlı", "Köşk", "Kuşadası", "Kuyucak", "Nazilli", "Söke", "Sultanhisar", "Yenipazar"],
        "Balıkesir": ["Altıeylül", "Ayvalık", "Balya", "Bandırma", "Bigadiç", "Burhaniye", "Dursunbey", "Edremit", "Erdek", "Gömeç", "Gönen", "Havran", "İvrindi", "Karesi", "Kepsut", "Manyas", "Marmara", "Savaştepe", "Sındırgı", "Susurluk"],
        "Bartın": ["Amasra", "Kurucaşile", "Merkez", "Ulus"],
        "Batman": ["Beşiri", "Gercüş", "Hasankeyf", "Kozluk", "Merkez", "Sason"],
        "Bayburt": ["Aydıntepe", "Demirözü", "Merkez"],
        "Bilecik": ["Bozüyük", "Gölpazarı", "İnhisar", "Merkez", "Osmaneli", "Pazaryeri", "Söğüt", "Yenipazar"],
        "Bingöl": ["Adaklı", "Genç", "Karlıova", "Kığı", "Merkez", "Solhan", "Yayladere", "Yedisu"],
        "Bitlis": ["Adilcevaz", "Ahlat", "Güroymak", "Hizan", "Merkez", "Mutki", "Tatvan"],
        "Bolu": ["Dörtdivan", "Gerede", "Göynük", "Kıbrıscık", "Mengen", "Merkez", "Mudurnu", "Seben", "Yeniçağa"],
        "Burdur": ["Ağlasun", "Altınyayla", "Bucak", "Çavdır", "Çeltikçi", "Gölhisar", "Karamanlı", "Kemer", "Merkez", "Tefenni", "Yeşilova"],
        "Bursa": ["Büyükorhan", "Gemlik", "Gürsu", "Harmancık", "İnegöl", "İznik", "Karacabey", "Keles", "Kestel", "Mudanya", "Mustafakemalpaşa", "Nilüfer", "Orhaneli", "Orhangazi", "Osmangazi", "Yenişehir", "Yıldırım"],
        "Çanakkale": ["Ayvacık", "Bayramiç", "Biga", "Bozcaada", "Çan", "Eceabat", "Ezine", "Gelibolu", "Gökçeada", "Lapseki", "Merkez", "Yenice"],
        "Çankırı": ["Atkaracalar", "Bayramören", "Çerkeş", "Eldivan", "Ilgaz", "Kızılırmak", "Korgun", "Kurşunlu", "Merkez", "Orta", "Şabanözü", "Yapraklı"],
        "Çorum": ["Alaca", "Bayat", "Boğazkale", "Dodurga", "İskilip", "Kargı", "Laçin", "Mecitözü", "Merkez", "Oğuzlar", "Osmancık", "Sungurlu", "Uğurludağ"],
        "Denizli": ["Acıpayam", "Babadağ", "Baklan", "Bekilli", "Beyağaç", "Bozkurt", "Buldan", "Çal", "Çameli", "Çardak", "Çivril", "Güney", "Honaz", "Kale", "Merkezefendi", "Pamukkale", "Sarayköy", "Serinhisar", "Tavas"],
        "Diyarbakır": ["Bağlar", "Bismil", "Çermik", "Çınar", "Çüngüş", "Dicle", "Eğil", "Ergani", "Hani", "Hazro", "Kayapınar", "Kocaköy", "Kulp", "Lice", "Silvan", "Sur", "Yenişehir"],
        "Düzce": ["Akçakoca", "Cumayeri", "Çilimli", "Gölyaka", "Gümüşova", "Kaynaşlı", "Merkez", "Yığılca"],
        "Edirne": ["Enez", "Havsa", "İpsala", "Keşan", "Lalapaşa", "Meriç", "Merkez", "Süloğlu", "Uzunköprü"],
        "Elazığ": ["Ağın", "Alacakaya", "Arıcak", "Baskil", "Karakoçan", "Keban", "Kovancılar", "Maden", "Merkez", "Palu", "Sivrice"],
        "Erzincan": ["Çayırlı", "İliç", "Kemah", "Kemaliye", "Merkez", "Otlukbeli", "Refahiye", "Tercan", "Üzümlü"],
        "Erzurum": ["Aşkale", "Aziziye", "Çat", "Hınıs", "Horasan", "İspir", "Karaçoban", "Karayazı", "Köprüköy", "Narman", "Oltu", "Olur", "Palandöken", "Pasinler", "Pazaryolu", "Şenkaya", "Tekman", "Tortum", "Uzundere", "Yakutiye"],
        "Eskişehir": ["Alpu", "Beylikova", "Çifteler", "Günyüzü", "Han", "İnönü", "Mahmudiye", "Mihalgazi", "Mihalıççık", "Odunpazarı", "Sarıcakaya", "Seyitgazi", "Sivrihisar", "Tepebaşı"],
        "Gaziantep": ["Araban", "İslahiye", "Karkamış", "Nizip", "Nurdağı", "Oğuzeli", "Şahinbey", "Şehitkamil", "Yavuzeli"],
        "Giresun": ["Alucra", "Bulancak", "Çamoluk", "Çanakçı", "Dereli", "Doğankent", "Espiye", "Eynesil", "Görele", "Güce", "Keşap", "Merkez", "Piraziz", "Şebinkarahisar", "Tirebolu", "Yağlıdere"],
        "Gümüşhane": ["Kelkit", "Köse", "Kürtün", "Merkez", "Şiran", "Torul"],
        "Hakkari": ["Çukurca", "Derecik", "Merkez", "Şemdinli", "Yüksekova"],
        "Hatay": ["Altınözü", "Antakya", "Arsuz", "Belen", "Defne", "Dörtyol", "Erzin", "Hassa", "İskenderun", "Kırıkhan", "Kumlu", "Payas", "Reyhanlı", "Samandağ", "Yayladağı"],
        "Iğdır": ["Aralık", "Karakoyunlu", "Merkez", "Tuzluca"],
        "Isparta": ["Aksu", "Atabey", "Eğirdir", "Gelendost", "Gönen", "Keçiborlu", "Merkez", "Senirkent", "Sütçüler", "Şarkikaraağaç", "Uluborlu", "Yalvaç", "Yenişarbademli"],
        "İstanbul": ["Adalar", "Arnavutköy", "Ataşehir", "Avcılar", "Bağcılar", "Bahçelievler", "Bakırköy", "Başakşehir", "Bayrampaşa", "Beşiktaş", "Beykoz", "Beylikdüzü", "Beyoğlu", "Büyükçekmece", "Çatalca", "Çekmeköy", "Esenler", "Esenyurt", "Eyüpsultan", "Fatih", "Gaziosmanpaşa", "Güngören", "Kadıköy", "Kağıthane", "Kartal", "Küçükçekmece", "Maltepe", "Pendik", "Sancaktepe", "Sarıyer", "Silivri", "Sultanbeyli", "Sultangazi", "Şile", "Şişli", "Tuzla", "Ümraniye", "Üsküdar", "Zeytinburnu"],
        "İzmir": ["Aliağa", "Balçova", "Bayındır", "Bayraklı", "Bergama", "Beydağ", "Bornova", "Buca", "Çeşme", "Çiğli", "Dikili", "Foça", "Gaziemir", "Güzelbahçe", "Karabağlar", "Karaburun", "Karşıyaka", "Kemalpaşa", "Kınık", "Kiraz", "Konak", "Menderes", "Menemen", "Narlıdere", "Ödemiş", "Seferihisar", "Selçuk", "Tire", "Torbalı", "Urla"],
        "Kahramanmaraş": ["Afşin", "Andırın", "Çağlayancerit", "Dulkadiroğlu", "Ekinözü", "Elbistan", "Göksun", "Nurhak", "Onikişubat", "Pazarcık", "Türkoğlu"],
        "Karabük": ["Eflani", "Eskipazar", "Karabük", "Ovacık", "Safranbolu", "Yenice"],
        "Karaman": ["Ayrancı", "Başyayla", "Ermenek", "Karaman", "Kazımkarabekir", "Sarıveliler"],
        "Kars": ["Akyaka", "Arpaçay", "Digor", "Kağızman", "Merkez", "Sarıkamış", "Selim", "Susuz"],
        "Kastamonu": ["Abana", "Ağlı", "Araç", "Azdavay", "Bozkurt", "Cide", "Çatalzeytin", "Daday", "Devrekani", "Doğanyurt", "Hanönü", "İhsangazi", "İnebolu", "Küre", "Merkez", "Pınarbaşı", "Seydiler", "Şenpazar", "Taşköprü", "Tosya"],
        "Kayseri": ["Akkışla", "Bünyan", "Develi", "Felahiye", "Hacılar", "İncesu", "Kocasinan", "Melikgazi", "Özvatan", "Pınarbaşı", "Sarıoğlan", "Sarız", "Talas", "Tomarza", "Yahyalı", "Yeşilhisar"],
        "Kırıkkale": ["Bahşılı", "Balışeyh", "Çelebi", "Delice", "Karakeçili", "Keskin", "Merkez", "Sulakyurt", "Yahşihan"],
        "Kırklareli": ["Babaeski", "Demirköy", "Kofçaz", "Lüleburgaz", "Merkez", "Pehlivanköy", "Pınarhisar", "Vize"],
        "Kırşehir": ["Akçakent", "Akpınar", "Boztepe", "Çiçekdağı", "Kaman", "Merkez", "Mucur"],
        "Kilis": ["Elbeyli", "Merkez", "Musabeyli", "Polateli"],
        "Kocaeli": ["Başiskele", "Çayırova", "Darıca", "Derince", "Dilovası", "Gebze", "Gölcük", "İzmit", "Kandıra", "Karamürsel", "Kartepe", "Körfez"],
        "Konya": ["Ahırlı", "Akören", "Akşehir", "Altınekin", "Beyşehir", "Bozkır", "Cihanbeyli", "Çeltik", "Çumra", "Derbent", "Derebucak", "Doğanhisar", "Emirgazi", "Ereğli", "Güneysınır", "Hadım", "Halkapınar", "Hüyük", "Ilgın", "Kadınhanı", "Karapınar", "Karatay", "Kulu", "Meram", "Sarayönü", "Selçuklu", "Seydişehir", "Taşkent", "Tuzlukçu", "Yalıhüyük", "Yunak"],
        "Kütahya": ["Altıntaş", "Aslanapa", "Çavdarhisar", "Domaniç", "Dumlupınar", "Emet", "Gediz", "Hisarcık", "Merkez", "Pazarlar", "Simav", "Şaphane", "Tavşanlı"],
        "Malatya": ["Akçadağ", "Arapgir", "Arguvan", "Battalgazi", "Darende", "Doğanşehir", "Doğanyol", "Hekimhan", "Kale", "Kuluncak", "Pütürge", "Yazıhan", "Yeşilyurt"],
        "Manisa": ["Ahmetli", "Akhisar", "Alaşehir", "Demirci", "Gölmarmara", "Gördes", "Kırkağaç", "Köprübaşı", "Kula", "Salihli", "Sarıgöl", "Saruhanlı", "Selendi", "Soma", "Şehzadeler", "Turgutlu", "Yunusemre"],
        "Mardin": ["Artuklu", "Dargeçit", "Derik", "Kızıltepe", "Mazıdağı", "Midyat", "Nusaybin", "Ömerli", "Savur", "Yeşilli"],
        "Mersin": ["Akdeniz", "Anamur", "Aydıncık", "Bozyazı", "Çamlıyayla", "Erdemli", "Gülnar", "Mezitli", "Mut", "Silifke", "Tarsus", "Toroslar", "Yenişehir"],
        "Muğla": [
            "Bodrum", "Dalaman", "Datça", "Fethiye", "Kavaklıdere", "Köyceğiz", "Marmaris", "Menteşe", "Milas", "Ortaca", "Seydikemer", "Ula", "Yatağan"
        ],
        "Muş": ["Bulanık", "Hasköy", "Korkut", "Malazgirt", "Merkez", "Varto"],
        "Nevşehir": ["Acıgöl", "Avanos", "Derinkuyu", "Gülşehir", "Hacıbektaş", "Kozaklı", "Merkez", "Ürgüp"],
        "Niğde": ["Altunhisar", "Bor", "Çamardı", "Çiftlik", "Merkez", "Ulukışla"],
        "Ordu": ["Akkuş", "Altınordu", "Aybastı", "Çamaş", "Çatalpınar", "Çaybaşı", "Fatsa", "Gölköy", "Gülyalı", "Gürgentepe", "İkizce", "Kabadüz", "Kabataş", "Korgan", "Kumru", "Mesudiye", "Perşembe", "Ulubey", "Ünye"],
        "Osmaniye": ["Bahçe", "Düziçi", "Kadirli", "Merkez", "Sumbas", "Toprakkale"],
        "Rize": ["Ardeşen", "Çamlıhemşin", "Çayeli", "Derepazarı", "Fındıklı", "Güneysu", "Hemşin", "İkizdere", "İyidere", "Kalkandere", "Merkez", "Pazar"],
        "Sakarya": ["Adapazarı", "Akyazı", "Arifiye", "Erenler", "Ferizli", "Geyve", "Hendek", "Karapürçek", "Karasu", "Kaynarca", "Kocaali", "Pamukova", "Sapanca", "Serdivan", "Söğütlü", "Taraklı"],
        "Samsun": ["Alaçam", "Asarcık", "Atakum", "Ayvacık", "Bafra", "Canik", "Çarşamba", "Havza", "İlkadım", "Kavak", "Ladik", "Ondokuzmayıs", "Salıpazarı", "Tekkeköy", "Terme", "Vezirköprü", "Yakakent"],
        "Siirt": ["Baykan", "Eruh", "Kurtalan", "Merkez", "Pervari", "Şirvan", "Tillo"],
        "Sinop": ["Ayancık", "Boyabat", "Dikmen", "Durağan", "Erfelek", "Gerze", "Merkez", "Saraydüzü", "Türkeli"],
        "Sivas": ["Akıncılar", "Altınyayla", "Divriği", "Doğanşar", "Gemerek", "Gölova", "Gürün", "Hafik", "İmranlı", "Kangal", "Koyulhisar", "Merkez", "Suşehri", "Şarkışla", "Ulaş", "Yıldızeli", "Zara"],
        "Şanlıurfa": ["Akçakale", "Birecik", "Bozova", "Ceylanpınar", "Eyyübiye", "Halfeti", "Haliliye", "Harran", "Hilvan", "Karaköprü", "Siverek", "Suruç", "Viranşehir"],
        "Şırnak": ["Beytüşşebap", "Cizre", "Güçlükonak", "İdil", "Merkez", "Silopi", "Uludere"],
        "Tekirdağ": ["Çerkezköy", "Çorlu", "Ergene", "Hayrabolu", "Kapaklı", "Malkara", "Marmaraereğlisi", "Muratlı", "Saray", "Süleymanpaşa", "Şarköy"],
        "Tokat": ["Almus", "Artova", "Başçiftlik", "Erbaa", "Merkez", "Niksar", "Pazar", "Reşadiye", "Sulusaray", "Turhal", "Yeşilyurt", "Zile"],
        "Trabzon": ["Akçaabat", "Araklı", "Arsin", "Beşikdüzü", "Çarşıbaşı", "Çaykara", "Dernekpazarı", "Düzköy", "Hayrat", "Köprübaşı", "Maçka", "Of", "Ortahisar", "Sürmene", "Şalpazarı", "Tonya", "Vakfıkebir", "Yomra"],
        "Tunceli": ["Çemişgezek", "Hozat", "Mazgirt", "Merkez", "Nazımiye", "Ovacık", "Pertek", "Pülümür"],
        "Uşak": ["Banaz", "Eşme", "Karahallı", "Merkez", "Sivaslı", "Ulubey"] ,
        "Van": ["Bahçesaray", "Başkale", "Çaldıran", "Çatak", "Edremit", "Erciş", "Gevaş", "Gürpınar", "İpekyolu", "Muradiye", "Özalp", "Saray", "Tuşba"],
        "Yalova": ["Altınova", "Armutlu", "Çınarcık", "Çiftlikköy", "Merkez", "Termal"],
        "Yozgat": ["Akdağmadeni", "Aydıncık", "Boğazlıyan", "Çandır", "Çayıralan", "Çekerek", "Kadışehri", "Merkez", "Saraykent", "Sarıkaya", "Şefaatli", "Sorgun", "Yenifakılı", "Yerköy"],
        "Zonguldak": ["Alaplı", "Çaycuma", "Devrek", "Ereğli", "Gökçebey", "Kilimli", "Kozlu", "Merkez"],
    }

    def ensure_sample_products():
        if app.db.products.count_documents({}) == 0:
            app.db.products.insert_many(
                [
                    {
                        "name": "Premium Multivitamin",
                        "slug": "premium-multivitamin",
                        "category": "Beslenme",
                        "price": 649.90,
                        "image_url": "https://images.unsplash.com/photo-1582719478250-c89cae4dc85b?w=600",
                        "description": "Bağışıklık sisteminizi güçlendiren, günlük mineral ve vitamin desteği.",
                        "stock": 120,
                    },
                    {
                        "name": "HydraGlow Serum",
                        "slug": "hydraglow-serum",
                        "category": "Güzellik",
                        "price": 799.90,
                        "image_url": "https://images.unsplash.com/photo-1522336572468-97b06e8ef143?w=600",
                        "description": "Cildi nemlendirirken ince çizgilerin görünümünü azaltan serum.",
                        "stock": 86,
                    },
                    {
                        "name": "EcoClean Konsantre",
                        "slug": "ecoclean-konsantre",
                        "category": "Ev Bakımı",
                        "price": 299.90,
                        "image_url": "https://images.unsplash.com/photo-1581578731548-c64695cc6952?w=600",
                        "description": "Doğal içeriklerle güçlendirilmiş çok amaçlı yüzey temizleyici.",
                        "stock": 200,
                    },
                    {
                        "name": "ZenBalance Çay Karışımı",
                        "slug": "zenbalance-cay",
                        "category": "Beslenme",
                        "price": 159.90,
                        "image_url": "https://images.unsplash.com/photo-1504384308090-c894fdcc538d?w=600",
                        "description": "Günün stresini azaltmaya yardımcı doğal bitki çay karışımı.",
                        "stock": 140,
                    },
                ]
            )

    def format_datetime_for_display(value, fmt="%Y-%m-%d %H:%M"):
        if not value:
            return ""
        if isinstance(value, datetime):
            return value.strftime(fmt)
        try:
            parsed = datetime.fromisoformat(value)
            return parsed.strftime(fmt)
        except (ValueError, TypeError):
            return str(value)

    def parse_datetime(value):
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value)
            except (ValueError, TypeError):
                return None
        return None

    def collect_sponsor_members(user: Dict[str, Any]) -> List[Dict[str, str]]:
        members: List[Dict[str, str]] = []
        sponsor_cursor = app.db.users.find(
            {"sponsor_id": user["_id"]},
            {
                "referral_code": 1,
                "name": 1,
                "email": 1,
                "phone": 1,
                "created_at": 1,
                "placement_assigned_at": 1,
                "profile": 1,
            },
        ).sort("created_at", 1)

        for doc in sponsor_cursor:
            profile_data = doc.get("profile", {}) or {}
            level = (profile_data.get("level") or profile_data.get("membership_type") or "BRONZ").upper()
            members.append(
                {
                    "member_number": doc.get("referral_code", "Tanımlanmadı"),
                    "full_name": doc.get("name") or "Üye",
                    "email": doc.get("email"),
                    "phone": doc.get("phone"),
                    "recorded_at": format_datetime_for_display(doc.get("created_at")),
                    "activated_at": format_datetime_for_display(profile_data.get("activated_at")),
                    "tree_placed_at": format_datetime_for_display(doc.get("placement_assigned_at")),
                    "package": level,
                }
            )
        return members

    def collect_faststart_records(user: Dict[str, Any]) -> List[Dict[str, Any]]:
        profile_data = user.get("profile", {}) or {}
        raw_records = profile_data.get("fast_start_records") or []
        format_date = format_datetime_for_display

        records: List[Dict[str, Any]] = []
        for entry in raw_records:
            records.append(
                {
                    "member_number": entry.get("member_number", "—"),
                    "full_name": entry.get("full_name", "Üye"),
                    "package": entry.get("package", "—"),
                    "bonus": float(entry.get("bonus") or 0),
                    "purchase_date": format_date(entry.get("purchase_date")),
                    "main_package_date": format_date(entry.get("main_package_date")),
                    "earnings": float(entry.get("earnings") or 0),
                }
            )
        return records

    def collect_referral_bonus_records(user: Dict[str, Any]) -> List[Dict[str, Any]]:
        profile_data = user.get("profile", {}) or {}
        raw_records = profile_data.get("referal_bonus_records") or []
        records: List[Dict[str, Any]] = []

        for entry in raw_records:
            raw_date = (
                entry.get("date")
                or entry.get("recorded_at")
                or entry.get("created_at")
                or entry.get("earned_at")
            )
            parsed_date = parse_datetime(raw_date)
            display_date = format_datetime_for_display(parsed_date or raw_date)

            raw_amount = entry.get("amount") or entry.get("bonus") or entry.get("value") or 0
            try:
                amount = float(raw_amount)
            except (TypeError, ValueError):
                amount = 0.0

            records.append(
                {
                    "member_number": entry.get("member_number")
                    or entry.get("referral_code")
                    or "Tanımlanmadı",
                    "full_name": entry.get("full_name") or entry.get("name") or "Üye",
                    "date": display_date,
                    "parsed_date": parsed_date,
                    "amount": amount,
                    "source": entry.get("source") or entry.get("package"),
                }
            )
        return records

    def format_currency(value: float = 0.0, suffix: str = "TL") -> str:
        try:
            amount = float(value)
        except (TypeError, ValueError):
            amount = 0.0
        formatted = f"{amount:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        return f"{formatted} {suffix}"

    def format_points(value: float = 0.0, suffix: str = "PV") -> str:
        try:
            amount = float(value)
        except (TypeError, ValueError):
            amount = 0.0
        formatted = f"{amount:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        return f"{formatted} {suffix}"


    @app.route("/")
    def index():
        ensure_sample_products()
        products = []
        for product in app.db.products.find():
            product_data = dict(product)
            product_data["id"] = str(product["_id"])
            products.append(product_data)

        return render_template("index.html", products=products)

    @app.route("/register", methods=["GET", "POST"])
    def register():
        total_users = app.db.users.count_documents({})
        requires_referral = total_users > 0

        sponsor_info: Optional[Dict[str, str]] = None

        if request.method == "POST":
            first_name = request.form.get("first_name", "").strip()
            last_name = request.form.get("last_name", "").strip()
            email = request.form.get("email", "").strip().lower()
            phone = request.form.get("phone", "").strip()
            identity_number = request.form.get("identity_number", "").strip()
            membership_type = request.form.get("membership_type", "bireysel").strip().lower() or "bireysel"
            password = request.form.get("password", "")
            password_confirm = request.form.get("password_confirm", "")
            country_code = request.form.get("country_code", "").strip()
            sponsor_code = request.form.get("sponsor_code", "").strip().upper()
            dob_day = request.form.get("dob_day", "").strip()
            dob_month = request.form.get("dob_month", "").strip()
            dob_year = request.form.get("dob_year", "").strip()
            gender = request.form.get("gender", "kadin")
            is_foreign = request.form.get("is_foreign") is not None
            city = request.form.get("city", "").strip()
            district = request.form.get("district", "").strip()
            neighborhood = request.form.get("neighborhood", "").strip()
            tax_office = request.form.get("tax_office", "").strip()
            tax_number = request.form.get("tax_number", "").strip()
            postal_code = request.form.get("postal_code", "").strip()
            address = request.form.get("address", "").strip()
            agreement_distributor = request.form.get("agreement_distributor") is not None
            agreement_kvkk = request.form.get("agreement_kvkk") is not None

            province_list = list(PROVINCES.keys())

            form_state = {
                "first_name": first_name,
                "last_name": last_name,
                "email": email,
                "phone": phone,
                "identity_number": identity_number,
                "membership_type": membership_type,
                "dob_day": dob_day,
                "dob_month": dob_month,
                "dob_year": dob_year,
                "gender": gender,
                "is_foreign": is_foreign,
                "city": city,
                "district": district,
                "neighborhood": neighborhood,
                "tax_office": tax_office,
                "tax_number": tax_number,
                "postal_code": postal_code,
                "address": address,
                "agreement_distributor": agreement_distributor,
                "agreement_kvkk": agreement_kvkk,
            }

            selected_country = country_code or (COUNTRY_OPTIONS[0]["dial_code"] if COUNTRY_OPTIONS else "")

            if sponsor_code and sponsor_info is None:
                sponsor_lookup = app.db.users.find_one({"referral_code": sponsor_code})
                if sponsor_lookup:
                    sponsor_info = {
                        "name": sponsor_lookup.get("name", ""),
                        "referral_code": sponsor_lookup.get("referral_code"),
                    }

            def render_form() -> str:
                context = {
                    "countries": COUNTRY_OPTIONS,
                    "province_list": province_list,
                    "province_map": PROVINCES,
                    "selected_country": selected_country,
                    "requires_referral": requires_referral,
                    "sponsor_code": sponsor_code,
                    "sponsor_info": sponsor_info,
                    "datetime": datetime,
                }
                context.update(form_state)
                return render_template("auth/register.html", **context)

            if not first_name or not last_name or not email or not phone or not identity_number or not password or not country_code:
                flash("Lütfen tüm zorunlu alanları doldurun.", "error")
                return render_form()

            if not (dob_day and dob_month and dob_year):
                flash("Lütfen doğum tarihinizi seçin.", "error")
                return render_form()

            if not city or not district:
                flash("Lütfen şehir ve ilçe seçin.", "error")
                return render_form()

            if city not in PROVINCES or district not in PROVINCES.get(city, []):
                flash("Geçerli bir il ve ilçe kombinasyonu seçiniz.", "error")
                return render_form()

            try:
                birth_date = datetime(int(dob_year), int(dob_month), int(dob_day))
            except ValueError:
                flash("Geçerli bir doğum tarihi seçin.", "error")
                return render_form()

            if not agreement_distributor or not agreement_kvkk:
                flash("Lütfen sözleşmeleri onaylayın.", "error")
                return render_form()

            valid_country = next((c for c in COUNTRY_OPTIONS if c["dial_code"] == country_code), None)
            if valid_country is None:
                flash("Geçerli bir ülke seçiniz.", "error")
                return render_form()

            if password != password_confirm:
                flash("Şifreler eşleşmiyor.", "error")
                return render_form()

            if app.db.users.find_one({"email": email}):
                flash("Bu e-posta ile zaten bir hesabınız var. Lütfen giriş yapın.", "warning")
                return redirect(url_for("login"))

            cleaned_phone = "".join(ch for ch in phone if ch.isdigit() or ch == "+")
            if len(cleaned_phone) < 10:
                flash("Lütfen geçerli bir telefon numarası girin.", "error")
                return render_form()

            if app.db.users.find_one({"phone": cleaned_phone}):
                flash("Bu telefon numarasıyla kayıtlı bir hesap mevcut. Lütfen giriş yapın.", "warning")
                return redirect(url_for("login"))

            tckn = "".join(ch for ch in identity_number if ch.isdigit())
            if not validate_tckn(tckn):
                flash("T.C. Kimlik numarası doğrulanamadı. Lütfen bilgiyi kontrol edin.", "error")
                return render_form()

            tckn_hash = hash_identity_number(tckn)
            if app.db.users.find_one({"identity_number_hash": tckn_hash}):
                flash("Bu T.C. Kimlik numarasıyla kayıtlı bir hesap mevcut.", "warning")
                return redirect(url_for("login"))

            sponsor_doc = None
            placement_parent_id = None
            placement_position = None
            placement_status = "placed" if not requires_referral else "pending"

            if requires_referral:
                if not sponsor_code:
                    flash("ID kodu zorunludur.", "error")
                    return render_form()

                sponsor_doc = app.db.users.find_one({"referral_code": sponsor_code})
                if not sponsor_doc:
                    flash("Geçerli bir ID kodu giriniz.", "error")
                    return render_form()

                sponsor_info = {
                    "name": sponsor_doc.get("name", ""),
                    "referral_code": sponsor_doc.get("referral_code"),
                }

                placement_parent_id = sponsor_doc.get("_id")
                placement_status = "pending"

            password_hash = generate_password_hash(password)
            referral_code = generate_referral_code(app)
            encrypted_tckn = encrypt_identity_number(tckn)
            full_name = f"{first_name} {last_name}".strip()

            user_doc = {
                "name": full_name,
                "email": email,
                "phone": cleaned_phone,
                "identity_number_hash": tckn_hash,
                "identity_number_encrypted": encrypted_tckn,
                "password_hash": password_hash,
                "created_at": datetime.utcnow(),
                "country_code": country_code,
                "referral_code": referral_code,
                "sponsor_id": sponsor_doc["_id"] if sponsor_doc else None,
                "placement_parent_id": placement_parent_id,
                "placement_position": placement_position,
                "placement_status": placement_status,
                "profile": {
                    "first_name": first_name,
                    "last_name": last_name,
                    "membership_type": membership_type,
                    "birth_date": birth_date.date().isoformat(),
                    "gender": gender,
                    "is_foreign": is_foreign,
                    "city": city,
                    "district": district,
                    "neighborhood": neighborhood,
                    "tax_office": tax_office,
                    "tax_number": tax_number,
                    "postal_code": postal_code,
                    "address": address,
                    "agreements": {
                        "distributor": agreement_distributor,
                        "kvkk": agreement_kvkk,
                    },
                },
            }

            result = app.db.users.insert_one(user_doc)

            session["user_id"] = str(result.inserted_id)
            if placement_status == "pending":
                flash(
                    f"Kayıt işlemi tamamlandı. ID'niz: {referral_code}. Sponsor yerleştirme onayı bekleniyor.",
                    "success",
                )
            else:
                flash(f"Kayıt işlemi tamamlandı. ID'niz: {referral_code}", "success")
            return redirect(url_for("index"))

        sponsor_code = request.args.get("sponsor", "").strip().upper()
        selected_country = COUNTRY_OPTIONS[0]["dial_code"] if COUNTRY_OPTIONS else None

        if sponsor_code:
            sponsor_doc = app.db.users.find_one({"referral_code": sponsor_code})
            if sponsor_doc:
                sponsor_info = {
                    "name": sponsor_doc.get("name", ""),
                    "referral_code": sponsor_doc.get("referral_code"),
                }

        province_list_default = list(PROVINCES.keys())

        return render_template(
            "auth/register.html",
            countries=COUNTRY_OPTIONS,
            province_list=province_list_default,
            province_map=PROVINCES,
            selected_country=selected_country,
            requires_referral=requires_referral,
            sponsor_code=sponsor_code,
            sponsor_info=sponsor_info,
            datetime=datetime,
            first_name="",
            last_name="",
            membership_type="bireysel",
            email="",
            phone="",
            identity_number="",
            dob_day="",
            dob_month="",
            dob_year="",
            gender="kadin",
            is_foreign=False,
            city="",
            district="",
            neighborhood="",
            tax_office="",
            tax_number="",
            postal_code="",
            address="",
            agreement_distributor=False,
            agreement_kvkk=False,
        )

    @app.route("/dashboard")
    @login_required
    def dashboard():
        user = g.user
        referral_code = user.get("referral_code")
        referral_link = None
        if referral_code:
            base_url = request.url_root.rstrip("/")
            referral_link = f"{base_url}{url_for('register')}?sponsor={referral_code}"

        pending_cursor = app.db.users.find(
            {
                "placement_status": "pending",
                "placement_parent_id": user["_id"],
            },
            {
                "profile.first_name": 1,
                "profile.last_name": 1,
                "email": 1,
                "created_at": 1,
                "referral_code": 1,
            },
        )
        pending_placements: List[Dict] = []
        for doc in pending_cursor:
            pending_placements.append(
                {
                    "id": str(doc["_id"]),
                    "name": (
                        f"{doc.get('profile', {}).get('first_name', '')} "
                        f"{doc.get('profile', {}).get('last_name', '')}"
                    ).strip()
                    or doc.get("email", "Üye"),
                    "email": doc.get("email"),
                    "joined_at": doc.get("created_at"),
                    "referral_code": doc.get("referral_code"),
                }
            )

        profile = user.get("profile", {})
        sponsor_count = app.db.users.count_documents({"sponsor_id": user["_id"]})
        team_left = app.db.users.count_documents(
            {
                "placement_parent_id": user["_id"],
                "placement_position": "left",
                "placement_status": "placed",
            }
        )
        team_right = app.db.users.count_documents(
            {
                "placement_parent_id": user["_id"],
                "placement_position": "right",
                "placement_status": "placed",
            }
        )
        matching_left = profile.get("matching_left", 0)
        matching_right = profile.get("matching_right", 0)
        personal_cv = profile.get("personal_cv", 0)
        instant_income = profile.get("instant_income", 0)
        pending_count = len(pending_placements)

        title_value = profile.get("title") or profile.get("membership_type", "Girişimci").title()

        stored_avatar = profile.get("avatar_url") or user.get("avatar_url")
        user_initials = generate_initials(user.get("name", ""))
        avatar_src = stored_avatar or build_initials_avatar(user_initials)

        varis_members = collect_varis_members(user)
        dashboard_cards = [
            {
                "title": "KARİYERİNİZ",
                "icon": "diamond",
                "value": title_value,
                "subtitle": None,
                "color": "from-amber-600 to-amber-400",
                "link": url_for("career_tracking"),
            },
            {
                "title": "MEVCUT SEVİYENİZ",
                "icon": "workspace_premium",
                "value": profile.get("career", "Girişimci").title(),
                "subtitle": profile.get("next_career"),
                "color": "from-amber-700 to-yellow-500",
                "link": url_for("career_tracking"),
            },
            {
                "title": "GİRİŞİMCİLİK SEVİYENİZ",
                "icon": "insights",
                "value": profile.get("level", "Platin"),
                "subtitle": None,
                "color": "from-slate-800 to-slate-600",
            },
            {
                "title": "SPONSOR OLDUKLARIM",
                "icon": "diversity_3",
                "value": sponsor_count,
                "subtitle": None,
                "color": "from-sky-700 to-sky-500",
                "link": url_for("sponsored_page"),
            },
            {
                "title": "EKİBİM",
                "icon": "groups_2",
                "value": f"{team_left} / {team_right}",
                "subtitle": "Sol / Sağ üye",
                "color": "from-orange-600 to-amber-500",
            },
            {
                "title": "ANLIK EŞLEŞME",
                "icon": "scale",
                "value": f"{matching_left:.2f} / {matching_right:.2f}",
                "subtitle": "Sol / Sağ CV",
                "color": "from-orange-500 to-orange-600",
            },
            {
                "title": "TOPLAM KAZANÇ",
                "icon": "attach_money",
                "value": f"{personal_cv:,.2f} CV",
                "subtitle": None,
                "link": url_for("prim_info"),
                "color": "from-emerald-600 to-emerald-500",
            },
            {
                "title": "YERLEŞİM BEKLEYEN",
                "icon": "person_add",
                "value": pending_count,
                "subtitle": "Onay bekleyen",
                "color": "from-purple-600 to-fuchsia-500",
                "action": pending_count > 0,
            },
            {
                "title": "ANLIK KAZANÇ",
                "icon": "payments",
                "value": f"{instant_income:,.2f} ₺",
                "subtitle": None,
                "link": url_for("prim_info"),
                "color": "from-green-600 to-green-500",
            },
        ]

        career_entries = build_career_entries()
        current_turkish = (profile.get("career") or "DİSTRİBÜTÖR").upper()
        current_index = next(
            (i for i, entry in enumerate(career_entries) if entry["turkish"] == current_turkish),
            0,
        )
        current_career_english = career_entries[current_index]["english"]
        career_entries_ordered = [career_entries[current_index]] + [
            entry for i, entry in enumerate(career_entries) if i != current_index
        ]
        current_display_title = current_career_english
        current_display_subtitle = current_turkish
        for card in dashboard_cards:
            if card["title"] in {"MEVCUT SEVİYENİZ", "KARİYERİNİZ"}:
                card["value"] = current_display_title
                card["subtitle"] = current_display_subtitle
                card["icon"] = "diamond"

        return render_template(
            "dashboard.html",
            referral_code=referral_code,
            referral_link=referral_link,
            dashboard_cards=dashboard_cards,
            pending_placements=pending_placements,
            profile=profile,
            avatar_src=avatar_src,
            varis_members=varis_members,
            career_entries=career_entries,
            career_entries_ordered=career_entries_ordered,
            current_career_english=current_career_english,
        )

    def build_career_entries():
        return [
            {"turkish": "DİSTRİBÜTÖR", "english": "Distributor", "icon": "diamond", "left": 5000, "right": 0},
            {"turkish": "PLATİN", "english": "Platinum", "icon": "diamond", "left": 5000, "right": 5000},
            {"turkish": "İNCİ", "english": "Pearl", "icon": "diamond", "left": 15000, "right": 15000},
            {"turkish": "SAFİR", "english": "Sapphire", "icon": "diamond", "left": 50000, "right": 50000},
            {"turkish": "YAKUT", "english": "Ruby", "icon": "diamond", "left": 100000, "right": 100000},
            {"turkish": "ZÜMRÜT", "english": "Emerald", "icon": "diamond", "left": 250000, "right": 250000},
            {"turkish": "ELMAS", "english": "Diamond", "icon": "diamond", "left": 500000, "right": 500000},
            {"turkish": "DOUBLE DİAMOND", "english": "Double Diamond", "icon": "diamond", "left": 1000000, "right": 1000000},
            {"turkish": "TRİPLE DİAMOND", "english": "Triple Diamond", "icon": "diamond", "left": 2000000, "right": 2000000},
            {"turkish": "PRESIDENT", "english": "President", "icon": "diamond", "left": 4000000, "right": 4000000},
            {"turkish": "DOUBLE PRESIDENT", "english": "Double President", "icon": "diamond", "left": 8000000, "right": 8000000},
            {"turkish": "TRIPLE PRESIDENT", "english": "Triple President", "icon": "diamond", "left": 16000000, "right": 16000000},
        ]

    @app.route("/career-tracking")
    @login_required
    def career_tracking():
        profile = g.user.get("profile", {}) or {}
        current_career = (profile.get("career") or "DİSTRİBÜTÖR").upper()
        career_entries = build_career_entries()
        turkish_to_english = {entry["turkish"]: entry["english"] for entry in career_entries}
        current_turkish = current_career
        current_career = turkish_to_english.get(current_turkish, "Distributor")
        careers = [entry["english"] for entry in career_entries]

        time_control = {
            "selected_month": request.args.get("month", datetime.utcnow().strftime("%B")),
            "selected_year": request.args.get("year", str(datetime.utcnow().year)),
        }

        rank_cards = []
        for index, entry in enumerate(career_entries, start=1):
            label = entry["english"]
            threshold = entry.get("left", 0) + entry.get("right", 0)
            rank_cards.append(
                {
                    "step": index,
                    "label": label,
                    "turkish": entry["turkish"],
                    "icon": entry.get("icon", "diamond"),
                    "threshold": f"{threshold:,.0f} PV",
                    "left_target": entry.get("left", 0),
                    "right_target": entry.get("right", 0),
                    "subtitle": "Aktif" if label == current_career else "Bekleniyor",
                    "progress": min(100, index * 8 + 30),
                }
            )

        try:
            current_index = careers.index(current_career)
        except ValueError:
            current_index = 0

        current_card = rank_cards[current_index] if 0 <= current_index < len(rank_cards) else rank_cards[0] if rank_cards else None

        return render_template(
            "career_tracking.html",
            careers=careers,
            rank_cards=rank_cards,
            current_career=current_career,
            career_entries=career_entries,
            time_control=time_control,
            current_card=current_card,
            summary={
                "left_pv": profile.get("matching_left", 0),
                "right_pv": profile.get("matching_right", 0),
                "next_rank": careers[min(current_index + 1, len(careers) - 1)],
                "target_pv": f"{career_entries[min(current_index + 1, len(career_entries) - 1)].get('left', 0) + career_entries[min(current_index + 1, len(career_entries) - 1)].get('right', 0):,.0f}",
            },
            datetime=datetime,
        )

    @app.route("/bank-info", methods=["GET", "POST"])
    @login_required
    def bank_info():
        user = g.user
        profile = user.get("profile", {})
        bank_info = profile.get("bank_info") or {}

        if request.method == "POST":
            account_name = request.form.get("account_name", "").strip()
            bank_name = request.form.get("bank_name", "").strip()
            iban = request.form.get("iban", "").strip()
            swift = request.form.get("swift", "").strip()

            if not account_name or not bank_name or not iban:
                flash("Lütfen zorunlu alanları doldurun.", "warning")
                return redirect(url_for("bank_info"))

            bank_info = {
                "account_name": account_name,
                "bank_name": bank_name,
                "iban": iban,
                "swift": swift,
            }

            app.db.users.update_one(
                {"_id": user["_id"]},
                {"$set": {"profile.bank_info": bank_info}},
            )
            flash("Banka bilgileriniz güncellendi.", "success")
            return redirect(url_for("bank_info"))

        return render_template("bank_info.html", bank_info=bank_info)

    @app.route("/varis")
    @login_required
    def varis_page():
        varis_members = collect_varis_members(g.user)
        return render_template("varis.html", varis_members=varis_members)

    @app.route("/userinfo")
    @login_required
    def userinfo():
        user = g.user
        profile = user.get("profile", {})
        referral_code = user.get("referral_code")
        referral_link = None
        if referral_code:
            base_url = request.url_root.rstrip("/")
            referral_link = f"{base_url}{url_for('register')}?sponsor={referral_code}"

        sponsor_info = None
        sponsor_id = user.get("sponsor_id")
        if sponsor_id:
            sponsor_doc = app.db.users.find_one(
                {"_id": sponsor_id},
                {"name": 1, "referral_code": 1, "phone": 1},
            )
            if sponsor_doc:
                sponsor_info = {
                    "name": sponsor_doc.get("name", "Sponsor"),
                    "phone": sponsor_doc.get("phone"),
                    "code": sponsor_doc.get("referral_code"),
                }

        gender_map = {"erkek": "ERKEK", "kadin": "KADIN"}
        gender_raw = profile.get("gender", "")
        gender_display = gender_map.get(gender_raw.lower(), gender_raw.upper() if gender_raw else "Belirtilmedi")

        country_name = next(
            (c["name"] for c in COUNTRY_OPTIONS if c["dial_code"] == user.get("country_code")),
            None,
        )
        country_label = country_name or profile.get("country") or "Belirtilmedi"

        birth_date_label = None
        birth_date_raw = profile.get("birth_date")
        if birth_date_raw:
            try:
                birth_date_label = datetime.fromisoformat(birth_date_raw).strftime("%d.%m.%Y")
            except ValueError:
                birth_date_label = birth_date_raw

        identity_token = user.get("identity_number_encrypted")
        identity_number = decrypt_identity_number(identity_token) if identity_token else None

        created_at = user.get("created_at")
        now = datetime.utcnow()
        registration_label = "Kayıt tarihi bilgisi yok."
        if created_at:
            days_registered = max(0, (now.date() - created_at.date()).days)
            registration_label = (
                f"{created_at.strftime('%d.%m.%Y')} ({days_registered} gündür sisteme kayıtlısınız)"
            )

        membership_level_raw = profile.get("level") or profile.get("membership_type") or "Bireysel"
        membership_level_display = membership_level_raw.upper()

        full_name = user.get("name") or f"{profile.get('first_name', '')} {profile.get('last_name', '')}".strip() or "Üye"

        sponsor_members = collect_sponsor_members(user)

        return render_template(
            "userinfo.html",
            full_name=full_name,
            identity_number=identity_number,
            email=user.get("email"),
            birth_date=birth_date_label,
            gender=gender_display,
            country=country_label,
            city=profile.get("city"),
            district=profile.get("district"),
            neighborhood=profile.get("neighborhood"),
            address=profile.get("address"),
            membership_level=membership_level_display,
            registration_label=registration_label,
            member_number=referral_code or "Tanımlanmadı",
            referral_link=referral_link,
            sponsor_info=sponsor_info,
            phone=user.get("phone"),
            sponsor_members=sponsor_members,
        )

    @app.route("/prim-info")
    @login_required
    def prim_info():
        user = g.user
        profile = user.get("profile", {})
        months = [
            "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
            "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık",
        ]
        current_year = datetime.utcnow().year
        created_at = user.get("created_at")
        reg_year = None
        reg_month = None
        if isinstance(created_at, datetime):
            reg_year = created_at.year
            reg_month = created_at.month
        elif isinstance(created_at, str):
            try:
                parsed = datetime.fromisoformat(created_at)
                reg_year = parsed.year
                reg_month = parsed.month
            except ValueError:
                pass

        earliest_year = reg_year or current_year
        year_options = list(range(current_year, earliest_year - 1, -1))

        default_year = str(reg_year if reg_year else current_year)
        selected_year = request.args.get("year", default_year)

        try:
            selected_year_int = int(selected_year)
        except (TypeError, ValueError):
            selected_year_int = current_year

        if selected_year_int > current_year:
            selected_year_int = current_year
        if selected_year_int < earliest_year:
            selected_year_int = earliest_year

        month_options = months
        if not reg_month:
            reg_month = 1
        if selected_year_int == reg_year and reg_month:
            default_month = months[reg_month - 1]
        elif selected_year_int == current_year:
            default_month = months[datetime.utcnow().month - 1]
        else:
            default_month = months[0]

        selected_month = request.args.get("month", default_month)
        if selected_month not in month_options:
            selected_month = default_month

        bonus_rows = [
            ("Satış Karı", profile.get("sales_profit", 0)),
            ("Referans Bonusu", profile.get("referal_bonus", 0)),
            ("Hızlı Başlangıç", profile.get("fast_start", 0)),
            ("Eşleşme Primi", profile.get("matching_bonus", 0)),
            ("Matching Bonusu", profile.get("matching_bonus_v2", 0)),
        ]

        monthly_total = sum(value for _, value in bonus_rows)
        tax_rate = 0.2
        tax_amount = monthly_total * tax_rate
        credited_total = monthly_total - tax_amount

        bonus_summary = [
            ("Prim Tutarı", monthly_total),
            ("Gelir Vergisi(%20)", tax_amount),
        ]

        return render_template(
            "priminfo.html",
            months=months,
            year_options=year_options,
            selected_month=selected_month,
            selected_year=selected_year,
            bonus_rows=bonus_rows,
            monthly_total=monthly_total,
            bonus_summary=bonus_summary,
            credited_total=credited_total,
            format_currency=format_currency,
        )

    @app.route("/sponsored")
    @login_required
    def sponsored_page():
        user = g.user
        sponsor_members = collect_sponsor_members(user)
        return render_template(
            "sponsored.html",
            sponsor_members=sponsor_members,
        )

    @app.route("/faststart")
    @login_required
    def faststart_page():
        user = g.user
        records = collect_faststart_records(user)
        total_bonus = sum(record["bonus"] for record in records)
        return render_template(
            "faststart.html",
            records=records,
            total_bonus=total_bonus,
            format_currency=format_currency,
        )

    @app.route("/referans-bonusu")
    @login_required
    def referans_bonus_page():
        user = g.user
        records = collect_referral_bonus_records(user)
        months = [
            "Ocak",
            "Şubat",
            "Mart",
            "Nisan",
            "Mayıs",
            "Haziran",
            "Temmuz",
            "Ağustos",
            "Eylül",
            "Ekim",
            "Kasım",
            "Aralık",
        ]
        current_year = datetime.utcnow().year
        created_at = user.get("created_at")
        created_year = None
        if isinstance(created_at, datetime):
            created_year = created_at.year
        elif isinstance(created_at, str):
            try:
                created_year = datetime.fromisoformat(created_at).year
            except ValueError:
                pass

        earliest_year = created_year or current_year
        if earliest_year > current_year:
            earliest_year = current_year

        year_options = list(range(current_year, earliest_year - 1, -1))
        if not year_options:
            year_options = [current_year]

        default_year = str(current_year)
        selected_year = request.args.get("year", default_year)
        try:
            selected_year_int = int(selected_year)
        except (TypeError, ValueError):
            selected_year_int = current_year

        if selected_year_int > current_year:
            selected_year_int = current_year
        if selected_year_int < earliest_year:
            selected_year_int = earliest_year

        default_month = months[datetime.utcnow().month - 1]
        selected_month = request.args.get("month", default_month)
        if selected_month not in months:
            selected_month = default_month

        search_query = request.args.get("member", "").strip()
        search_lower = search_query.lower()

        records.sort(
            key=lambda entry: entry.get("parsed_date") or datetime.min, reverse=True
        )

        filtered_records = []
        for record in records:
            parsed_date = record.get("parsed_date")
            month_name = months[parsed_date.month - 1] if parsed_date else None
            year_value = parsed_date.year if parsed_date else None

            if month_name and month_name != selected_month:
                continue
            if year_value and year_value != selected_year_int:
                continue

            if search_lower:
                member = record.get("member_number", "").lower()
                full_name = record.get("full_name", "").lower()
                if search_lower not in member and search_lower not in full_name:
                    continue

            filtered_records.append(record)

        total_amount = sum(record["amount"] for record in filtered_records)

        return render_template(
            "bonref.html",
            months=months,
            year_options=year_options,
            selected_month=selected_month,
            selected_year=selected_year,
            records=filtered_records,
            total_amount=total_amount,
            search_query=search_query,
            format_currency=format_currency,
        )

    @app.route("/referans-ekip")
    @login_required
    def referans_team_page():
        user = g.user
        sponsor_members = collect_sponsor_members(user)
        months = [
            "Ocak",
            "Şubat",
            "Mart",
            "Nisan",
            "Mayıs",
            "Haziran",
            "Temmuz",
            "Ağustos",
            "Eylül",
            "Ekim",
            "Kasım",
            "Aralık",
        ]
        current_year = datetime.utcnow().year
        created_at = user.get("created_at")
        created_year = None
        if isinstance(created_at, datetime):
            created_year = created_at.year
        elif isinstance(created_at, str):
            try:
                created_year = datetime.fromisoformat(created_at).year
            except ValueError:
                pass
        earliest_year = created_year or current_year
        if earliest_year > current_year:
            earliest_year = current_year
        year_options = list(range(current_year, earliest_year - 1, -1))
        if not year_options:
            year_options = [current_year]

        selected_year = request.args.get("year", str(current_year))
        try:
            selected_year_int = int(selected_year)
        except (TypeError, ValueError):
            selected_year_int = current_year

        if selected_year_int > current_year:
            selected_year_int = current_year
        if selected_year_int < earliest_year:
            selected_year_int = earliest_year

        default_month = months[datetime.utcnow().month - 1]
        selected_month = request.args.get("month", default_month)
        if selected_month not in months:
            selected_month = default_month

        search_query = request.args.get("member", "").strip()
        search_lower = search_query.lower()

        filtered_members = []
        for member in sponsor_members:
            member_number = member.get("member_number", "")
            full_name = member.get("full_name", "")
            if search_lower and search_lower not in member_number.lower() and search_lower not in full_name.lower():
                continue
            filtered_members.append(member)

        status_palette = [
            {"key": "aktif", "label": "Aktif Üye", "icon": "person", "color": "bg-[#16a34a]"},
            {"key": "pasif", "label": "Pasif Üye", "icon": "person_off", "color": "bg-[#dc2626]"},
            {"key": "siparis", "label": "Son yıl içinde sipariş vermemiş", "icon": "calendar_month", "color": "bg-[#7c3aed]"},
            {"key": "silinmis", "label": "Silinmiş Üye", "icon": "clear", "color": "bg-[#0f172a]"},
        ]

        records = []
        for index, member in enumerate(filtered_members):
            palette = status_palette[index % len(status_palette)]
            personal_points = (index + 1) * 8
            team_points = (index + 1) * 12
            total_points = personal_points + team_points
            records.append(
                {
                    "member_number": member.get("member_number", "Tanımlanmadı"),
                    "full_name": member.get("full_name", "Üye"),
                    "total_members": (index % 3) + 1,
                    "personal_points": personal_points,
                    "team_points": team_points,
                    "total_points": total_points,
                    "status_key": palette["key"],
                    "status_label": palette["label"],
                    "status_icon": palette["icon"],
                    "status_color": palette["color"],
                }
            )

        return render_template(
            "refekip.html",
            months=months,
            year_options=year_options,
            selected_month=selected_month,
            selected_year=selected_year,
            search_query=search_query,
            records=records,
            status_legends=status_palette,
            format_points=format_points,
        )

    @app.route("/s400")
    def s400_portal():
        return render_template("s400/index.html")

    @app.route("/upload-avatar", methods=["POST"])
    @login_required
    def upload_avatar():
        user = g.user
        file = request.files.get("avatar")
        if not file or not file.filename:
            flash("Lütfen bir resim dosyası seçin.", "warning")
            return redirect(url_for("dashboard"))
        if not allowed_avatar_file(file.filename):
            flash("Sadece JPG, PNG, GIF veya WEBP formatları desteklenmektedir.", "error")
            return redirect(url_for("dashboard"))

        extension = file.filename.rsplit(".", 1)[1].lower()
        timestamp = int(datetime.utcnow().timestamp())
        filename = secure_filename(f"{user['_id']}_{timestamp}.{extension}")
        avatars_dir = os.path.join(app.root_path, "static", "avatars")
        os.makedirs(avatars_dir, exist_ok=True)
        filepath = os.path.join(avatars_dir, filename)
        try:
            file.save(filepath)
        except Exception:
            flash("Profil resmi yüklenirken bir hata oluştu.", "error")
            return redirect(url_for("dashboard"))

        avatar_url = url_for("static", filename=f"avatars/{filename}")
        app.db.users.update_one({"_id": user["_id"]}, {"$set": {"profile.avatar_url": avatar_url}})
        flash("Profil resmi başarıyla yüklendi.", "success")
        return redirect(url_for("dashboard"))

    @app.route("/change-password", methods=["GET", "POST"])
    @login_required
    def change_password():
        if request.method == "GET":
            return render_template("change_password_page.html")
        user = g.user
        old_password = request.form.get("old_password", "")
        new_password = request.form.get("new_password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not old_password or not new_password or not confirm_password:
            flash("Lütfen tüm alanları doldurun.", "warning")
            return redirect(url_for("dashboard"))

        if new_password != confirm_password:
            flash("Yeni şifre ve tekrarı eşleşmiyor.", "error")
            return redirect(url_for("dashboard"))

        if not check_password_hash(user["password_hash"], old_password):
            flash("Eski şifre yanlış.", "error")
            return redirect(url_for("dashboard"))

        if old_password == new_password:
            flash("Yeni şifre eski şifreden farklı olmalıdır.", "warning")
            return redirect(url_for("dashboard"))

        new_hash = generate_password_hash(new_password)
        app.db.users.update_one({"_id": user["_id"]}, {"$set": {"password_hash": new_hash}})
        flash("Şifreniz başarıyla güncellendi.", "success")
        return redirect(url_for("dashboard"))

    @app.route("/save-varis", methods=["POST"])
    @login_required
    def save_varis():
        user = g.user
        entry_id = request.form.get("entry_id", "").strip()
        name = request.form.get("name", "").strip()
        tc = request.form.get("tc", "").strip()
        phone = request.form.get("phone", "").strip()
        email = request.form.get("email", "").strip()
        relation = request.form.get("relation", "").strip()
        address = request.form.get("address", "").strip()

        if not name or not tc:
            flash("Ad Soyad ve TC alanları zorunludur.", "warning")
            return redirect(url_for("dashboard"))

        base_entry = {
            "name": name,
            "tc": tc,
            "phone": phone or "Belirtilmedi",
            "email": email or "Belirtilmedi",
            "relation": relation or "Belirtilmedi",
            "address": address or "Belirtilmedi",
        }

        if entry_id:
            existing = app.db.users.find_one(
                {"_id": user["_id"], "profile.varis_entries.entry_id": entry_id},
                {"profile.varis_entries.$": 1},
            )
            if existing:
                existing_entry = existing.get("profile", {}).get("varis_entries", [{}])[0]
                base_entry["entry_id"] = entry_id
                base_entry["created_at"] = existing_entry.get("created_at", datetime.utcnow())
                base_entry["updated_at"] = datetime.utcnow()
                app.db.users.update_one(
                    {"_id": user["_id"], "profile.varis_entries.entry_id": entry_id},
                    {"$set": {"profile.varis_entries.$": base_entry}},
                )
                flash("Varis bilgisi güncellendi.", "success")
                return redirect(url_for("dashboard"))

        base_entry["entry_id"] = entry_id or f"manual-{uuid4().hex}"
        base_entry["created_at"] = datetime.utcnow()
        app.db.users.update_one(
            {"_id": user["_id"]},
            {"$push": {"profile.varis_entries": base_entry}},
        )
        flash("Varis bilgisi eklenmiştir.", "success")
        return redirect(url_for("dashboard"))

    @app.route("/delete-varis", methods=["POST"])
    @login_required
    def delete_varis():
        user = g.user
        entry_id = request.form.get("entry_id", "").strip()
        if not entry_id:
            flash("Silinecek kayıt bulunamadı.", "warning")
            return redirect(url_for("dashboard"))

        result = app.db.users.update_one(
            {"_id": user["_id"]},
            {"$pull": {"profile.varis_entries": {"entry_id": entry_id}}},
        )
        if result.modified_count:
            flash("Varis bilgisi silindi.", "success")
        else:
            flash("Kayıt silinemedi.", "error")
        return redirect(url_for("dashboard"))

<<<<<<< HEAD
    @app.route("/login", methods=["GET", "POST"])
    def login():
=======
    def _render_login_view(template_name: str):
>>>>>>> 894ff30 (BestSoft)
        if request.method == "POST":
            identifier = request.form.get("identifier", "").strip()
            password = request.form.get("password", "")
            next_url = request.args.get("next") or request.form.get("next") or url_for("index")

<<<<<<< HEAD
            user = resolve_user_by_identifier(app, identifier)
            if not user or not check_password_hash(user["password_hash"], password):
                flash("Kimlik bilgileri veya şifre hatalı.", "error")
                return render_template("auth/login.html", identifier=identifier, next=next_url)
=======
            if identifier == DEMO_LOGIN_IDENTIFIER and password == DEMO_LOGIN_PASSWORD:
                user = ensure_demo_user_exists(app)
            else:
                user = resolve_user_by_identifier(app, identifier)
                if user and not check_password_hash(user["password_hash"], password):
                    user = None

            if not user:
                flash("Kimlik bilgileri veya şifre hatalı.", "error")
                return render_template(template_name, identifier=identifier, next=next_url)
>>>>>>> 894ff30 (BestSoft)

            session["user_id"] = str(user["_id"])
            flash("Tekrar hoş geldiniz!", "success")
            return redirect(next_url)

        next_url = request.args.get("next", "")
<<<<<<< HEAD
        return render_template("auth/login.html", next=next_url, identifier="")
=======
        identifier = request.args.get("identifier", "")
        return render_template(template_name, next=next_url, identifier=identifier)

    @app.route("/login", methods=["GET", "POST"])
    def login():
        return _render_login_view("auth/login.html")

    @app.route("/bestsoft", methods=["GET", "POST"])
    def bestsoft_login():
        return _render_login_view("bestsoft/login.html")

    @app.route("/bestwork")
    def bestsoft_landing():
        return render_template("bestsoft/index.html")
>>>>>>> 894ff30 (BestSoft)

    @app.route("/forgot-password", methods=["GET", "POST"])
    def forgot_password():
        identifier = ""
        if request.method == "POST":
            identifier = request.form.get("identifier", "").strip()
            if not identifier:
                flash("Lütfen e-posta, telefon veya ID girin.", "warning")
            else:
                user = resolve_user_by_identifier(app, identifier)
                if not user:
                    flash("Girilen bilgilerle eşleşen kullanıcı bulunamadı.", "warning")
                else:
                    flash("Şifre sıfırlama bağlantısı kayıtlı e-posta adresinize gönderildi.", "success")

        return render_template("auth/forgot_password.html", identifier=identifier)

    @app.route("/logout")
    def logout():
        session.clear()
        flash("Güvenli çıkış yapıldı.", "info")
        return redirect(url_for("index"))

    @app.route("/cart")
    def cart():
        cart_items, cart_total = load_cart_with_products(app)
        return render_template("cart.html", cart_items=cart_items, cart_total=cart_total)

    @app.route("/cart/add/<product_id>", methods=["POST"])
    def add_to_cart(product_id: str):
        product = fetch_product(app, product_id)
        if not product:
            abort(404)

        try:
            quantity = int(request.form.get("quantity", "1"))
        except ValueError:
            quantity = 1

        if quantity < 1:
            quantity = 1

        cart: List[Dict] = session.get("cart", [])
        for item in cart:
            if item["product_id"] == str(product["_id"]):
                item["quantity"] += quantity
                break
        else:
            cart.append({"product_id": str(product["_id"]), "quantity": quantity})

        session["cart"] = cart
        session.modified = True

        flash(f"{product['name']} sepetinize eklendi.", "success")
        return redirect(request.referrer or url_for("index"))

    @app.route("/cart/update/<product_id>", methods=["POST"])
    def update_cart_item(product_id: str):
        cart: List[Dict] = session.get("cart", [])
        try:
            quantity = int(request.form.get("quantity", "1"))
        except ValueError:
            quantity = 1

        updated = False
        for item in cart:
            if item["product_id"] == product_id:
                if quantity <= 0:
                    cart.remove(item)
                else:
                    item["quantity"] = quantity
                updated = True
                break

        if updated:
            session["cart"] = cart
            session.modified = True
            flash("Sepetiniz güncellendi.", "info")

        return redirect(url_for("cart"))

    @app.route("/cart/clear", methods=["POST"])
    def clear_cart():
        session.pop("cart", None)
        flash("Sepetiniz temizlendi.", "info")
        return redirect(url_for("cart"))

    @app.route("/checkout", methods=["GET", "POST"])
    @login_required
    def checkout():
        cart_items, cart_total = load_cart_with_products(app)
        if not cart_items:
            flash("Sepetiniz boş. Lütfen ürün ekleyin.", "warning")
            return redirect(url_for("index"))

        profile = g.user.get("profile", {}) or {}
        saved_addresses = profile.get("addresses", []) or []
        selected_address_id = "new"
        new_address_data = {
            "label": "",
            "address": "",
            "city": "",
            "postal_code": "",
            "district": "",
            "note": "",
            "save_address": False,
        }

        if request.method == "POST":
            selected_address_id = request.form.get("selected_address", "new")

            delivery_address = None
            if selected_address_id != "new":
                delivery_address = next(
                    (addr for addr in saved_addresses if addr.get("address_id") == selected_address_id),
                    None,
                )
                if not delivery_address:
                    flash("Seçilen adres bulunamadı.", "warning")
                    return render_template(
                        "checkout.html",
                        cart_items=cart_items,
                        cart_total=cart_total,
                        saved_addresses=saved_addresses,
                        selected_address_id="new",
                        new_address_data=new_address_data,
                    )
            else:
                new_address_data = {
                    "label": request.form.get("address_label", "").strip(),
                    "address": request.form.get("address_line", "").strip(),
                    "city": request.form.get("city", "").strip(),
                    "postal_code": request.form.get("postal_code", "").strip(),
                    "district": request.form.get("district", "").strip(),
                    "note": request.form.get("address_note", "").strip(),
                    "save_address": request.form.get("save_address") is not None,
                }

                if not (
                    new_address_data["label"]
                    and new_address_data["address"]
                    and new_address_data["city"]
                    and new_address_data["postal_code"]
                ):
                    flash("Lütfen tüm teslimat bilgilerini eksiksiz doldurun.", "warning")
                    return render_template(
                        "checkout.html",
                        cart_items=cart_items,
                        cart_total=cart_total,
                        saved_addresses=saved_addresses,
                        selected_address_id="new",
                        new_address_data=new_address_data,
                    )

                delivery_address = {
                    "label": new_address_data["label"],
                    "address": new_address_data["address"],
                    "city": new_address_data["city"],
                    "postal_code": new_address_data["postal_code"],
                    "district": new_address_data["district"],
                    "note": new_address_data["note"],
                }

                if new_address_data["save_address"]:
                    stored_address = {
                        "address_id": uuid4().hex,
                        **delivery_address,
                        "created_at": datetime.utcnow(),
                    }
                    app.db.users.update_one(
                        {"_id": g.user["_id"]},
                        {"$push": {"profile.addresses": stored_address}},
                    )
                    saved_addresses.append(stored_address)

            now = datetime.utcnow()
            date_part = now.strftime("%y%m%d")
            time_part = now.strftime("%H%M%S")
            daily_count = app.db.orders.count_documents(
                {"order_number": {"$regex": f'^{date_part}'}}
            )
            order_number = f"{date_part}{time_part}{daily_count + 1:03d}"

            order_doc = {
                "user_id": g.user["_id"],
                "order_number": order_number,
                "items": [
                    {
                        "product_id": ObjectId(item["product_id"]),
                        "name": item["product"]["name"],
                        "price": item["product"]["price"],
                        "quantity": item["quantity"],
                    }
                    for item in cart_items
                ],
                "total": cart_total,
                "created_at": datetime.utcnow(),
                "status": "hazırlanıyor",
                "delivery_address": {
                    "label": delivery_address.get("label"),
                    "address": delivery_address.get("address"),
                    "city": delivery_address.get("city"),
                    "postal_code": delivery_address.get("postal_code"),
                    "district": delivery_address.get("district"),
                    "note": delivery_address.get("note"),
                },
            }

            app.db.orders.insert_one(order_doc)
            session.pop("cart", None)
            flash("Siparişiniz alındı! Teşekkür ederiz.", "success")
            return redirect(url_for("orders"))

        return render_template(
            "checkout.html",
            cart_items=cart_items,
            cart_total=cart_total,
            saved_addresses=saved_addresses,
            selected_address_id=selected_address_id,
            new_address_data=new_address_data,
        )

    @app.route("/orders")
    @login_required
    def orders():
        user_orders = list(
            app.db.orders.find({"user_id": g.user["_id"]}).sort("created_at", -1)
        )
        return render_template("orders.html", orders=user_orders)

    @app.route("/placement/assign", methods=["POST"])
    @login_required
    def assign_placement():
        placement_user_id = request.form.get("user_id", "").strip()
        placement_side = request.form.get("placement_side", "").strip().lower()

        if placement_side not in {"left", "right"}:
            flash("Lütfen geçerli bir yerleşim seçin.", "error")
            return redirect(request.referrer or url_for("index"))

        try:
            pending_user = app.db.users.find_one({"_id": ObjectId(placement_user_id)})
        except Exception:
            pending_user = None

        if not pending_user:
            flash("Yerleştirilecek üye bulunamadı.", "error")
            return redirect(request.referrer or url_for("index"))

        if pending_user.get("placement_status") != "pending":
            flash("Bu üye zaten yerleştirilmiş.", "warning")
            return redirect(request.referrer or url_for("index"))

        parent_id = pending_user.get("placement_parent_id")
        if not parent_id or parent_id != g.user["_id"]:
            flash("Bu üyeyi yerleştirme yetkiniz yok.", "error")
            return redirect(request.referrer or url_for("index"))

        parent_doc = app.db.users.find_one(
            {"_id": g.user["_id"]}, {"left_child_id": 1, "right_child_id": 1}
        )
        if not parent_doc:
            flash("Sponsor bilgisi bulunamadı.", "error")
            return redirect(request.referrer or url_for("index"))

        child_field = f"{placement_side}_child_id"
        if parent_doc.get(child_field):
            flash(f"{placement_side.capitalize()} kolu zaten dolu.", "error")
            return redirect(request.referrer or url_for("index"))

        app.db.users.update_one(
            {"_id": g.user["_id"]}, {"$set": {child_field: pending_user["_id"]}}
        )
        app.db.users.update_one(
            {"_id": pending_user["_id"]},
            {
                "$set": {
                    "placement_status": "placed",
                    "placement_position": placement_side,
                }
            },
        )

        flash(
            f"{pending_user.get('profile', {}).get('first_name', 'Üye')} {placement_side} koluna yerleştirildi.",
            "success",
        )
        return redirect(request.referrer or url_for("index"))


def generate_referral_code(app: Flask) -> str:
    """Her kullanıcı için benzersiz ID kodu üret."""
    prefix = "TR"
    characters = string.digits
    for _ in range(50):
        digits_count = random.choice([8, 9])
        suffix = "".join(random.choices(characters, k=digits_count))
        code = f"{prefix}{suffix}"
        if not app.db.users.find_one({"referral_code": code}):
            return code
    raise RuntimeError("ID kodu oluşturulamadı. Lütfen tekrar deneyin.")


def find_binary_slot(app: Flask, sponsor_doc: Dict) -> Tuple[Optional[ObjectId], Optional[str]]:
    """Binary ağında uygun ilk boş pozisyonu bul."""
    sponsor_id = sponsor_doc.get("_id")
    if not sponsor_id:
        return None, None
    queue = deque([sponsor_id])
    visited: set = set()

    while queue:
        current_id = queue.popleft()
        if current_id in visited:
            continue
        visited.add(current_id)

        node = app.db.users.find_one(
            {"_id": current_id},
            {"left_child_id": 1, "right_child_id": 1},
        )
        if not node:
            continue

        left_child = node.get("left_child_id")
        right_child = node.get("right_child_id")

        if not left_child:
            return current_id, "left"
        if not right_child:
            return current_id, "right"

        queue.append(left_child)
        queue.append(right_child)

    return None, None


def resolve_user_by_identifier(app: Flask, identifier: str):
    """E-posta, telefon veya ID kodu ile kullanıcıyı bul."""
    if not identifier:
        return None

    identifier = identifier.strip()
    if not identifier:
        return None

    lowered = identifier.lower()
    if "@" in identifier:
        user = app.db.users.find_one({"email": lowered})
        if user:
            return user

    cleaned_phone = "".join(ch for ch in identifier if ch.isdigit() or ch == "+")
    if len(cleaned_phone) >= 10:
        user = app.db.users.find_one({"phone": cleaned_phone})
        if user:
            return user

    upper = identifier.upper()
    return app.db.users.find_one({"referral_code": upper})


def validate_tckn(tckn: str) -> bool:
    """T.C. Kimlik numarasını format kurallarına göre doğrula."""
    if len(tckn) != 11 or not tckn.isdigit() or tckn[0] == "0":
        return False

    digits = [int(ch) for ch in tckn]
    odd_sum = sum(digits[0:9:2])
    even_sum = sum(digits[1:8:2])
    digit10 = ((odd_sum * 7) - even_sum) % 10
    if digit10 != digits[9]:
        return False

    digit11 = (sum(digits[:10])) % 10
    return digit11 == digits[10]


def hash_identity_number(tckn: str) -> str:
    """TCKN için geri döndürülemez hash üret."""
    return hashlib.sha256(tckn.encode("utf-8")).hexdigest()


def encrypt_identity_number(tckn: str) -> str:
    """TCKN değerini Fernet ile şifrele."""
    cipher = get_identity_cipher()
    token = cipher.encrypt(tckn.encode("utf-8"))
    return token.decode("utf-8")


def decrypt_identity_number(token: str) -> Optional[str]:
    """Gerekirse TCKN bilgisini çöz."""
    cipher = get_identity_cipher()
    try:
        value = cipher.decrypt(token.encode("utf-8"))
        return value.decode("utf-8")
    except (InvalidToken, ValueError):
        return None


def get_identity_cipher() -> Fernet:
    global _identity_cipher
    if _identity_cipher is not None:
        return _identity_cipher

    secret = app_config("TCKN_SECRET_KEY")
    generated = False
    if not secret:
        generated_key = base64.urlsafe_b64encode(os.urandom(32)).decode("utf-8")
        secret = generated_key
        generated = True

    digest = hashlib.sha256(secret.encode("utf-8")).digest()
    key = base64.urlsafe_b64encode(digest)
    _identity_cipher = Fernet(key)

    if generated:
        message = (
            "TCKN_SECRET_KEY ortam değişkeni tanımlı değil. Geçici bir anahtar üretildi; "
            "kayıtlı TCKN verileri uygulama yeniden başlatıldığında çözümlenemez. "
            "Lütfen kalıcı bir TCKN_SECRET_KEY tanımlayın."
        )
        try:
            current_app.logger.warning(message)
        except RuntimeError:
            print(message)

    return _identity_cipher


def fetch_product(app: Flask, product_id: str):
    """Verilen ürün kimliğiyle ürünü bul."""
    try:
        return app.db.products.find_one({"_id": ObjectId(product_id)})
    except Exception:
        return None


def load_cart_with_products(app: Flask):
    """
    Oturumdaki sepet öğelerini ürün detaylarıyla birleştir.
    cart_items çıktısı: [{"product": product_doc, "quantity": int, "line_total": float}, ...]
    """
    cart: List[Dict] = session.get("cart", [])
    detailed_items = []
    cart_total = 0.0

    for item in cart:
        product = fetch_product(app, item["product_id"])
        if not product:
            continue

        quantity = int(item.get("quantity", 1))
        line_total = float(product["price"]) * quantity
        cart_total += line_total

        product_data = dict(product)
        product_data["_id"] = str(product["_id"])

        detailed_items.append(
            {
                "product": product_data,
                "product_id": product_data["_id"],
                "quantity": quantity,
                "line_total": line_total,
            }
        )

    cart_total = round(cart_total, 2)
    return detailed_items, cart_total


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)
