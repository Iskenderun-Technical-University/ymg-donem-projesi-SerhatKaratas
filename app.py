from flask_cors import CORS
from models import *
from flask_jwt_extended import JWTManager, create_access_token, jwt_required
from initialize_db import createApp, createDB
from flask import request, jsonify
import datetime
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from itsdangerous import URLSafeTimedSerializer



app = createApp()
CORS(app)
createDB()
app.config['SECRET_KEY'] = 'mysecretkey'
jwt = JWTManager(app)


def delete_category(category):
    # Alt kategorileri sil
    for child in category.children:
        delete_category(child)

    # Kategoriye ait ürünleri deaktive et
    deactivate_products(category.products)

    # Kategoriyi sil
    db.session.delete(category)


def deactivate_products(products):
    for product in products:
        product.category_id = None
        product.is_active = False
        db.session.add(product)


def get_products_by_category(category):
    products = []
    if not category.children:
        products = category.products
    else:
        for child in category.children:
            products.extend(get_products_by_category(child))
    return products


@app.route('/category/<int:category_id>/products', methods=['GET'])
def get_product_by_category(category_id):            #seçilen kategoriye ait tüm ürünleri döndürür.

    category = Category.query.get(category_id)
    if not category:
        return jsonify({'message': 'Kategori bulunamadı'}), 404

    product_list = get_products_by_category(category)

    products = []
    for product in product_list:
        products.append({
            'id': product.id,
            'name': product.name,
            'price': product.price,
            'stock': product.stock,
            'description': product.description
        })

    return jsonify({'products': products}), 200


@app.route('/category/<int:category_id>', methods=['DELETE'])
def delete_category_api(category_id):
    category = Category.query.get(category_id)
    if not category:
        return jsonify({'message': 'Kategori bulunamadı'}), 404

    delete_category(category)
    db.session.commit()

    return jsonify({'message': 'Kategori başarıyla silindi'}), 200



@app.route('/login', methods=['POST'])        # Pozitif
def login():      # kullanıcı kimlik bilgileriyle oturum açmayı sağlar
    content = request.json
    password, email = content["password"], content["email"]
    user = UserTable.query.filter_by(email=email).first()   # Veritabanında kullanıcı arama
    if user is None or not user.check_password(password):   # E-posta veya parola yanlış ise hata yanıtı döndür
        return jsonify({'status': 'false', 'description': 'Email or Password Wrong'})
    # JWT oluşturma
    expires = datetime.timedelta(1.0)      # 24 saat sürecek bir zaman aralığı nesnesi oluşturur
    token = create_access_token(identity=email, expires_delta=expires)
    # Token veritabanında kaydedilir veya güncellenir
    token_record = Token.query.filter_by(user_id=user.id).first()
    if token_record is None:
        token_record = Token(token=token, user_id=user.id)
        db.session.add(token_record)
    else:
        token_record.token = token
    db.session.commit()

    return jsonify({'token': token, 'status': 'true', 'description': 'Login Successfully', 'is_admin': user.is_admin})

@app.route('/logout', methods=['GET'])
@jwt_required()
def logout():
    try:
        token = None
        if 'Authorization' in request.headers:
            # Bearer tokeni al
            token = request.headers['Authorization'].split()[1]
        else:
            # Token yoksa hata döndür
            return jsonify({'error': 'Token not found'}), 401
        token_obj = Token.query.filter_by(token=token).first()
        db.session.delete(token_obj)
        db.session.commit()
        return jsonify({'status': 'true', 'description': 'Logout Successfully'}), 200
    except Exception as e:
        print("Veritabanı hatası:", e), 500


@app.route('/reset_password', methods=['POST'])
def reset_password():                         # Bu api şuan çalışmaz. Doğru smtp sağlayıcı bilgileri verirse çalışıyor.
    email = request.json['email']
    user = UserTable.query.filter_by(email=email).first()
    if not user:
        return jsonify({'message': 'Geçersiz e-posta adresi'}), 404
    print(user)
    print(email)
    # Şifre sıfırlama token'ını oluşturma
    token = generate_password_token(email)
    print(token)
    login = "example@examplemailprovider"     # Mail gönderme işlemi yapacağın posta ismi.
    recipients_emails = email
    subject = 'Parola yenile'
    header = 'Merhaba, parolanızı sıfırlamak için aşağıdaki bağlantıya tıklayın'
    body = '<a class="btn btn-primary" href="https://google.com/{}" role="button">TIKLA</a>'.format(token)   # Parola yenileme sayfasına yönlendirir(Bu bir örnektir)
    print(body)
    msg = MIMEMultipart('alternative')

    html_content = '''
    <html>
        <head>
            <style>
                h2 {{
                    margin: 0;
                    padding: 20px;
                    color: #ffffff;
                    background: #4b9fc5;
                }}
                .btn {{
                    display: block;
                    width: 100%;
                    background-color: #4b9fc5;
                    color: #ffffff;
                    text-decoration: none;
                    padding: 10px 20px;
                    border-radius: 5px;
                    text-align: center;
                }}
                .btn:hover {{
                    background-color: #3579a8;
                }}
            </style>
        </head>
        <body>
            <h2>{}</h2>
            <br>
            {}
        </body>
    </html>
    '''.format(header, body)

    part = MIMEText(html_content, 'html')

    msg.attach(part)

    msg['Subject'] = subject
    msg['From'] = login
    msg['To'] = recipients_emails

    smtp_host = 'smtp.example.com'      # SMTP saglayıcını yaz.
    smtp_port = 587
    password = "oldukca gizli bir parola"              # Gönderme işlemi yapacağın mailin parolasını yaz.

    with smtplib.SMTP(smtp_host, smtp_port) as server:
        server.starttls()
        server.login(login, password)
        server.send_message(msg)
        print("Mail başarıyla gönderildi.")

    return jsonify({'message': 'Şifre sıfırlama e-postası gönderildi'}), 200

@app.route('/reset_password/<token>', methods=['POST'])
def reset_password_confirm(token):
    email = verify_password_token(token)
    if not email:
        return jsonify({'message': 'Geçersiz veya süresi dolmuş token'}), 400

    new_password = request.json['new_password']
    user = UserTable.query.filter_by(email=email).first()
    if not user:
        return jsonify({'message': 'Geçersiz e-posta adresi'}), 404

    user.password = new_password
    db.session.commit()

    return jsonify({'message': 'Parola başarıyla güncellendi'}), 200

def generate_password_token(email):
    serializer = URLSafeTimedSerializer('mysecretkey')  # Gizli anahtarınızı buraya girin

    # Token'ı oluşturma
    token = serializer.dumps(email)

    return token



# Token'ı doğrulama işlemini gerçekleştiren fonksiyon
def verify_password_token(token):
    serializer = URLSafeTimedSerializer('mysecretkey')  # Gizli anahtarınızı buraya girin

    try:
        # Token'ı doğrulama ve e-posta adresini geri döndürme
        email = serializer.loads(token)
        return email
    except:
        # Token doğrulama hatası durumunda None döndürme
        return None


if __name__ == "__main__":
    app.run()
