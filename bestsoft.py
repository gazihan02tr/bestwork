"""
BestSoft Admin Panel Module
Modern, secure and feature-rich administration interface
"""

import os
from datetime import datetime
from functools import wraps
from typing import Optional

from bson import ObjectId
from flask import (
    Blueprint,
    Flask,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename
from PIL import Image


# Create Blueprint
bestsoft_bp = Blueprint('bestsoft_bp', __name__, url_prefix='/bestsoft')


# Configuration
UPLOAD_FOLDERS = {
    'slider': 'static/uploads/slider',
    'certificates': 'static/uploads/certificates',
    'branding': 'static/uploads/branding',
}

ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'gif', 'webp'}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB


def init_bestsoft(app: Flask) -> None:
    """Initialize BestSoft module with Flask app"""
    # Create upload directories
    for folder in UPLOAD_FOLDERS.values():
        path = os.path.join(app.root_path, folder)
        os.makedirs(path, exist_ok=True)
    
    # Register blueprint
    app.register_blueprint(bestsoft_bp)
    
    # Add context processors
    @app.context_processor
    def inject_site_info():
        if hasattr(app, 'db'):
            site_info = app.db.site_settings.find_one() or {}
            return {'site_info': site_info}
        return {'site_info': {}}


# Decorators
def login_required(f):
    """Require admin login"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'bestsoft_admin' not in session:
            flash('Bu sayfayı görüntülemek için giriş yapmalısınız.', 'error')
            return redirect(url_for('bestsoft_bp.login'))
        return f(*args, **kwargs)
    return decorated_function


def allowed_file(filename: str) -> bool:
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def save_uploaded_image(file, folder: str, max_width: int = 1920) -> Optional[str]:
    """Save and optimize uploaded image"""
    if not file or not allowed_file(file.filename):
        return None
    
    try:
        # Generate unique filename
        filename = secure_filename(file.filename)
        name, ext = os.path.splitext(filename)
        unique_filename = f"{name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}{ext}"
        
        # Get upload path
        upload_path = os.path.join(
            os.path.dirname(__file__),
            UPLOAD_FOLDERS[folder],
            unique_filename
        )
        
        # Save and optimize image
        image = Image.open(file)
        
        # Resize if too large
        if image.width > max_width:
            ratio = max_width / image.width
            new_height = int(image.height * ratio)
            image = image.resize((max_width, new_height), Image.LANCZOS)
        
        # Convert RGBA to RGB if needed
        if image.mode == 'RGBA':
            bg = Image.new('RGB', image.size, (255, 255, 255))
            bg.paste(image, mask=image.split()[3])
            image = bg
        
        # Save optimized image
        image.save(upload_path, quality=85, optimize=True)
        
        return unique_filename
    
    except Exception as e:
        print(f"Error saving image: {e}")
        return None


# =====================
# Authentication Routes
# =====================

@bestsoft_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Admin login page"""
    from flask import current_app
    
    if 'bestsoft_admin' in session:
        return redirect(url_for('bestsoft_bp.dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        # Get admin from database
        app = current_app
        admin = app.db.admins.find_one({'username': username})
        
        if admin and check_password_hash(admin.get('password', ''), password):
            session['bestsoft_admin'] = str(admin['_id'])
            session['username'] = username
            flash('Başarıyla giriş yaptınız!', 'success')
            return redirect(url_for('bestsoft_bp.dashboard'))
        else:
            flash('Kullanıcı adı veya şifre hatalı!', 'error')
    
    return render_template('bestsoft/login.html')


@bestsoft_bp.route('/logout', methods=['GET', 'POST'])
def logout():
    """Admin logout"""
    session.pop('bestsoft_admin', None)
    session.pop('username', None)
    flash('Başarıyla çıkış yaptınız.', 'success')
    return redirect(url_for('bestsoft_bp.login'))


# =====================
# Dashboard
# =====================

@bestsoft_bp.route('/dashboard')
@login_required
def dashboard():
    """Main dashboard"""
    from flask import current_app
    app = current_app
    db = app.db
    
    # Get statistics
    stats = {
        'total_users': db.users.count_documents({}),
        'new_users_today': db.users.count_documents({
            'created_at': {'$gte': datetime.now().replace(hour=0, minute=0, second=0)}
        }),
        'active_orders': db.orders.count_documents({'status': {'$in': ['pending', 'processing']}}),
        'completed_today': db.orders.count_documents({
            'status': 'completed',
            'completed_at': {'$gte': datetime.now().replace(hour=0, minute=0, second=0)}
        }),
        'total_revenue': 0,  # Calculate from orders
        'revenue_today': 0,
        'unread_messages': db.contact_messages.count_documents({'read': False}),
        'total_messages': db.contact_messages.count_documents({}),
    }
    
    # Calculate revenue
    orders = list(db.orders.find({'status': 'completed'}))
    stats['total_revenue'] = sum(order.get('total', 0) for order in orders)
    
    today_orders = [o for o in orders if o.get('completed_at', datetime(1970, 1, 1)) >= datetime.now().replace(hour=0, minute=0, second=0)]
    stats['revenue_today'] = sum(order.get('total', 0) for order in today_orders)
    
    # Get recent activities
    recent_activities = []
    
    # Recent orders
    for order in db.orders.find().sort('created_at', -1).limit(5):
        recent_activities.append({
            'type': 'order',
            'title': f"Yeni Sipariş #{str(order['_id'])[:8]}",
            'description': f"{order.get('user_name', 'Kullanıcı')} tarafından",
            'time': order.get('created_at', datetime.now()).strftime('%d.%m.%Y %H:%M') if order.get('created_at') else ''
        })
    
    # Recent users
    for user in db.users.find().sort('created_at', -1).limit(3):
        recent_activities.append({
            'type': 'user',
            'title': 'Yeni Üye Kaydı',
            'description': f"{user.get('name', 'Yeni Kullanıcı')} sisteme katıldı",
            'time': user.get('created_at', datetime.now()).strftime('%d.%m.%Y %H:%M') if user.get('created_at') else ''
        })
    
    # Recent messages
    for msg in db.contact_messages.find().sort('created_at', -1).limit(2):
        recent_activities.append({
            'type': 'message',
            'title': 'Yeni Mesaj',
            'description': f"{msg.get('name', 'Bilinmeyen')} - {msg.get('subject', 'Konu yok')}",
            'time': msg.get('created_at', datetime.now()).strftime('%d.%m.%Y %H:%M') if msg.get('created_at') else ''
        })
    
    # Sort by time
    recent_activities.sort(key=lambda x: x.get('time', ''), reverse=True)
    
    # System info
    system_info = {
        'cpu': '15',
        'memory': '42',
    }
    
    db_info = {
        'total_records': sum([
            db.users.count_documents({}),
            db.orders.count_documents({}),
            db.products.count_documents({}),
        ]),
        'size': '24.5',
        'last_backup': '2 saat önce',
    }
    
    return render_template(
        'bestsoft/dashboard.html',
        stats=stats,
        recent_activities=recent_activities,
        system_info=system_info,
        db_info=db_info
    )


# =====================
# Slider Management
# =====================

@bestsoft_bp.route('/slider', methods=['GET', 'POST'])
@login_required
def slider():
    """Slider management"""
    from flask import current_app
    app = current_app
    db = app.db
    
    if request.method == 'POST':
        # Handle slider upload
        title = request.form.get('title')
        description = request.form.get('description')
        button_text = request.form.get('button_text')
        button_link = request.form.get('button_link')
        order = int(request.form.get('order', 0))
        active = request.form.get('active') == '1'
        
        image_file = request.files.get('image')
        if image_file:
            filename = save_uploaded_image(image_file, 'slider', max_width=1920)
            if filename:
                slider_data = {
                    'title': title,
                    'description': description,
                    'button_text': button_text,
                    'button_link': button_link,
                    'image': filename,
                    'order': order,
                    'active': active,
                    'created_at': datetime.now()
                }
                db.sliders.insert_one(slider_data)
                flash('Slider başarıyla eklendi!', 'success')
            else:
                flash('Görsel yüklenirken hata oluştu!', 'error')
        else:
            flash('Lütfen bir görsel seçin!', 'error')
        
        return redirect(url_for('bestsoft_bp.slider'))
    
    # Get all sliders
    sliders = list(db.sliders.find().sort('order', 1))
    
    return render_template('bestsoft/slider.html', sliders=sliders)


@bestsoft_bp.route('/slider/toggle/<slider_id>')
@login_required
def slider_toggle(slider_id):
    """Toggle slider status"""
    from flask import current_app
    app = current_app
    slider = app.db.sliders.find_one({'_id': ObjectId(slider_id)})
    
    if slider:
        app.db.sliders.update_one(
            {'_id': ObjectId(slider_id)},
            {'$set': {'active': not slider.get('active', False)}}
        )
        flash('Slider durumu güncellendi!', 'success')
    
    return redirect(url_for('bestsoft_bp.slider'))


@bestsoft_bp.route('/slider/delete/<slider_id>')
@login_required
def slider_delete(slider_id):
    """Delete slider"""
    from flask import current_app
    app = current_app
    slider = app.db.sliders.find_one({'_id': ObjectId(slider_id)})
    
    if slider:
        # Delete image file
        if slider.get('image'):
            image_path = os.path.join(
                os.path.dirname(__file__),
                UPLOAD_FOLDERS['slider'],
                slider['image']
            )
            if os.path.exists(image_path):
                os.remove(image_path)
        
        app.db.sliders.delete_one({'_id': ObjectId(slider_id)})
        flash('Slider silindi!', 'success')
    
    return redirect(url_for('bestsoft_bp.slider'))


# =====================
# Certificates
# =====================

@bestsoft_bp.route('/certificates', methods=['GET', 'POST'])
@login_required
def certificates():
    """Certificate management"""
    from flask import current_app
    app = current_app
    db = app.db
    
    if request.method == 'POST':
        title = request.form.get('title')
        issuer = request.form.get('issuer')
        description = request.form.get('description')
        date_str = request.form.get('date')
        
        cert_date = None
        if date_str:
            try:
                cert_date = datetime.strptime(date_str, '%Y-%m-%d')
            except:
                pass
        
        image_file = request.files.get('image')
        if image_file:
            filename = save_uploaded_image(image_file, 'certificates', max_width=1200)
            if filename:
                cert_data = {
                    'title': title,
                    'issuer': issuer,
                    'description': description,
                    'date': cert_date,
                    'image': filename,
                    'created_at': datetime.now()
                }
                db.certificates.insert_one(cert_data)
                flash('Sertifika başarıyla eklendi!', 'success')
            else:
                flash('Görsel yüklenirken hata oluştu!', 'error')
        else:
            flash('Lütfen bir görsel seçin!', 'error')
        
        return redirect(url_for('bestsoft_bp.certificates'))
    
    certificates_list = list(db.certificates.find().sort('created_at', -1))
    
    return render_template('bestsoft/certificates.html', certificates=certificates_list)


@bestsoft_bp.route('/certificates/delete/<cert_id>')
@login_required
def certificate_delete(cert_id):
    """Delete certificate"""
    from flask import current_app
    app = current_app
    cert = app.db.certificates.find_one({'_id': ObjectId(cert_id)})
    
    if cert:
        # Delete image file
        if cert.get('image'):
            image_path = os.path.join(
                os.path.dirname(__file__),
                UPLOAD_FOLDERS['certificates'],
                cert['image']
            )
            if os.path.exists(image_path):
                os.remove(image_path)
        
        app.db.certificates.delete_one({'_id': ObjectId(cert_id)})
        flash('Sertifika silindi!', 'success')
    
    return redirect(url_for('bestsoft_bp.certificates'))


# =====================
# Announcements
# =====================

@bestsoft_bp.route('/announcements', methods=['GET', 'POST'])
@login_required
def announcements():
    """Announcement management"""
    from flask import current_app
    app = current_app
    db = app.db
    
    if request.method == 'POST':
        title = request.form.get('title')
        message = request.form.get('message')
        priority = request.form.get('priority', 'medium')
        active = request.form.get('active') == '1'
        expire_date_str = request.form.get('expire_date')
        target = request.form.get('target', 'all')
        
        expire_date = None
        if expire_date_str:
            try:
                expire_date = datetime.strptime(expire_date_str, '%Y-%m-%d')
            except:
                pass
        
        announcement_data = {
            'title': title,
            'message': message,
            'priority': priority,
            'active': active,
            'expire_date': expire_date,
            'target_users': target,
            'created_at': datetime.now()
        }
        
        db.announcements.insert_one(announcement_data)
        flash('Duyuru başarıyla oluşturuldu!', 'success')
        
        return redirect(url_for('bestsoft_bp.announcements'))
    
    announcements_list = list(db.announcements.find().sort('created_at', -1))
    
    return render_template('bestsoft/announcements.html', announcements=announcements_list)


@bestsoft_bp.route('/announcements/toggle/<announcement_id>')
@login_required
def announcement_toggle(announcement_id):
    """Toggle announcement status"""
    from flask import current_app
    app = current_app
    announcement = app.db.announcements.find_one({'_id': ObjectId(announcement_id)})
    
    if announcement:
        app.db.announcements.update_one(
            {'_id': ObjectId(announcement_id)},
            {'$set': {'active': not announcement.get('active', False)}}
        )
        flash('Duyuru durumu güncellendi!', 'success')
    
    return redirect(url_for('bestsoft_bp.announcements'))


@bestsoft_bp.route('/announcements/delete/<announcement_id>')
@login_required
def announcement_delete(announcement_id):
    """Delete announcement"""
    from flask import current_app
    app = current_app
    app.db.announcements.delete_one({'_id': ObjectId(announcement_id)})
    flash('Duyuru silindi!', 'success')
    return redirect(url_for('bestsoft_bp.announcements'))


# =====================
# Site Settings
# =====================

@bestsoft_bp.route('/site-info', methods=['GET', 'POST'])
@login_required
def site_info():
    """Site settings"""
    from flask import current_app
    app = current_app
    db = app.db
    
    if request.method == 'POST':
        settings_data = {
            # General
            'site_name': request.form.get('site_name'),
            'site_slogan': request.form.get('site_slogan'),
            'site_description': request.form.get('site_description'),
            'maintenance_mode': request.form.get('maintenance_mode') == '1',
            'registration_enabled': request.form.get('registration_enabled') == '1',
            
            # Contact
            'contact_email': request.form.get('contact_email'),
            'contact_phone': request.form.get('contact_phone'),
            'contact_address': request.form.get('contact_address'),
            'working_hours': request.form.get('working_hours'),
            'whatsapp': request.form.get('whatsapp'),
            'fax': request.form.get('fax'),
            
            # Social Media
            'facebook': request.form.get('facebook'),
            'instagram': request.form.get('instagram'),
            'twitter': request.form.get('twitter'),
            'linkedin': request.form.get('linkedin'),
            'youtube': request.form.get('youtube'),
            'github': request.form.get('github'),
            
            # SEO
            'meta_title': request.form.get('meta_title'),
            'meta_description': request.form.get('meta_description'),
            'meta_keywords': request.form.get('meta_keywords'),
            'google_analytics': request.form.get('google_analytics'),
            'google_verification': request.form.get('google_verification'),
            
            # Branding
            'primary_color': request.form.get('primary_color'),
            'secondary_color': request.form.get('secondary_color'),
            'accent_color': request.form.get('accent_color'),
            'success_color': request.form.get('success_color'),
            
            'updated_at': datetime.now()
        }
        
        # Handle logo upload
        logo_file = request.files.get('logo')
        if logo_file:
            filename = save_uploaded_image(logo_file, 'branding', max_width=500)
            if filename:
                settings_data['logo'] = f"/static/uploads/branding/{filename}"
        
        # Handle favicon upload
        favicon_file = request.files.get('favicon')
        if favicon_file:
            filename = save_uploaded_image(favicon_file, 'branding', max_width=64)
            if filename:
                settings_data['favicon'] = f"/static/uploads/branding/{filename}"
        
        # Update or insert
        db.site_settings.update_one(
            {},
            {'$set': settings_data},
            upsert=True
        )
        
        flash('Ayarlar başarıyla kaydedildi!', 'success')
        return redirect(url_for('bestsoft_bp.site_info'))
    
    site_info_data = db.site_settings.find_one() or {}
    
    return render_template('bestsoft/site_info.html', site_info=site_info_data)


# =====================
# Contact Messages
# =====================

@bestsoft_bp.route('/messages')
@login_required
def contact_messages():
    """Contact messages"""
    from flask import current_app
    app = current_app
    db = app.db
    
    filter_type = request.args.get('filter', 'all')
    
    query = {}
    if filter_type == 'unread':
        query['read'] = False
    elif filter_type == 'read':
        query['read'] = True
    elif filter_type == 'replied':
        query['replied'] = True
    
    messages = list(db.contact_messages.find(query).sort('created_at', -1))
    
    # Calculate stats
    stats = {
        'total': db.contact_messages.count_documents({}),
        'unread': db.contact_messages.count_documents({'read': False}),
        'replied': db.contact_messages.count_documents({'replied': True}),
        'today': db.contact_messages.count_documents({
            'created_at': {'$gte': datetime.now().replace(hour=0, minute=0, second=0)}
        })
    }
    
    return render_template(
        'bestsoft/contact_page.html',
        messages=messages,
        stats=stats
    )


@bestsoft_bp.route('/messages/read/<message_id>')
@login_required
def message_read(message_id):
    """Mark message as read"""
    from flask import current_app
    app = current_app
    app.db.contact_messages.update_one(
        {'_id': ObjectId(message_id)},
        {'$set': {'read': True}}
    )
    flash('Mesaj okundu olarak işaretlendi!', 'success')
    return redirect(url_for('bestsoft_bp.contact_messages'))


@bestsoft_bp.route('/messages/delete/<message_id>')
@login_required
def message_delete(message_id):
    """Delete message"""
    from flask import current_app
    app = current_app
    app.db.contact_messages.delete_one({'_id': ObjectId(message_id)})
    flash('Mesaj silindi!', 'success')
    return redirect(url_for('bestsoft_bp.contact_messages'))


@bestsoft_bp.route('/messages/reply', methods=['POST'])
@login_required
def message_reply():
    """Reply to message"""
    from flask import current_app
    # Here you would implement email sending logic
    message_id = request.form.get('message_id')
    
    app = current_app
    app.db.contact_messages.update_one(
        {'_id': ObjectId(message_id)},
        {'$set': {'replied': True, 'replied_at': datetime.now()}}
    )
    
    flash('Mesaj başarıyla yanıtlandı!', 'success')
    return redirect(url_for('bestsoft_bp.contact_messages'))


# =====================
# Additional Pages
# =====================

# Default e-commerce band items
DEFAULT_BAND_ITEMS = [
    {
        "key": 1,
        "icon": "local_shipping",
        "title": "Ücretsiz Kargo",
        "description": "500 TL ve üzeri tüm siparişlerinizde",
    },
    {
        "key": 2,
        "icon": "verified_user",
        "title": "Memnuniyet Garantisi",
        "description": "180 gün içinde koşulsuz iade",
    },
    {
        "key": 3,
        "icon": "support_agent",
        "title": "7/24 Destek",
        "description": "Uzman ekibimiz her zaman yanınızda",
    },
]


@bestsoft_bp.route('/eticaret-bandi', methods=['GET', 'POST'])
@login_required
def eticaret_bandi():
    """E-commerce band settings"""
    from flask import current_app
    db = current_app.db
    
    # Load band items from database or use defaults
    band_items = []
    for defaults in DEFAULT_BAND_ITEMS:
        idx = defaults["key"]
        stored = db.eticaret_band.find_one({"key": idx})
        if stored:
            band_items.append({
                "key": idx,
                "icon": stored.get("icon", defaults["icon"]),
                "title": stored.get("title", defaults["title"]),
                "description": stored.get("description", defaults["description"]),
            })
        else:
            band_items.append(defaults.copy())
    
    if request.method == 'POST':
        updates = 0
        for item in band_items:
            idx = item["key"]
            icon = request.form.get(f"item_{idx}_icon", "").strip() or item["icon"]
            title = request.form.get(f"item_{idx}_title", "").strip() or item["title"]
            description = request.form.get(f"item_{idx}_description", "").strip() or item["description"]
            
            db.eticaret_band.update_one(
                {"key": idx},
                {"$set": {
                    "key": idx,
                    "icon": icon,
                    "title": title,
                    "description": description,
                    "updated_at": datetime.now(),
                    "updated_by": session.get('bestsoft_admin')
                }},
                upsert=True
            )
            
            # Update local copy for display
            item["icon"] = icon
            item["title"] = title
            item["description"] = description
            updates += 1
        
        if updates:
            flash('E-Ticaret bandı başarıyla güncellendi!', 'success')
        return redirect(url_for('bestsoft_bp.eticaret_bandi'))
    
    return render_template('bestsoft/eticaret_bandi.html', band_items=band_items)


@bestsoft_bp.route('/corporate-page')
@login_required
def corporate_page():
    """Corporate page editor"""
    return render_template('bestsoft/corporate_page.html')


# =====================
# Utility Functions
# =====================

def create_default_admin(app: Flask, username: str = 'admin', password: str = 'admin123'):
    """Create default admin user"""
    if not app.db.admins.find_one({'username': username}):
        admin_data = {
            'username': username,
            'password': generate_password_hash(password),
            'email': 'admin@bestsoft.com',
            'created_at': datetime.now()
        }
        app.db.admins.insert_one(admin_data)
        print(f"✅ Default admin created: {username} / {password}")
