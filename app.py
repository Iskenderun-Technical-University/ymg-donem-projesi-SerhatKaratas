from flask_cors import CORS
from models import *
from flask_jwt_extended import JWTManager, create_access_token, jwt_required
from initialize_db import createApp, createDB
from flask import request, jsonify
import datetime


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


if __name__ == "__main__":
    app.run()
