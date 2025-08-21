from flask import Flask, render_template, request, redirect, session, flash, url_for, jsonify
from pymongo import MongoClient
from bson.objectid import ObjectId
import config
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'clave_secreta'

# ------------------------------
# Conexión a MongoDB Atlas
# ------------------------------

client = MongoClient(config.MONGO_URI)
db = client['MigrationData']
usuarios = db['usuarios']
collection = db['Stock']
equipos_collection = db['Equipos']
reservas_collection = db["Reservas"]

# ------------------------------

@app.route('/')
def index():
    return render_template('login.html')

# ------------------------------

@app.route('/login', methods=['POST'])
def login():
    user = request.form['usuario']
    pwd = request.form['password']
    user_found = usuarios.find_one({'usuario': user, 'password': pwd})
    if user_found:
        session['usuario'] = user
        return redirect('/inventario')
    return 'Usuario o contraseña incorrectos'

# ------------------------------

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

# ------------------------------


@app.route('/logout')
def logout():
    session.pop('usuario', None)
    return redirect('/')

# ------------------------------



@app.route('/agregar', methods=['GET', 'POST'])
def agregar():
    if 'usuario' not in session:
        return redirect('/')

    if request.method == 'POST':
        try:
            # Obtener y convertir Days_Available de forma segura
            days_available = int(request.form['Days_Available']) if request.form['Days_Available'] else 0

            # Calcular Status en backend (seguridad)
            status = "Expirado" if days_available < 0 else "Vigente"


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


# ------------------------------



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

            # Procesar fecha Date_In
            try:
                fecha_in = datetime.strptime(request.form['Date_In'], '%m/%d/%Y')
            except ValueError:
                try:
                    fecha_in = datetime.strptime(request.form['Date_In'], '%Y-%m-%d')
                except ValueError:
                    flash("Error: Formato de fecha inválido en Date_In", "danger")
                    return redirect(url_for('editar', id=id))

            if fecha_in.date() > datetime.now().date():
                flash("Error: La fecha de entrada no puede ser futura.", "danger")
                return redirect(url_for('editar', id=id))

            date_in_str = fecha_in.strftime('%Y-%m-%d')

            # Procesar fecha Due_Date
            due_date = None
            if request.form.get('Due_Date'):
                try:
                    due_date = datetime.strptime(request.form['Due_Date'], '%Y-%m-%d')
                except ValueError:
                    try:
                        due_date = datetime.strptime(request.form['Due_Date'], '%m/%d/%Y')
                    except ValueError:
                        flash("Error: Formato de fecha inválido en Due_Date", "danger")
                        return redirect(url_for('editar', id=id))

            # Calcular Days_Available
            days_available = None
            status_text = ""  # Campo para Status
            if due_date:
                days_available = (due_date.date() - fecha_in.date()).days
                if days_available > 0:
                    status_text = "Vigente"
                else:
                    status_text = "Expirado"


            qty_per_box = float(request.form['Qty_Per_Box']) if request.form['Qty_Per_Box'] else 0
            box_available = round(stock_actualizado / qty_per_box, 1) if qty_per_box > 0 else 0

            qty_vol = float(request.form.get('QTY_Vol', 0))

            

            datos_actualizados = {
                "LOT": request.form['LOT'],
                "ListNumber": request.form['list_number'],
                "Description": request.form['description'],
                "Product_Type": request.form['product_type'],
                "Located": request.form['located'],
                "Date_In": date_in_str,
                "Due_Date": due_date.strftime('%Y-%m-%d') if due_date else "",
                "Days_Available": days_available,
                "QTY_Vol": qty_vol,
                "Unit": request.form['Unit'],
                "STOCK": stock_actualizado,
                "Qty_Per_Box": qty_per_box,
                "Box_Available": box_available,
                "Maximum _Storage (Days)": float(request.form['Maximum_Storage_Days']),
                "Status": status_text,
                "Note": request.form['Note']
            }

            collection.update_one({'_id': ObjectId(id)}, {'$set': datos_actualizados})
            flash("Producto actualizado correctamente.", "success")
            return redirect('/inventario')

        except (ValueError, KeyError) as e:
            flash(f"Error en los datos ingresados: {e}", "danger")
            return redirect(url_for('editar', id=id))

    # Preparar formato de fechas para el formulario
    if producto.get('Date_In'):
        try:
            fecha = datetime.strptime(producto['Date_In'], '%Y-%m-%d')
            producto['Date_In'] = fecha.strftime('%Y-%m-%d')
        except ValueError:
            pass

    if producto.get('Due_Date'):
        try:
            fecha_due = datetime.strptime(producto['Due_Date'], '%Y-%m-%d')
            producto['Due_Date'] = fecha_due.strftime('%Y-%m-%d')
        except ValueError:
            pass

    return render_template('editar.html', producto=producto)

# ------------------------------


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


# ------------------------------
# Mostrar descripcion
# ------------------------------

@app.route("/get_product_info")
def get_product_info():
    list_number = request.args.get("ListNumber")
    
    if not list_number:
        return jsonify({}), 400
    
    # Buscar en MongoDB
    product = collection.find_one({"ListNumber": list_number}, {"_id": 0, "Description": 1, "Product_Type": 1, "Unit": 1, "Qty_Per_Box": 1})
    
    if product:
        return jsonify(product)
    else:
        return jsonify({})


# ------------------------------
# Mostrar equipos
# ------------------------------
@app.route("/equipos")
def listar_equipos():
    equipos = list(equipos_collection.find())
    return render_template("equipos.html", equipos=equipos)

# ------------------------------
# Mostrar vista Tarimas
# ------------------------------

@app.route('/Tarimas')
def tarimas():
    return render_template('Tarimas.html', active_tab='Tarimas')



# ------------------------------
# Mostrar vista Calendario
# ------------------------------
@app.route("/calendario")
def calendario():
    return render_template("calendario.html")


@app.route("/api/reservas")
def api_reservas():
    reservas = list(reservas_collection.find())
    eventos = []
    for r in reservas:
        eventos.append({
            "title": "Reservado",
            "start": r["fecha_inicio"].isoformat(),
            "end": r["fecha_fin"].isoformat()
        })
    return jsonify(eventos)




# ------------------------------
if __name__ == "__main__":
    app.run(debug=True)
