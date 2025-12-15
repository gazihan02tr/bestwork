import hashlib
import os
from datetime import datetime
from typing import Any, Callable, Dict, Optional
from uuid import uuid4

from bson import ObjectId
from bson.errors import InvalidId
from cryptography.fernet import InvalidToken
from flask import (
    Flask,
    abort,
    flash,
    redirect,
    render_template,
    request,
    send_from_directory,
    session,
    url_for,
)
from PIL import Image
from werkzeug.utils import secure_filename


SiteTextSetter = Callable[[Flask, str, str, str, Optional[Dict[str, Any]]], None]
SiteTextGetter = Callable[[Flask, str, str], Optional[str]]
DatetimeFormatter = Callable[[Any], str]
CipherFactory = Callable[[], Any]


def register_bestsoft_routes(
    app: Flask,
    *,
    dist_dir: str,
    default_locale: str,
    translations: Dict[str, Dict[str, str]],
    set_site_text_value: SiteTextSetter,
    get_site_text_value: SiteTextGetter,
    format_datetime_for_display: DatetimeFormatter,
    get_identity_cipher: CipherFactory,
) -> None:
    """
    Yönetim paneline özel BestSoft rotalarını kaydet.
    """
    slider_upload_dir = os.path.join(app.root_path, "static", "uploads", "slider")
    os.makedirs(slider_upload_dir, exist_ok=True)
    slider_allowed_extensions = {"jpg", "jpeg", "png", "gif", "webp"}
    slider_max_images = 10
    slider_settings_locale = "default"

    def _allowed_slider_file(filename: str) -> bool:
        return "." in filename and filename.rsplit(".", 1)[1].lower() in slider_allowed_extensions

    def _save_slider_image(upload) -> Optional[str]:
        if not upload or not upload.filename:
            return None
        if not _allowed_slider_file(upload.filename):
            return None
        upload.stream.seek(0)
        try:
            image = Image.open(upload.stream)
        except Exception:
            return None

        export_image = image
        if export_image.mode not in ("RGB", "RGBA"):
            export_image = export_image.convert("RGB")

        dest_name = f"{uuid4().hex}.webp"
        dest_path = os.path.join(slider_upload_dir, dest_name)
        try:
            export_image.save(dest_path, format="WEBP", quality=90, method=6)
        except Exception:
            return None
        return dest_name

    def _clear_bestsoft_session() -> None:
        session.pop("management_entry_id", None)
        session.pop("management_user_id", None)

    def _require_management_session(next_endpoint: str):
        if not session.get("management_entry_id"):
            flash("Lütfen önce BestSoft hesabınızla giriş yapın.", "warning")
            return redirect(url_for("bestsoft_login", next=url_for(next_endpoint)))
        return None

    @app.route("/bestsoft", methods=["GET", "POST"])
    def bestsoft_login():
        next_url = request.args.get("next") or request.form.get("next") or url_for("bestsoft_landing")
        identifier = request.args.get("identifier", "")

        if request.method == "POST":
            identifier = request.form.get("identifier", "").strip()
            password = request.form.get("password", "")

            if not identifier or not password:
                flash("Kullanıcı ID ve şifre zorunludur.", "warning")
                return render_template("bestsoft/login.html", identifier=identifier, next=next_url)

            user_hash = hashlib.sha256(identifier.encode("utf-8")).hexdigest()
            record = app.db.managements.find_one({"user_id_hash": user_hash})
            if not record:
                flash("Geçersiz kullanıcı ID veya şifre.", "error")
                return render_template("bestsoft/login.html", identifier=identifier, next=next_url)

            cipher = get_identity_cipher()
            try:
                stored_user_id = cipher.decrypt(record["user_id_encrypted"].encode("utf-8")).decode("utf-8")
                stored_password = cipher.decrypt(record["password_encrypted"].encode("utf-8")).decode("utf-8")
            except (InvalidToken, KeyError, AttributeError, ValueError):
                flash("Yönetici bilgileri çözümlenemedi. Lütfen tekrar deneyin.", "error")
                return render_template("bestsoft/login.html", identifier=identifier, next=next_url)

            if stored_user_id != identifier or stored_password != password:
                flash("Geçersiz kullanıcı ID veya şifre.", "error")
                return render_template("bestsoft/login.html", identifier=identifier, next=next_url)

            session["management_entry_id"] = str(record["_id"])
            session["management_user_id"] = stored_user_id
            flash("BestSoft portalına hoş geldiniz.", "success")
            return redirect(next_url)

        return render_template("bestsoft/login.html", identifier=identifier, next=next_url)

    @app.route("/bestwork")
    @app.route("/bestwork/")
    def bestsoft_landing():
        if not session.get("management_entry_id"):
            flash("Lütfen önce BestSoft hesabınızla giriş yapın.", "warning")
            return redirect(url_for("bestsoft_login"))

        index_path = os.path.join(dist_dir, "index.html")
        if os.path.isfile(index_path):
            return redirect(url_for("bestsoft_dist", filename="index.html"))

        return render_template("bestsoft/index.html")

    @app.route("/bestwork/announcements", methods=["GET", "POST"])
    def bestsoft_announcements():
        redirect_response = _require_management_session("bestsoft_announcements")
        if redirect_response:
            return redirect_response

        promo_locale = "default"

        if request.method == "POST":
            form_type = request.form.get("form_type") or "announcement"
            if form_type == "promo_text":
                content = request.form.get("promo_content", "").strip()
                if not content:
                    return redirect(url_for("bestsoft_announcements"))
                set_site_text_value(
                    app,
                    "promo_text",
                    promo_locale,
                    content,
                    {"updated_by": session.get("management_user_id")},
                )
                return redirect(url_for("bestsoft_announcements"))

            content = request.form.get("content", "").strip()
            if not content:
                return redirect(url_for("bestsoft_announcements"))
            now = datetime.utcnow()
            app.db.bestsoft_announcements.insert_one(
                {
                    "content": content,
                    "created_at": now,
                    "updated_at": now,
                    "created_by": session.get("management_user_id"),
                }
            )
            return redirect(url_for("bestsoft_announcements"))

        announcements_cursor = app.db.bestsoft_announcements.find().sort("created_at", -1)
        announcements = [
            {
                "id": str(doc["_id"]),
                "content": doc.get("content", ""),
                "created_at_display": format_datetime_for_display(doc.get("created_at")),
                "updated_at_display": format_datetime_for_display(doc.get("updated_at")),
            }
            for doc in announcements_cursor
        ]
        promo_text_value = get_site_text_value(app, "promo_text", promo_locale)
        if not promo_text_value:
            promo_text_value = translations.get(default_locale, {}).get("promo_text")
        return render_template(
            "bestsoft/announcements.html",
            announcements=announcements,
            promo_text_value=promo_text_value,
        )

    @app.route("/bestwork/announcements/<announcement_id>/update", methods=["POST"])
    def update_announcement(announcement_id: str):
        redirect_response = _require_management_session("bestsoft_announcements")
        if redirect_response:
            return redirect_response

        content = request.form.get("content", "").strip()
        if not content:
            return redirect(url_for("bestsoft_announcements"))

        try:
            announcement_oid = ObjectId(announcement_id)
        except (InvalidId, TypeError):
            flash("Geçersiz duyuru kaydı.", "error")
            return redirect(url_for("bestsoft_announcements"))

        app.db.bestsoft_announcements.update_one(
            {"_id": announcement_oid},
            {"$set": {"content": content, "updated_at": datetime.utcnow()}},
        )
        return redirect(url_for("bestsoft_announcements"))

    @app.route("/bestwork/announcements/<announcement_id>/delete", methods=["POST"])
    def delete_announcement(announcement_id: str):
        redirect_response = _require_management_session("bestsoft_announcements")
        if redirect_response:
            return redirect_response

        try:
            announcement_oid = ObjectId(announcement_id)
        except (InvalidId, TypeError):
            flash("Geçersiz duyuru kaydı.", "error")
            return redirect(url_for("bestsoft_announcements"))

        app.db.bestsoft_announcements.delete_one({"_id": announcement_oid})
        return redirect(url_for("bestsoft_announcements"))

    @app.route("/bestwork/slider", methods=["GET", "POST"])
    def bestsoft_slider():
        redirect_response = _require_management_session("bestsoft_slider")
        if redirect_response:
            return redirect_response

        current_count = app.db.bestsoft_slider_images.count_documents({})

        if request.method == "POST":
            form_type = request.form.get("form_type", "upload").strip().lower() or "upload"

            if form_type == "transition":
                raw_seconds = (request.form.get("transition_seconds") or "").replace(",", ".")
                try:
                    seconds = float(raw_seconds)
                except (TypeError, ValueError):
                    seconds = 6.5
                seconds = max(1.0, min(30.0, seconds))
                set_site_text_value(
                    app,
                    "slider_transition_seconds",
                    slider_settings_locale,
                    f"{seconds:.2f}",
                    {"updated_by": session.get("management_user_id")},
                )
                flash("Geçiş süresi güncellendi.", "success")
                return redirect(url_for("bestsoft_slider"))

            if form_type == "ordering":
                image_ids = request.form.getlist("image_ids[]")
                order_values = request.form.getlist("orders[]")
                updated_count = 0
                for raw_id, raw_order in zip(image_ids, order_values):
                    try:
                        image_oid = ObjectId(raw_id)
                    except (InvalidId, TypeError):
                        continue
                    try:
                        display_order = int(raw_order)
                    except (TypeError, ValueError):
                        continue
                    app.db.bestsoft_slider_images.update_one(
                        {"_id": image_oid},
                        {"$set": {"display_order": display_order}},
                    )
                    updated_count += 1
                if updated_count:
                    flash("Slider sıralaması güncellendi.", "success")
                else:
                    flash("Güncellenecek geçerli bir kayıt bulunamadı.", "warning")
                return redirect(url_for("bestsoft_slider"))

            if current_count >= slider_max_images:
                flash(f"En fazla {slider_max_images} adet slider görseli yükleyebilirsiniz.", "warning")
                return redirect(url_for("bestsoft_slider"))

            upload = request.files.get("image")
            if not upload or upload.filename.strip() == "":
                flash("Lütfen yüklemek için bir görsel seçin.", "warning")
                return redirect(url_for("bestsoft_slider"))

            saved_name = _save_slider_image(upload)
            if not saved_name:
                allowed_text = ", ".join(sorted(slider_allowed_extensions))
                flash(f"Görsel yüklenemedi. Desteklenen formatlar: {allowed_text}", "error")
                return redirect(url_for("bestsoft_slider"))

            highest_order_doc = app.db.bestsoft_slider_images.find_one(
                {"display_order": {"$ne": None}}, sort=[("display_order", -1)]
            )
            highest_order = 0
            if highest_order_doc:
                try:
                    highest_order = int(highest_order_doc.get("display_order") or 0)
                except (TypeError, ValueError):
                    highest_order = 0

            app.db.bestsoft_slider_images.insert_one(
                {
                    "filename": saved_name,
                    "original_name": secure_filename(upload.filename) or saved_name,
                    "created_at": datetime.utcnow(),
                    "uploaded_by": session.get("management_user_id"),
                    "display_order": highest_order + 1,
                }
            )
            flash("Slider görseli eklendi.", "success")
            return redirect(url_for("bestsoft_slider"))

        slider_cursor = app.db.bestsoft_slider_images.find().sort([("display_order", 1), ("created_at", -1)])
        slider_images = []
        for index, doc in enumerate(slider_cursor, start=1):
            display_order = doc.get("display_order")
            if display_order is None:
                display_order = index
                app.db.bestsoft_slider_images.update_one(
                    {"_id": doc["_id"]},
                    {"$set": {"display_order": display_order}},
                )
            slider_images.append(
                {
                    "id": str(doc["_id"]),
                    "url": url_for("static", filename=f"uploads/slider/{doc['filename']}"),
                    "original_name": doc.get("original_name") or doc.get("filename"),
                    "created_at_display": format_datetime_for_display(doc.get("created_at")),
                    "display_order": display_order,
                }
            )

        transition_value = get_site_text_value(app, "slider_transition_seconds", slider_settings_locale) or "6.5"
        try:
            transition_seconds = float(transition_value)
        except (TypeError, ValueError):
            transition_seconds = 6.5

        return render_template(
            "bestsoft/slider.html",
            slider_images=slider_images,
            current_count=current_count,
            max_images=slider_max_images,
            transition_seconds=transition_seconds,
        )

    @app.route("/bestwork/slider/<image_id>/delete", methods=["POST"])
    def delete_slider_image(image_id: str):
        redirect_response = _require_management_session("bestsoft_slider")
        if redirect_response:
            return redirect_response

        try:
            image_oid = ObjectId(image_id)
        except (InvalidId, TypeError):
            flash("Geçersiz slider kaydı.", "error")
            return redirect(url_for("bestsoft_slider"))

        doc = app.db.bestsoft_slider_images.find_one({"_id": image_oid})
        if not doc:
            flash("Slider kaydı bulunamadı.", "error")
            return redirect(url_for("bestsoft_slider"))

        app.db.bestsoft_slider_images.delete_one({"_id": image_oid})
        stored_filename = doc.get("filename")
        if stored_filename:
            file_path = os.path.join(slider_upload_dir, stored_filename)
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except OSError:
                    pass
        flash("Slider görseli silindi.", "success")
        return redirect(url_for("bestsoft_slider"))

    @app.route("/bestwork/<path:filename>")
    def bestsoft_dist(filename: str):
        if not session.get("management_entry_id"):
            abort(403)

        safe_path = os.path.normpath(filename)
        if safe_path.startswith(".."):
            abort(404)

        target_path = os.path.join(dist_dir, safe_path)
        if not os.path.isfile(target_path):
            abort(404)

        return send_from_directory(dist_dir, safe_path)

    @app.route("/bestsoft/logout")
    def bestsoft_logout():
        _clear_bestsoft_session()
        flash("BestSoft oturumunuz sonlandırıldı.", "info")
        return redirect(url_for("bestsoft_login"))

    @app.route("/managements/setup", methods=["GET", "POST"])
    def management_setup():
        form_state = {"user_id": ""}

        if request.method == "POST":
            user_id = request.form.get("user_id", "").strip()
            password = request.form.get("password", "")
            form_state["user_id"] = user_id

            if not user_id or not password:
                flash("Kullanıcı ID ve şifre zorunludur.", "warning")
                return render_template("managements_setup.html", form_state=form_state)

            user_id_hash = hashlib.sha256(user_id.encode("utf-8")).hexdigest()
            existing = app.db.managements.find_one({"user_id_hash": user_id_hash})
            if existing:
                flash("Bu kullanıcı ID'si için zaten bir yönetici kaydı mevcut.", "warning")
                return render_template("managements_setup.html", form_state=form_state)

            cipher = get_identity_cipher()
            encrypted_user_id = cipher.encrypt(user_id.encode("utf-8")).decode("utf-8")
            encrypted_password = cipher.encrypt(password.encode("utf-8")).decode("utf-8")

            app.db.managements.insert_one(
                {
                    "user_id_hash": user_id_hash,
                    "user_id_encrypted": encrypted_user_id,
                    "password_encrypted": encrypted_password,
                    "created_at": datetime.utcnow(),
                }
            )

            flash("Yönetici kaydı oluşturuldu.", "success")
            return redirect(url_for("management_setup"))

        return render_template("managements_setup.html", form_state=form_state)
