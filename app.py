import base64
from collections import deque
from datetime import datetime
from functools import wraps
import hashlib
import os
import random
import string
from typing import Dict, List, Optional, Tuple

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
from werkzeug.security import check_password_hash, generate_password_hash
from cryptography.fernet import Fernet, InvalidToken


_identity_cipher: Optional[Fernet] = None


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

            if requires_referral:
                if not sponsor_code:
                    flash("Referans kodu zorunludur.", "error")
                    return render_form()

                sponsor_doc = app.db.users.find_one({"referral_code": sponsor_code})
                if not sponsor_doc:
                    flash("Geçerli bir referans kodu giriniz.", "error")
                    return render_form()

                sponsor_info = {
                    "name": sponsor_doc.get("name", ""),
                    "referral_code": sponsor_doc.get("referral_code"),
                }

                placement_parent_id, placement_position = find_binary_slot(app, sponsor_doc)
                if not placement_parent_id or not placement_position:
                    flash("Bu referans kodu için uygun yer bulunamadı. Lütfen farklı bir referans kodu deneyin.", "error")
                    return render_form()

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

            if placement_parent_id and placement_position:
                app.db.users.update_one(
                    {"_id": placement_parent_id},
                    {"$set": {f"{placement_position}_child_id": result.inserted_id}},
                )

            session["user_id"] = str(result.inserted_id)
            flash(f"Kayıt işlemi tamamlandı. Referans kodunuz: {referral_code}", "success")
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
        referral_code = g.user.get("referral_code")
        referral_link = None
        if referral_code:
            base_url = request.url_root.rstrip("/")
            referral_link = f"{base_url}{url_for('register')}?sponsor={referral_code}"

        def simplify_member(member_id):
            if not member_id:
                return None
            try:
                query_id = member_id if isinstance(member_id, ObjectId) else ObjectId(member_id)
            except Exception:
                return None
            doc = app.db.users.find_one(
                {"_id": query_id},
                {"name": 1, "referral_code": 1}
            )
            if not doc:
                return None
            return {
                "id": str(doc["_id"]),
                "name": doc.get("name", ""),
                "referral_code": doc.get("referral_code"),
            }

        left_member = simplify_member(g.user.get("left_child_id"))
        right_member = simplify_member(g.user.get("right_child_id"))

        return render_template(
            "dashboard.html",
            referral_code=referral_code,
            referral_link=referral_link,
            left_member=left_member,
            right_member=right_member,
        )

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            identifier = request.form.get("identifier", "").strip()
            password = request.form.get("password", "")
            next_url = request.args.get("next") or request.form.get("next") or url_for("index")

            user = resolve_user_by_identifier(app, identifier)
            if not user or not check_password_hash(user["password_hash"], password):
                flash("Kimlik bilgileri veya şifre hatalı.", "error")
                return render_template("auth/login.html", identifier=identifier, next=next_url)

            session["user_id"] = str(user["_id"])
            flash("Tekrar hoş geldiniz!", "success")
            return redirect(next_url)

        next_url = request.args.get("next", "")
        return render_template("auth/login.html", next=next_url, identifier="")

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

        if request.method == "POST":
            order_doc = {
                "user_id": g.user["_id"],
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
            }

            app.db.orders.insert_one(order_doc)
            session.pop("cart", None)
            flash("Siparişiniz alındı! Teşekkür ederiz.", "success")
            return redirect(url_for("orders"))

        return render_template("checkout.html", cart_items=cart_items, cart_total=cart_total)

    @app.route("/orders")
    @login_required
    def orders():
        user_orders = list(
            app.db.orders.find({"user_id": g.user["_id"]}).sort("created_at", -1)
        )
        return render_template("orders.html", orders=user_orders)


def generate_referral_code(app: Flask) -> str:
    """Her kullanıcı için benzersiz referans kodu üret."""
    prefix = "TR"
    characters = string.digits
    for _ in range(50):
        digits_count = random.choice([8, 9])
        suffix = "".join(random.choices(characters, k=digits_count))
        code = f"{prefix}{suffix}"
        if not app.db.users.find_one({"referral_code": code}):
            return code
    raise RuntimeError("Referans kodu oluşturulamadı. Lütfen tekrar deneyin.")


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
    """E-posta, telefon veya referans kodu ile kullanıcıyı bul."""
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
