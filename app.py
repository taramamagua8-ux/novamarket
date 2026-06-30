from flask import Flask, render_template, request, redirect, url_for, session
import os
import secrets
import sqlite3
import smtplib
from decimal import Decimal, InvalidOperation
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from werkzeug.utils import secure_filename
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("NOVARKET_SECRET_KEY") or secrets.token_hex(32)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SQLITE_PATH = os.environ.get(
    "SQLITE_PATH", os.path.join(BASE_DIR, "instance", "novamarket.db")
)


class SQLiteCursor:
    """Cursor compatible con las consultas originales escritas para MySQL."""

    def __init__(self, dictionary=False):
        os.makedirs(os.path.dirname(SQLITE_PATH), exist_ok=True)
        self.connection = sqlite3.connect(SQLITE_PATH, timeout=30)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.cursor = self.connection.cursor()
        self.dictionary = dictionary

    def execute(self, sql, params=()):
        sql = sql.replace("%s", "?")
        params = tuple(float(value) if isinstance(value, Decimal) else value for value in (params or ()))
        self.cursor.execute(sql, params)
        self.connection.commit()
        return self

    def fetchone(self):
        row = self.cursor.fetchone()
        if row is None:
            return None
        return dict(row) if self.dictionary else tuple(row)

    def fetchall(self):
        rows = self.cursor.fetchall()
        return [dict(row) for row in rows] if self.dictionary else [tuple(row) for row in rows]

    @property
    def lastrowid(self):
        return self.cursor.lastrowid

    def close(self):
        self.cursor.close()
        self.connection.close()


class SQLiteConnectionFacade:
    def cursor(self, **kwargs):
        return SQLiteCursor(dictionary=kwargs.get("dictionary", False))

    def commit(self):
        return None


conexion = SQLiteConnectionFacade()


def conectar_bd():
    return conexion


def asegurar_conexion():
    return conexion


def cursor_bd(**kwargs):
    return SQLiteCursor(dictionary=kwargs.get("dictionary", False))


SCHEMA = """
CREATE TABLE IF NOT EXISTS clientes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario TEXT NOT NULL,
    correo TEXT NOT NULL UNIQUE,
    password TEXT NOT NULL,
    telefono TEXT DEFAULT '',
    sexo TEXT DEFAULT '',
    cp TEXT DEFAULT '',
    calle TEXT DEFAULT '',
    num_ext TEXT DEFAULT '',
    num_int TEXT DEFAULT '',
    colonia_barrio TEXT DEFAULT '',
    foto TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS vendedores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    password TEXT NOT NULL,
    telefono TEXT DEFAULT '',
    sexo TEXT DEFAULT '',
    cp TEXT DEFAULT '',
    calle TEXT DEFAULT '',
    num_ext TEXT DEFAULT '',
    num_int TEXT DEFAULT '',
    comprobante TEXT DEFAULT '',
    estado TEXT NOT NULL DEFAULT 'pendiente'
);
CREATE TABLE IF NOT EXISTS local (
    id_local INTEGER PRIMARY KEY AUTOINCREMENT,
    num_local TEXT NOT NULL UNIQUE,
    Telefono TEXT DEFAULT '',
    tipo_local TEXT DEFAULT '',
    tipo_producto TEXT DEFAULT '',
    nombre_local TEXT NOT NULL,
    horario TEXT DEFAULT '',
    encargado TEXT DEFAULT '',
    vendedor_id INTEGER NOT NULL UNIQUE,
    FOREIGN KEY (vendedor_id) REFERENCES vendedores(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS producto (
    id_producto INTEGER PRIMARY KEY AUTOINCREMENT,
    precio NUMERIC NOT NULL,
    Marca TEXT NOT NULL,
    Peso TEXT DEFAULT '',
    "Tamaño" TEXT DEFAULT '',
    vendedor_id INTEGER NOT NULL,
    FOREIGN KEY (vendedor_id) REFERENCES vendedores(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS promociones (
    id_promociones INTEGER PRIMARY KEY AUTOINCREMENT,
    Descuento NUMERIC NOT NULL,
    Precio_total NUMERIC NOT NULL,
    id_producto INTEGER NOT NULL,
    FOREIGN KEY (id_producto) REFERENCES producto(id_producto) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS venta (
    id_venta INTEGER PRIMARY KEY AUTOINCREMENT,
    id_producto INTEGER NOT NULL,
    cantidad INTEGER NOT NULL CHECK (cantidad > 0),
    cliente_id INTEGER,
    FOREIGN KEY (id_producto) REFERENCES producto(id_producto) ON DELETE CASCADE,
    FOREIGN KEY (cliente_id) REFERENCES clientes(id) ON DELETE CASCADE
);
"""


