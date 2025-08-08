from flask import Flask, render_template, request, redirect, session, flash, url_for, jsonify
from pymongo import MongoClient
from bson.objectid import ObjectId
import config
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'clave_secreta'

# Conexión a MongoDB Atlas
client = MongoClient(config.MONGO_URI)
db = client['MigrationData']
usuarios = db['usuarios']
collection = db['Stock']

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
    if 'usuario' not in session:
        return redirect('/')

    busqueda = request.args.get('q', '')
    page = int(request.args.get('page', 1))
    por_pagina = request.args.get('por_pagina', None)

    try:
        por_pagina = int(por_pagina)
    except (TypeError, ValueError):
        por_pagina = 16  # default

    filtro = {}
    if busqueda:
        filtro = {
            "$or": [
                {"LOT": {"$regex": busqueda, "$options": "i"}},
                {"Description": {"$regex": busqueda, "$options": "i"}},
                {"ListNumber": {"$regex": busqueda, "$options": "i"}},
                {"Product_Type": {"$regex": busqueda, "$options": "i"}},
            ]
        }

    total_productos = collection.count_documents(filtro)
    total_paginas = (total_productos + por_pagina - 1) // por_pagina

    productos_cursor = collection.find(filtro).skip((page - 1) * por_pagina).limit(por_pagina)
    productos = list(productos_cursor)

    for prod in productos:
        if 'Date_In' in prod:
            try:
                fecha = datetime.strptime(prod['Date_In'], '%Y-%m-%d')
                prod['Date_In'] = fecha.strftime('%m/%d/%Y')
            except Exception:
                pass

    return render_template(
        'inventario.html',
        productos=productos,
        busqueda=busqueda,
        page=page,
        total_paginas=total_paginas,
        por_pagina=por_pagina,
        active_tab='inventario'
    )



@app.route('/Tarimas')
def tarimas():
    return render_template('tarimas.html', active_tab='Tarimas')



@app.route('/logout')
def logout():
    session.pop('usuario', None)
    return redirect('/')

@app.route('/agregar', methods=['GET', 'POST'])
def agregar():
    if 'usuario' not in session:
        return redirect('/')

    if request.method == 'POST':
        try:
            nuevo_producto = {
                "LOT": request.form['LOT'],
                "ListNumber": request.form['list_number'],
                "Description": request.form['description'],
                "Product_Type": request.form['product_type'],
                "Located": request.form['located'],
                "Date_In": request.form['Date_In'],
                "QTY_Vol": float(request.form['QTY_Vol']) if request.form['QTY_Vol'] else 0,
                "Unit": request.form['Unit'],
                "STOCK": float(request.form['stock']) if request.form['stock'] else 0,
                "Qty_Per_Box": float(request.form['Qty_Per_Box']) if request.form['Qty_Per_Box'] else 0,
                "Box_Available": float(request.form['Box_Available']) if request.form['Box_Available'] else 0,
                "Maximum_Storage_Days": float(request.form['Maximum_Storage_Days']) if request.form['Maximum_Storage_Days'] else 0,
                "Due_Date": request.form['Due_Date'] if request.form['Due_Date'] else None,
                "Days_Available": int(request.form['Days_Available']) if request.form['Days_Available'] else 0,
                "Status": request.form['Status'],
                "Note": request.form['Note'],
                "STATUS": True
            }
            collection.insert_one(nuevo_producto)
            return redirect('/inventario')

        except (KeyError, ValueError) as e:
            flash(f"Error en los datos del formulario: {e}", "danger")
            return render_template('agregar.html')

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
            stock_original = float(request.form.get('stock', 0))
            add = float(request.form.get('add', 0))
            lower = float(request.form.get('lower', 0))
            stock_actualizado = round(stock_original + add - lower, 2)

            # Aceptar formato m/d/Y (por Flatpickr) o Y-m-d (navegador)
            try:
                fecha_in = datetime.strptime(request.form['Date_In'], '%m/%d/%Y')
            except ValueError:
                try:
                    fecha_in = datetime.strptime(request.form['Date_In'], '%Y-%m-%d')
                except ValueError:
                    flash("Error: Formato de fecha inválido", "danger")
                    return redirect(url_for('editar', id=id))

            if fecha_in.date() > datetime.now().date():
                flash("Error: La fecha no puede ser futura.", "danger")
                return redirect(url_for('editar', id=id))

            date_in_str = fecha_in.strftime('%Y-%m-%d')

            qty_vol = producto.get('QTY_Vol', 0)

            datos_actualizados = {
                "LOT": request.form['LOT'],
                "ListNumber": request.form['list_number'],
                "Description": request.form['description'],
                "Product_Type": request.form['product_type'],
                "Located": request.form['located'],
                "Date_In": date_in_str,
                "QTY_Vol": qty_vol,
                "Unit": request.form['Unit'],
                "STOCK": stock_actualizado,
                "Qty_Per_Box": float(request.form['Qty_Per_Box']),
                "Box_Available": float(request.form['Box_Available']),
                "Maximum _Storage (Days)": float(request.form['Maximum_Storage_Days']),
                "STATUS": True  # O mantener el valor anterior si no usas checkbox
            }

            collection.update_one({'_id': ObjectId(id)}, {'$set': datos_actualizados})
            flash("Producto actualizado correctamente.", "success")
            return redirect('/inventario')

        except (ValueError, KeyError) as e:
            flash(f"Error en los datos ingresados: {e}", "danger")
            return redirect(url_for('editar', id=id))

    # Convertir fecha para mostrarla en el input si existe
    if producto.get('Date_In'):
        try:
            fecha = datetime.strptime(producto['Date_In'], '%Y-%m-%d')
            producto['Date_In'] = fecha.strftime('%Y-%m-%d')  # Para <input type="date">
        except ValueError:
            pass

    return render_template('editar.html', producto=producto)

@app.route('/equipos')
def equipos():
    return render_template('equipos.html', active_tab='equipos')



        



@app.route('/eliminar/<id>',methods=['POST'])
def eliminar(id):
    if 'usuario' not in session:
        return redirect('/')

    collection.delete_one({'_id': ObjectId(id)})
    return redirect('/inventario')

@app.route('/buscar_productos')
def buscar_productos():
    if 'usuario' not in session:
        return jsonify([])

    q = request.args.get('q', '')
    filtro = {}
    if q:
        filtro = {
            "$or": [
                {"LOT": {"$regex": q, "$options": "i"}},
                {"Description": {"$regex": q, "$options": "i"}},
                {"ListNumber": {"$regex": q, "$options": "i"}},
                {"Product_Type": {"$regex": q, "$options": "i"}},
            ]
        }

    productos = list(collection.find(filtro).limit(50))

    for prod in productos:
        prod['_id'] = str(prod['_id'])
        if 'Date_In' in prod:
            try:
                fecha = datetime.strptime(prod['Date_In'], '%Y-%m-%d')
                prod['Date_In'] = fecha.strftime('%m/%d/%Y')
            except Exception:
                pass

    return jsonify(productos)

if __name__ == "__main__":
    app.run(debug=True)
