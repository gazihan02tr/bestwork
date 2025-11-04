# Bestwork E-Ticaret Uygulaması

## Kurulum

1. Depoyu klonladıktan sonra bir sanal ortam oluşturup etkinleştirin (önerilir).
2. Bağımlılıkları kurun:

   ```bash
   pip install -r requirements.txt
   ```

3. `.env` dosyası oluşturun:

   ```bash
   cp .env.example .env
   ```

4. `.env` içindeki değerleri güncelleyin:
   - `SECRET_KEY`: Flask oturumları için güçlü bir değer.
    - `MONGO_URI`: MongoDB bağlantı adresiniz (örnek: `mongodb://localhost:27017/bestwork`).
    - `TCKN_SECRET_KEY`: T.C. kimlik numarası verilerini şifrelemek için rastgele güçlü bir anahtar (ör. `openssl rand -base64 32`).

5. Uygulamayı başlatın:

   ```bash
   flask run --debug
   ```

## Notlar

- `TCKN_SECRET_KEY` tanımlı değilse uygulama geçici bir anahtar üretir; bu, kayıtlı kimlik numaralarının bir sonraki başlatmada çözülemeyeceği anlamına gelir. Üretimde mutlaka kalıcı bir anahtar kullanın.
- Formdaki şehir ve ilçe listeleri otomatik olarak Türkiye'deki 81 ili ve ilçelerini içerir.