def inicializar_bd():
    os.makedirs(os.path.dirname(SQLITE_PATH), exist_ok=True)
    db = sqlite3.connect(SQLITE_PATH)
    db.execute("PRAGMA foreign_keys = ON")
    db.executescript(SCHEMA)
    if not db.execute("SELECT 1 FROM vendedores LIMIT 1").fetchone():
        password = generate_password_hash("demo123")
        vendedores = [
            ("Vendedora Demo", "vendedor@demo.local", password, "5550000001", "Otro", "56334", "Pasillo Central", "1", "", "", "aprobado"),
            ("Dulcería Estrella", "dulceria@demo.local", password, "5550000002", "Otro", "56334", "Pasillo Dulces", "3", "", "", "aprobado"),
            ("Papelería Nova", "papeleria@demo.local", password, "5550000003", "Otro", "56334", "Pasillo Escolar", "5", "", "", "aprobado"),
        ]
        db.executemany("""
            INSERT INTO vendedores
            (usuario,email,password,telefono,sexo,cp,calle,num_ext,num_int,comprobante,estado)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """, vendedores)
        locales = [
            ("001", "5550000001", "Abarrotes", "Productos variados", "Abarrotes La Canasta", "08:00 - 19:00", "Vendedora Demo", 1),
            ("002", "5550000002", "Dulcería", "Dulces y botanas", "Dulcería La Estrella", "09:00 - 20:00", "Dulcería Estrella", 2),
            ("003", "5550000003", "Papelería", "Útiles escolares", "Papelería Nova", "09:00 - 18:00", "Papelería Nova", 3),
        ]
        db.executemany("""
            INSERT INTO local
            (num_local,Telefono,tipo_local,tipo_producto,nombre_local,horario,encargado,vendedor_id)
            VALUES (?,?,?,?,?,?,?,?)
        """, locales)
        productos = [
            (28.00, "Arroz premium", "1 kg", "Mediano", 1),
            (24.50, "Frijol negro", "1 kg", "Mediano", 1),
            (19.00, "Refresco de cola", "600 ml", "Individual", 1),
            (65.00, "Caja de chocolates", "250 g", "Grande", 2),
            (18.00, "Paleta surtida", "10 piezas", "Bolsa", 2),
            (42.00, "Botana familiar", "300 g", "Grande", 2),
            (35.00, "Cuaderno profesional", "100 hojas", "Profesional", 3),
            (12.00, "Juego de lápices", "5 piezas", "Escolar", 3),
            (29.00, "Colores de madera", "12 piezas", "Caja", 3),
        ]
        db.executemany("INSERT INTO producto (precio,Marca,Peso,\"Tamaño\",vendedor_id) VALUES (?,?,?,?,?)", productos)
        promociones = [
            (15, 23.80, 1),
            (10, 22.05, 2),
            (20, 52.00, 4),
            (25, 31.50, 6),
            (10, 31.50, 7),
        ]
        db.executemany("INSERT INTO promociones (Descuento,Precio_total,id_producto) VALUES (?,?,?)", promociones)
        db.execute("""
            INSERT INTO clientes
            (usuario,correo,password,telefono,sexo,cp,calle,num_ext,num_int,colonia_barrio)
            VALUES (?,?,?,?,?,?,?,?,?,?)
        """, ("Cliente Demo", "cliente@demo.local", password, "5550000010", "Otro", "56334", "Calle Demo", "1", "", "Centro"))
    db.commit()
    db.close()


def password_valido(guardado, enviado):
    try:
        return check_password_hash(guardado, enviado)
    except (ValueError, TypeError):
        return secrets.compare_digest(str(guardado), str(enviado))


inicializar_bd()


