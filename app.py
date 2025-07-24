from flask import Flask, render_template, request, redirect, session
from pymongo import MongoClient
from bson.objectid import ObjectId
import re
import config
import math

app = Flask(__name__)
app.secret_key = 'clave_secreta'

# Conexión a MongoDB Atlas
client = MongoClient(config.MONGO_URI)
db = client['MigrationData']  # Cambia según tu DB real
usuarios = db['usuarios']
collection = db['Stock']  # Tu colección Stock

@app.route('/')
def index():
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def login():
    user = request.form['usuario']
    pwd = request.form['password']
    user_found = usuarios.find_one({'usuario': user, 'password': pwd})
    if user_found:
        session['usuario'] = user
        return redirect('/inventario')
    return 'Usuario o contraseña incorrectos'

@app.route('/inventario')
def inventario():
    busqueda = request.args.get('q', '')  # Obtener texto de búsqueda
    page = request.args.get('page', 1, type=int)  # Página actual, default 1
    per_page = 10  # Cantidad de productos por página

    filtro = {}
    if busqueda:
        regex = re.compile(re.escape(busqueda), re.IGNORECASE)
        filtro = {
            "$or": [
                {"Description": regex},
                {"LOT": regex},
                {"Product Number": regex}
            ]
        }

    total_items = collection.count_documents(filtro)  # total productos que coinciden
    total_paginas = math.ceil(total_items / per_page)

    productos_cursor = collection.find(filtro).skip((page - 1) * per_page).limit(per_page)
    productos = list(productos_cursor)

    return render_template(
        'inventario.html',
        productos=productos,
        busqueda=busqueda,
        page=page,
        total_paginas=total_paginas
    )

@app.route('/logout')
def logout():
    session.pop('usuario', None)
    return redirect('/')

@app.route('/agregar', methods=['GET', 'POST'])
def agregar():
    if 'usuario' not in session:
        return redirect('/')

    if request.method == 'POST':
        nuevo_producto = {
            "Description": request.form['description'],
            "LOT": request.form['lot'],
            "ListNumber": request.form['list_number'],
            "Product Number": request.form['product_number'],
            "Description b": request.form['description_b'],
            "Product Type": request.form['product_type'],
            "Located": request.form['located'],
            "Income": int(request.form['income']),
            "Spent": int(request.form['spent']),
            "STOCK": float(request.form['stock']),
            "STATUS": request.form.get('status') == 'on'
        }
        collection.insert_one(nuevo_producto)
        return redirect('/inventario')

    return render_template('agregar.html')

@app.route('/editar/<id>', methods=['GET', 'POST'])
def editar(id):
    if 'usuario' not in session:
        return redirect('/')

    producto = collection.find_one({'_id': ObjectId(id)})
    if not producto:
        return 'Producto no encontrado'

    if request.method == 'POST':
        try:
            # Obtener valores de formulario
            income_original = int(request.form['income'])
            add = int(request.form.get('add', 0))
            lower = int(request.form.get('lower', 0))
            income_actualizado = income_original + add - lower

            datos_actualizados = {
                "Description": request.form['description'],
                "LOT": request.form['lot'],
                "ListNumber": request.form['list_number'],
                "Product Number": request.form['product_number'],
                "Description b": request.form['description_b'],
                "Product Type": request.form['product_type'],
                "Located": request.form['located'],
                "Income": income_actualizado,
                "Spent": int(request.form['spent']),
                "STOCK": float(request.form['stock']),
                "STATUS": request.form.get('status') == 'on'
            }

            collection.update_one({'_id': ObjectId(id)}, {'$set': datos_actualizados})
            return redirect('/inventario')
        except ValueError:
            return "Error en los datos ingresados"

    return render_template('editar.html', producto=producto)



@app.route('/eliminar/<id>')
def eliminar(id):
    if 'usuario' not in session:
        return redirect('/')

    collection.delete_one({'_id': ObjectId(id)})
    return redirect('/inventario')

if __name__ == "__main__":
    app.run(debug=True)
