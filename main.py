from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from datetime import datetime

app = Flask(__name__)

habilidades = {
    "guerrero": [
        {"icono": "⚔️", "nombre": "Disciplina de Acero", "desc": "Bonificación por rachas largas"},
        {"icono": "🛡️", "nombre": "Voluntad Férrea", "desc": "Menor castigo al romper racha"}
    ],
    "explorador": [
        {"icono": "🧭", "nombre": "Visión de Ruta", "desc": "Mejor progreso en metas semanales"},
        {"icono": "🥾", "nombre": "Paso Constante", "desc": "Bonificación por constancia diaria"}
    ],
    "mago": [
        {"icono": "🪄", "nombre": "Enfoque Arcano", "desc": "Metas difíciles valen más XP"},
        {"icono": "📜", "nombre": "Sabiduría Ancestral", "desc": "Mejor rendimiento en metas mensuales"}
    ]
}



# Configuración de Base de Datos y Seguridad
app.config['SECRET_KEY'] = 'trilha_pro_key_2026'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///trilha.db'
db = SQLAlchemy(app)

# Configuración de Login
login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)

# --- MODELOS ---

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    clase = db.Column(db.String(20), default='explorador')

    xp = db.Column(db.Integer, default=0)      # 🔥 XP TOTAL
    nivel = db.Column(db.Integer, default=1)   # 🔥 NIVEL RPG

    metas = db.relationship('Meta', backref='autor', lazy=True)


class Meta(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    contenido = db.Column(db.String(200), nullable=False)
    tipo = db.Column(db.String(20), default='diaria')  # diaria, semanal, mensual, anual
    objetivo_conteo = db.Column(db.Float, default=1) 
    progreso_conteo = db.Column(db.Float, default=0) 
    completada = db.Column(db.Boolean, default=False)
    racha = db.Column(db.Integer, default=0)           # Contador de ciclos seguidos
    total_cumplido = db.Column(db.Float, default=0)  # Historial total de éxitos
    ultima_actualizacion = db.Column(db.DateTime, default=datetime.now)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

# Inicialización de la base de datos
with app.app_context():
    db.create_all()

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- RUTAS DE AUTENTICACIÓN ---

@app.route('/')
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form.get('usuario')).first()
        if user and user.password == request.form.get('password'):
            login_user(user)
            return redirect(url_for('dashboard'))
    return render_template('index.html')

@app.route('/registro', methods=['GET', 'POST'])
def registro():
    if request.method == 'POST':
        usuario = request.form.get('usuario')
        clase = request.form.get('clase')

        if not User.query.filter_by(username=usuario).first():
            nuevo = User(
                username=usuario,
                password=request.form.get('password'),
                clase=clase
            )
            db.session.add(nuevo)
            db.session.commit()
            return redirect(url_for('login'))
    return render_template('registro.html')


# --- RUTA PRINCIPAL (DASHBOARD) ---