IMAGENES_LOCAL = (
    (("pollo", "polleria", "pollería"), "img/polleria.webp"),
    (("dulce", "dulceria", "dulcería"), "img/dulceria.webp"),
    (("papel", "papeleria", "papelería"), "img/papeleriaFlor.webp"),
    (("foto", "fotografia", "fotografía"), "img/fotografias.webp"),
    (("merceria", "mercería"), "img/merceria.webp"),
    (("vela",), "img/velas.webp"),
    (("soda", "bebida", "comida"), "img/sodas.webp"),
)


def imagen_para_local(local):
    texto = " ".join(
        str(local.get(campo) or "")
        for campo in ("tipo_producto", "tipo_local", "nombre_local")
    ).lower()
    for claves, imagen in IMAGENES_LOCAL:
        if any(clave in texto for clave in claves):
            return imagen
    return "img/abarrotes.webp"


def consultar_producto(id_producto):
    cursor = cursor_bd(dictionary=True)
    cursor.execute(
        """
        SELECT pr.*, l.id_local, l.nombre_local
        FROM producto pr
        LEFT JOIN local l ON l.vendedor_id = pr.vendedor_id
        WHERE pr.id_producto=%s
        """,
        (id_producto,),
    )
    producto = cursor.fetchone()
    cursor.close()
    return producto

def consultar_locales():
    cursor = cursor_bd(dictionary=True)
    cursor.execute(
        """
        SELECT l.*, COUNT(p.id_producto) AS total_productos
        FROM local l
        LEFT JOIN producto p ON p.vendedor_id = l.vendedor_id
        GROUP BY l.id_local
        ORDER BY l.nombre_local, l.id_local
        """
    )
    locales = cursor.fetchall()
    cursor.close()
    for local in locales:
        local["imagen"] = imagen_para_local(local)
    return locales

def enviar_correo_aprobacion(destinatario):

    remitente = os.environ.get("NOVARKET_EMAIL")
    password = os.environ.get("NOVARKET_EMAIL_PASSWORD")

    if not remitente or not password:
        print("Correo de aprobación omitido: faltan NOVARKET_EMAIL y NOVARKET_EMAIL_PASSWORD")
        return False

    mensaje = MIMEMultipart()

    mensaje["From"] = remitente
    mensaje["To"] = destinatario
    mensaje["Subject"] = "Solicitud aprobada - Novarket"

    base_url = os.environ.get("RENDER_EXTERNAL_URL", request.url_root.rstrip('/'))
    cuerpo = f"""
    <html>
    <head>
    </head>
    <body style="font-family: Arial, sans-serif; background-color:#f4f4f4; padding:20px;">

        <div style="
            max-width:600px;
            margin:auto;
            background:white;
            border-radius:15px;
            overflow:hidden;
            box-shadow:0 4px 10px rgba(0,0,0,0.1);
        ">

        <div style="
            background:#bd122e;
            color:white;
            text-align:center;
            padding:25px;
        ">
            <h1>¡Solicitud Aprobada!</h1>
        </div>

        <div style="padding:30px; color:#333;">

            <h2>Hola 👋</h2>

            <p>
                Nos complace informarte que tu solicitud para convertirte
                en vendedor dentro de <strong>Novarket</strong> ha sido aprobada.
            </p>

            <p>
                A partir de este momento ya puedes iniciar sesión y comenzar
                a administrar tu local, publicar productos y realizar ventas.
            </p>

            <div style="
                text-align:center;
                margin:30px 0;
            ">
                <a href="{base_url}/login"
                   style="
                        background:#bd122e;
                        color:white;
                        padding:14px 25px;
                        text-decoration:none;
                        border-radius:8px;
                        font-weight:bold;
                   ">
                    Iniciar Sesión
                </a>
            </div>

            <p>
                Gracias por confiar en Novarket.
            </p>

            <p>
                Atentamente,<br>
                <strong>Equipo Novarket</strong>
            </p>

        </div>

        <div style="
            background:#f2f2f2;
            text-align:center;
            padding:15px;
            font-size:12px;
            color:#666;
        ">
            © 2026 Novarket - Todos los derechos reservados
        </div>

    </div>

    </body>
    </html>
    """

    mensaje.attach(MIMEText(cuerpo, "html"))
    

    try:
        servidor = smtplib.SMTP("smtp.gmail.com", 587, timeout=20)
        servidor.starttls()
        servidor.login(remitente, password)
        servidor.sendmail(remitente, destinatario, mensaje.as_string())
        servidor.quit()
        return True
    except (OSError, smtplib.SMTPException) as error:
        print("No se pudo enviar el correo de aprobación:", error)
        return False


@app.route('/')
def bienvenida():
    return render_template('pagina_bienvenida.html')


@app.route('/health')
def health():
    return {'status': 'ok'}, 200

@app.route('/logout')
def logout():
    session.clear()  # elimina toda la sesión
    return redirect(url_for('acceso'))

@app.route('/acceso')
def acceso():
    return render_template('acceso.html')

@app.route('/seleccionar_cuenta')
def seleccionar_cuenta():
    return render_template('cuenta.html')

@app.route('/pagina')
def inicio():
    return redirect(url_for('bienvenida'))

@app.route('/login', methods=['GET', 'POST'])
def login():

    mensaje = ""

    if request.method == 'POST':

        email = request.form.get('email')
        password = request.form.get('password')

        admin_email = os.environ.get('NOVARKET_ADMIN_EMAIL', 'admin@demo.local')
        admin_password = os.environ.get('NOVARKET_ADMIN_PASSWORD', 'demo123')
        if email == admin_email and secrets.compare_digest(password or '', admin_password):
            session.clear()
            session['tipo_usuario'] = 'admin'
            return redirect(url_for('admin_vendedores'))

        cursor = cursor_bd(dictionary=True)

        cursor.execute("SELECT * FROM clientes WHERE correo=%s", (email,))

        cliente = cursor.fetchone()

        if cliente and password_valido(cliente['password'], password):
            session['tipo_usuario'] = 'cliente'
            session['cliente_id'] = cliente['id']

            cursor.close()

            return redirect(url_for('menu_cliente'))

        cursor.execute("""
            SELECT * FROM vendedores
            WHERE email=%s AND estado='aprobado'
        """, (email,))

        vendedor = cursor.fetchone()

        cursor.close()

        if vendedor and password_valido(vendedor['password'], password):
            session['tipo_usuario'] = 'vendedor'
            session['vendedor_id'] = vendedor['id']
            return redirect(url_for('menu_vendedor'))

        mensaje = "Correo o contraseña incorrectos"

    return render_template(
        'login.html',
        mensaje=mensaje
    )
@app.route('/volver_menu')
def volver_menu():

    tipo = session.get('tipo_usuario')
    if tipo == 'cliente':
        return redirect(url_for('menu_cliente'))

    elif tipo == 'vendedor':
        return redirect(url_for('menu_vendedor'))

    elif tipo == 'admin':
        return redirect(url_for('admin_vendedores'))

    return redirect(url_for('inicio'))

@app.route('/pagina_invitado')
def pagina_invitado():
    return render_template('menuNovarket.html', locales=consultar_locales())


@app.route('/menu_vendedor')
def menu_vendedor():
    if session.get('tipo_usuario') != 'vendedor':
        return redirect(url_for('login'))
    return render_template('menuNovarket2.html', locales=consultar_locales())