@app.route('/dashboard')
@login_required
def dashboard():
    estilo_avatar = {
        'guerrero': 'adventurer',
        'explorador': 'personas',
        'mago': 'bottts'
    }

    avatar_url = f"https://api.dicebear.com/7.x/{estilo_avatar[current_user.clase]}/svg?seed={current_user.username}"

    mis_metas = Meta.query.filter_by(user_id=current_user.id).all()
    ahora = datetime.now()
    cambio_db = False

    # Lógica de Reinicio Automático y Gestión de Rachas
    for m in mis_metas:
        reiniciar = False
        
        # Comprobar si el periodo ha expirado
        if m.tipo == 'diaria' and m.ultima_actualizacion.date() < ahora.date():
            reiniciar = True
        elif m.tipo == 'semanal' and m.ultima_actualizacion.isocalendar()[1] < ahora.isocalendar()[1]:
            reiniciar = True
        elif m.tipo == 'mensual' and m.ultima_actualizacion.month < ahora.month:
            reiniciar = True
        elif m.tipo == 'anual' and m.ultima_actualizacion.year < ahora.year:
            reiniciar = True

        if reiniciar:
            # Si el periodo acabó y NO se completó, la racha se rompe
            if not m.completada:
                m.racha = 0
            
            m.progreso_conteo = 0
            m.completada = False
            m.ultima_actualizacion = ahora
            cambio_db = True

        # En dashboard, dentro del loop de metas
        if current_user.clase == "mago" and m.tipo == "mensual" and not m.completada:
            if m.ultima_actualizacion.date() < ahora.date():
                m.progreso_conteo += 1


    if cambio_db:
        db.session.commit()


    # ─── SISTEMA DE XP Y BARRA ─────────────────────────

    xp = current_user.xp
    nivel = int((xp / 100) ** 0.5) + 1

    xp_nivel_actual = int(((nivel - 1) ** 2) * 100)
    xp_siguiente_nivel = int((nivel ** 2) * 100)

    xp_en_nivel = xp - xp_nivel_actual
    xp_necesario = xp_siguiente_nivel - xp_nivel_actual

    progreso_xp = int((xp_en_nivel / xp_necesario) * 100)

    current_user.nivel = nivel
    db.session.commit()


    # ─── NIVEL RPG (XP PERMANENTE) ─────────────────────

    xp = current_user.xp
    nivel = int((xp / 100) ** 0.5) + 1

    current_user.nivel = nivel
    db.session.commit()

    
    return render_template(
        'dashboard.html',
        nombre=current_user.username,
        avatar=avatar_url,
        clase=current_user.clase,
        habilidades=habilidades[current_user.clase],
        metas=mis_metas,
        xp=xp,
        nivel=nivel,
        progreso_xp=progreso_xp,
        xp_en_nivel=xp_en_nivel,
        xp_necesario=xp_necesario,
        ahora=ahora
    )


# --- GESTIÓN DE METAS ---

@app.route('/nueva_meta', methods=['POST'])
@login_required
def nueva_meta():
    contenido = request.form.get('meta')
    if contenido:
        nueva = Meta(
            contenido=contenido,
            tipo=request.form.get('tipo'),
            objetivo_conteo=int(request.form.get('objetivo', 1)),
            autor=current_user
        )
        db.session.add(nueva)
        db.session.commit()
    return redirect(url_for('dashboard'))

@app.route('/subir_progreso/<int:id>')
@login_required
def subir_progreso(id):
    meta = Meta.query.get(id)

    if not meta or meta.user_id != current_user.id or meta.completada:
        return redirect(url_for('dashboard'))

    # Progreso base
    meta.progreso_conteo += 1
    meta.ultima_actualizacion = datetime.now()

    # ─── HABILIDADES PASIVAS ─────────────────────────

    # Explorador: progreso extra en semanal
    if current_user.clase == "explorador" and meta.tipo == "semanal":
        meta.progreso_conteo += 1

    # Mago: metas grandes avanzan más
    if current_user.clase == "mago" and meta.objetivo_conteo >= 5:
        meta.progreso_conteo += 1

    # ─── COMPLETAR META ─────────────────────────────

    if meta.progreso_conteo >= meta.objetivo_conteo:
        meta.completada = True
        meta.racha += 1
        meta.total_cumplido += 1

        # 🎮 XP BASE
        xp_ganado = {
            "diaria": 10,
            "semanal": 30,
            "mensual": 80,
            "anual": 200
        }[meta.tipo]

        # BONOS POR CLASE
        if current_user.clase == "guerrero" and meta.racha >= 3:
            xp_ganado += 5

        if current_user.clase == "explorador" and meta.tipo == "diaria":
            xp_ganado += 3

        if current_user.clase == "mago" and meta.objetivo_conteo >= 5:
            xp_ganado += 10

        #  XP PERMANENTE
        current_user.xp += xp_ganado

    db.session.commit()
    return redirect(url_for('dashboard'))


@app.route('/borrar/<int:id>')
@login_required
def borrar(id):
    meta = Meta.query.get(id)
    if meta and meta.user_id == current_user.id:
        db.session.delete(meta)
        db.session.commit()
    return redirect(url_for('dashboard'))

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))



if __name__ == '__main__':
    app.run(debug=True)