@app.route('/productos_vendedor', methods=['GET', 'POST'])
def productos_vendedor():
    vendedor_id = session.get('vendedor_id')
    if session.get('tipo_usuario') != 'vendedor' or not vendedor_id:
        return redirect(url_for('login'))

    if request.method == 'POST':
        nombre = (request.form.get('nombre') or '').strip()
        peso = (request.form.get('peso') or '').strip()
        tamano = (request.form.get('tamano') or '').strip()
        try:
            precio = Decimal(request.form.get('precio') or '')
        except InvalidOperation:
            return "Precio inválido", 400

        if not nombre or precio <= 0:
            return "Nombre y precio son obligatorios", 400

        cursor = cursor_bd()
        cursor.execute(
            """
            INSERT INTO producto (precio, Marca, Peso, Tamaño, vendedor_id)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (precio, nombre, peso, tamano, vendedor_id),
        )
        asegurar_conexion().commit()
        cursor.close()
        return redirect(url_for('productos_vendedor'))

    cursor = cursor_bd(dictionary=True)
    cursor.execute(
        "SELECT * FROM producto WHERE vendedor_id=%s ORDER BY id_producto DESC",
        (vendedor_id,),
    )
    productos = cursor.fetchall()
    cursor.close()
    return render_template('productos_vendedor.html', productos=productos)

@app.route('/eliminar_producto/<int:id_producto>', methods=['POST'])
def eliminar_producto(id_producto):
    vendedor_id = session.get('vendedor_id')
    if session.get('tipo_usuario') != 'vendedor' or not vendedor_id:
        return redirect(url_for('login'))

    cursor = cursor_bd()
    cursor.execute(
        "DELETE FROM producto WHERE id_producto=%s AND vendedor_id=%s",
        (id_producto, vendedor_id),
    )
    asegurar_conexion().commit()
    cursor.close()
    return redirect(url_for('productos_vendedor'))

@app.route('/promociones_vendedor', methods=['GET', 'POST'])
def promociones_vendedor():
    vendedor_id = session.get('vendedor_id')
    if session.get('tipo_usuario') != 'vendedor' or not vendedor_id:
        return redirect(url_for('login'))

    if request.method == 'POST':
        id_producto = request.form.get('id_producto', type=int)
        try:
            descuento = Decimal(request.form.get('descuento') or '')
        except InvalidOperation:
            return "Datos de promoción inválidos", 400

        if not id_producto or descuento <= 0 or descuento > 100:
            return "Datos de promoción inválidos", 400

        cursor = cursor_bd()
        cursor.execute(
            "SELECT id_producto, precio FROM producto WHERE id_producto=%s AND vendedor_id=%s",
            (id_producto, vendedor_id),
        )
        producto_promocion = cursor.fetchone()
        if not producto_promocion:
            cursor.close()
            return "Producto no encontrado", 404

        precio_total = round(Decimal(str(producto_promocion[1])) * (Decimal('1') - descuento / Decimal('100')), 2)
        cursor.execute(
            """
            INSERT INTO promociones (Descuento, Precio_total, id_producto)
            VALUES (%s, %s, %s)
            """,
            (descuento, precio_total, id_producto),
        )
        asegurar_conexion().commit()
        cursor.close()
        return redirect(url_for('promociones_vendedor'))

    cursor = cursor_bd(dictionary=True)
    cursor.execute(
        "SELECT * FROM producto WHERE vendedor_id=%s ORDER BY Marca",
        (vendedor_id,),
    )
    productos = cursor.fetchall()
    cursor.execute(
        """
        SELECT p.id_promociones, p.Descuento, p.Precio_total,
               pr.id_producto, pr.Marca, pr.precio
        FROM promociones p
        JOIN producto pr ON pr.id_producto = p.id_producto
        WHERE pr.vendedor_id=%s
        ORDER BY p.id_promociones DESC
        """,
        (vendedor_id,),
    )
    promociones = cursor.fetchall()
    cursor.close()
    return render_template(
        'promociones_vendedor.html',
        productos=productos,
        promociones=promociones,
    )

@app.route('/eliminar_promocion/<int:id_promocion>', methods=['POST'])
def eliminar_promocion(id_promocion):
    vendedor_id = session.get('vendedor_id')
    if session.get('tipo_usuario') != 'vendedor' or not vendedor_id:
        return redirect(url_for('login'))

    cursor = cursor_bd()
    cursor.execute(
        """
        DELETE FROM promociones
        WHERE id_promociones=%s
          AND id_producto IN (SELECT id_producto FROM producto WHERE vendedor_id=%s)
        """,
        (id_promocion, vendedor_id),
    )
    asegurar_conexion().commit()
    cursor.close()
    return redirect(url_for('promociones_vendedor'))


@app.route('/espera', methods=['GET', 'POST'])
def espera():

    if request.method == 'POST':

        archivo = request.files.get('comprobante')

        if archivo and archivo.filename:

            carpeta = os.path.join('static', 'comprobantes')
            os.makedirs(carpeta, exist_ok=True)

            nombre_archivo = secure_filename(archivo.filename)
            archivo.save(os.path.join(carpeta, nombre_archivo))

            print("Archivo guardado:", nombre_archivo)

    return render_template('pagina_espera.html')


@app.route('/menu', methods=['GET', 'POST'])
def menu():

    if request.method == 'POST':

        nombre_usuario = request.form.get('usuario')
        correo = request.form.get('correo')
        password = request.form.get('password')
        telefono = request.form.get('telefono')
        sexo = request.form.get('sexo')
        cp = request.form.get('cp')
        calle = request.form.get('calle')
        num_ext = request.form.get('num_ext')
        num_int = request.form.get('num_int')
        colonia_barrio = request.form.get('colonia_barrio')

        if not nombre_usuario or not correo or not password:
            return "Nombre, correo y contraseña son obligatorios", 400

        cursor = cursor_bd()
        cursor.execute("SELECT id FROM clientes WHERE correo=%s", (correo,))
        if cursor.fetchone():
            cursor.close()
            return "Ese correo ya está registrado", 409

        sql = """
        INSERT INTO clientes
        (usuario, correo, password, telefono, sexo, cp, calle, num_ext, num_int, colonia_barrio)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """

        valores = (
            nombre_usuario,
            correo,
            generate_password_hash(password),
            telefono,
            sexo,
            cp,
            calle,
            num_ext,
            num_int,
            colonia_barrio
        )

        cursor.execute(sql, valores)
        cliente_id = cursor.lastrowid
        asegurar_conexion().commit()
        cursor.close()

        # Guardar que es cliente
        session['tipo_usuario'] = 'cliente'
        session['cliente_id'] = cliente_id

        return redirect(url_for('menu_cliente'))

    return redirect(url_for('menu_cliente'))


@app.route('/cuenta_usuario')
def cuenta():

    id_cliente = session.get('cliente_id')
    if not id_cliente:
        return redirect(url_for('login'))

    cursor = cursor_bd(dictionary=True)

    cursor.execute(
        "SELECT * FROM clientes WHERE id=%s",
        (id_cliente,)
    )

    cliente = cursor.fetchone()

    cursor.close()

    return render_template(
        'cuenta_usuario.html',
        cliente=cliente
    )

@app.route('/actualizar_cliente', methods=['POST'])
def actualizar_cliente():

    id_cliente = session.get('cliente_id')
    if not id_cliente:
        return redirect(url_for('login'))

    usuario = request.form['usuario']
    correo = request.form['correo']
    telefono = request.form['telefono']
    colonia_barrio = request.form.get('colonia_barrio')

    cursor = cursor_bd()

    sql = """
   UPDATE clientes
SET usuario=%s,
    correo=%s,
    telefono=%s,
    colonia_barrio=%s
WHERE id=%s
    """

    cursor.execute(
    sql,
    (
        usuario,
        correo,
        telefono,
        colonia_barrio,
        id_cliente
    )
)

    asegurar_conexion().commit()

    cursor.close()

    return redirect(url_for('cuenta'))

@app.route('/subir_foto', methods=['POST'])
def subir_foto():

    if 'cliente_id' not in session:
        return redirect(url_for('login'))

    foto = request.files.get('foto')

    if foto and foto.filename:

        carpeta = os.path.join('static', 'fotos_perfil')
        os.makedirs(carpeta, exist_ok=True)

        nombre_seguro = secure_filename(foto.filename)
        nombre_archivo = f"cliente_{session['cliente_id']}_{nombre_seguro}"

        ruta = os.path.join(carpeta, nombre_archivo)

        foto.save(ruta)

        cursor = cursor_bd()

        cursor.execute("""
            UPDATE clientes
            SET foto=%s
            WHERE id=%s
        """, (
            nombre_archivo,
            session['cliente_id']
        ))

        asegurar_conexion().commit()
        cursor.close()

    return redirect(url_for('cuenta'))

@app.route('/usuario')
def usuario():
    return local_usuario()


@app.route('/vendedor')
def vendedor():
    return redirect(url_for('productos_vendedor'))


@app.route('/mi_local')
def mi_local():

    vendedor_id = session.get('vendedor_id')
    if session.get('tipo_usuario') != 'vendedor' or not vendedor_id:
        return redirect(url_for('login'))

    cursor = cursor_bd(dictionary=True)

    cursor.execute(
        """
        SELECT * FROM local WHERE vendedor_id=%s
        """,
        (vendedor_id,)
    )

    local = cursor.fetchone()

    cursor.close()


    return render_template(
        'mi_local.html',
        local=local
    )

@app.route('/guardar_local', methods=['POST'])
def guardar_local():

    vendedor_id = session.get('vendedor_id')
    if session.get('tipo_usuario') != 'vendedor' or not vendedor_id:
        return redirect(url_for('login'))

    nombre = request.form.get('nombre')
    tipo_producto = request.form.get('tipo')
    horario = request.form.get('horario')
    encargado = request.form.get('encargado')
    telefono = request.form.get('telefono')

    cursor = cursor_bd()

    cursor.execute("""
        INSERT INTO local
            (num_local, Telefono, tipo_local, tipo_producto,
             nombre_local, horario, encargado, vendedor_id)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT(vendedor_id) DO UPDATE SET
            Telefono=excluded.Telefono,
            tipo_local=excluded.tipo_local,
            tipo_producto=excluded.tipo_producto,
            nombre_local=excluded.nombre_local,
            horario=excluded.horario,
            encargado=excluded.encargado
    """,
    (
        f"V{vendedor_id:03d}",
        telefono,
        tipo_producto,
        tipo_producto,
        nombre,
        horario,
        encargado,
        vendedor_id,
    ))

    asegurar_conexion().commit()
    cursor.close()
    return redirect(url_for('mi_local'))

@app.route('/local/<int:id_local>')
def detalle_local(id_local):
    cursor = cursor_bd(dictionary=True)
    cursor.execute("SELECT * FROM local WHERE id_local=%s", (id_local,))
    local = cursor.fetchone()

    if not local:
        cursor.close()
        return "Local no encontrado", 404

    cursor.execute(
        """
        SELECT * FROM producto
        WHERE vendedor_id=%s
        ORDER BY Marca
        """,
        (local['vendedor_id'],),
    )
    productos = cursor.fetchall()
    cursor.close()
    local["imagen"] = imagen_para_local(local)
    return render_template(
        'local_usuario.html',
        local=local,
        productos=productos,
    )

@app.route('/local-usuario')
def local_usuario():
    locales = consultar_locales()
    if not locales:
        return redirect(url_for('pagina_invitado'))
    return redirect(url_for('detalle_local', id_local=locales[0]['id_local']))


@app.route('/formulario_cliente')
def formulario_cliente():
    return render_template('formulario_cliente.html')


@app.route('/formulario_vendedor', methods=['GET', 'POST'])
def formulario_vendedor():

    if request.method == 'POST':

        usuario = request.form.get('usuario')
        email = request.form.get('email')
        password = request.form.get('password')
        telefono = request.form.get('telefono')
        sexo = request.form.get('sexo')
        cp = request.form.get('cp')
        calle = request.form.get('calle')
        num_ext = request.form.get('num_ext')
        num_int = request.form.get('num_int')

        archivo = request.files.get('comprobante')

        if not usuario or not email or not password:
            return "Nombre, correo y contraseña son obligatorios", 400

        nombre_archivo = ""

        if archivo and archivo.filename:

            carpeta = os.path.join('static', 'comprobantes')
            os.makedirs(carpeta, exist_ok=True)

            nombre_archivo = secure_filename(archivo.filename)

            archivo.save(
                os.path.join(carpeta, nombre_archivo)
            )

        cursor = cursor_bd()
        cursor.execute("SELECT id FROM vendedores WHERE email=%s", (email,))
        if cursor.fetchone():
            cursor.close()
            return "Ese correo ya está registrado", 409

        sql = """
        INSERT INTO vendedores
        (
            usuario,
            email,
            password,
            telefono,
            sexo,
            cp,
            calle,
            num_ext,
            num_int,
            comprobante,
            estado
        )
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """

        valores = (
            usuario,
            email,
            generate_password_hash(password),
            telefono,
            sexo,
            cp,
            calle,
            num_ext,
            num_int,
            nombre_archivo,
            'pendiente'
        )

        cursor.execute(sql, valores)
        asegurar_conexion().commit()
        cursor.close()

        return redirect(url_for('espera'))

    return render_template('formulario_vendedor.html')


@app.route('/menu_cliente')
def menu_cliente():
    if session.get('tipo_usuario') != 'cliente':
        return redirect(url_for('login'))
    return render_template(
    'menuNovarket3.html',
    locales=consultar_locales()
    )

@app.route('/promociones_usuario')
def promociones_usuario():
    cursor = cursor_bd(dictionary=True)
    cursor.execute(
        """
        SELECT p.id_promociones, p.Descuento, p.Precio_total,
               pr.id_producto, pr.Marca, pr.precio, l.nombre_local
        FROM promociones p
        JOIN producto pr ON pr.id_producto = p.id_producto
        LEFT JOIN local l ON l.vendedor_id = pr.vendedor_id
        ORDER BY p.id_promociones DESC
        """
    )
    promociones = cursor.fetchall()
    cursor.close()
    return render_template('promociones_usuario.html', promociones=promociones)


@app.route('/historia')
def historia():
    return render_template('historia.html')


@app.route('/carrito2')
def carrito2():
    tipo_usuario = session.get('tipo_usuario')
    if tipo_usuario not in ('cliente', 'vendedor'):
        return redirect(url_for('login'))

    cursor = cursor_bd(dictionary=True)
    if tipo_usuario == 'cliente':
        cursor.execute(
            """
        SELECT v.id_venta, v.cantidad, pr.id_producto, pr.Marca,
               pr.precio, (pr.precio * v.cantidad) AS total
        FROM venta v
        JOIN producto pr ON pr.id_producto = v.id_producto
        WHERE v.cliente_id=%s
        ORDER BY v.id_venta DESC
            """,
            (session.get('cliente_id'),),
        )
    else:
        cursor.execute(
            """
        SELECT v.id_venta, v.cantidad, pr.id_producto, pr.Marca,
               pr.precio, (pr.precio * v.cantidad) AS total
        FROM venta v
        JOIN producto pr ON pr.id_producto = v.id_producto
        WHERE pr.vendedor_id=%s
        ORDER BY v.id_venta DESC
            """,
            (session.get('vendedor_id'),),
        )
    compras = cursor.fetchall()
    cursor.close()
    return render_template('carrito2.html', compras=compras)


@app.route('/producto', methods=['GET'])
@app.route('/producto/<int:id_producto>', methods=['GET', 'POST'])
def producto(id_producto=None):
    if id_producto is None:
        cursor = cursor_bd()
        cursor.execute("SELECT id_producto FROM producto ORDER BY id_producto DESC LIMIT 1")
        fila = cursor.fetchone()
        cursor.close()
        if not fila:
            return render_template('Productos.html', producto=None), 200
        return redirect(url_for('producto', id_producto=fila[0]))

    producto_db = consultar_producto(id_producto)
    if not producto_db:
        return "Producto no encontrado", 404

    if request.method == 'POST':
        if session.get('tipo_usuario') != 'cliente' or not session.get('cliente_id'):
            return redirect(url_for('login'))
        cantidad = request.form.get('cantidad', type=int) or 1
        if cantidad < 1:
            return "Cantidad inválida", 400

        cursor = cursor_bd()
        cursor.execute(
            "INSERT INTO venta (id_producto, cantidad, cliente_id) VALUES (%s, %s, %s)",
            (id_producto, cantidad, session.get('cliente_id')),
        )
        asegurar_conexion().commit()
        cursor.close()
        return redirect(url_for('carrito2'))

    return render_template('Productos.html', producto=producto_db)


@app.route('/formulario')
def formulario():
    return render_template('formulario.html')

@app.route('/admin_vendedores')
def admin_vendedores():

    if session.get('tipo_usuario') != 'admin':
        return redirect(url_for('login'))

    cursor = cursor_bd(dictionary=True)

    cursor.execute("""
        SELECT * FROM vendedores
        WHERE estado = 'pendiente'
    """)

    vendedores = cursor.fetchall()

    cursor.close()

    return render_template(
        'admin_vendedores.html',
        vendedores=vendedores
    )

@app.route('/aprobar_vendedor/<int:id>', methods=['POST'])
def aprobar_vendedor(id):

    if session.get('tipo_usuario') != 'admin':
        return redirect(url_for('login'))

    cursor = cursor_bd()

    cursor.execute("""
    SELECT email
    FROM vendedores
    WHERE id=%s
    """, (id,))

    vendedor = cursor.fetchone()

    if not vendedor:
        cursor.close()
        return "Vendedor no encontrado"

    correo = vendedor[0]

    cursor.execute("""
    UPDATE vendedores
    SET estado='aprobado'
    WHERE id=%s
    """, (id,))

    asegurar_conexion().commit()
    cursor.close()
    enviar_correo_aprobacion(correo)

    return redirect(url_for('admin_vendedores'))

if __name__ == "__main__":
    debug = os.environ.get("NOVARKET_DEBUG", "0") == "1"
    app.run(host="127.0.0.1", port=5000, debug=debug)
