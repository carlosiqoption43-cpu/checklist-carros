import os
import math
import tempfile
from datetime import datetime, timedelta
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, send_file, jsonify, send_from_directory
from flask_login import LoginManager, current_user, login_required, login_user, logout_user
from werkzeug.security import generate_password_hash
import secrets
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from db import init_db, get_conn
from models import User, Manutencao
from auth import auth_bp
from services import (
    salvar_checklist,
    listar_historico,
    obter_registro,
    gerar_pdf_registro,
    ITENS_CARRO,
    ITENS_MOTO,
    limpar_arquivos_orfaos
)
from config import ANEXOS_DIR, MAIL_SERVER, MAIL_PORT, MAIL_USERNAME, MAIL_PASSWORD, MAIL_DEFAULT_SENDER, SECRET_KEY

# Inicializa DB (cria tabelas e índices)
init_db()

app = Flask(__name__, static_folder="static", template_folder="templates")
app.secret_key = os.environ.get("SECRET_KEY", "troque-esta-chave")

# Configuração do Flask-Login
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.login_message = 'Por favor, faça login para acessar esta página.'
login_manager.login_message_category = 'warning'
login_manager.init_app(app)

# Configuração do envio de e-mail
def send_email(subject, recipient, html_content):
    if not MAIL_SERVER or not MAIL_USERNAME or not MAIL_PASSWORD:
        print("Configuração de e-mail não encontrada. E-mail não enviado.")
        print(f"Assunto: {subject}")
        print(f"Para: {recipient}")
        print(f"Conteúdo: {html_content}")
        return False
        
    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = MAIL_DEFAULT_SENDER
        msg['To'] = recipient
        
        part = MIMEText(html_content, 'html')
        msg.attach(part)
        
        with smtplib.SMTP(MAIL_SERVER, MAIL_PORT) as server:
            server.starttls()
            server.login(MAIL_USERNAME, MAIL_PASSWORD)
            server.send_message(msg)
            
        return True
    except Exception as e:
        print(f"Erro ao enviar e-mail: {e}")
        return False

@login_manager.user_loader
def load_user(user_id):
    return User.get(user_id)

# Registrar Blueprint de autenticação
app.register_blueprint(auth_bp, url_prefix='/')

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('Acesso restrito a administradores', 'error')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

@app.context_processor
def inject_year():
    return {"current_year": datetime.now().year}

@app.route("/")
def home():
    return redirect(url_for("dashboard"))

@app.route("/dashboard")
@login_required
def dashboard():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM veiculos")
    total_checklists = cur.fetchone()[0] or 0
    cur.execute("SELECT COUNT(*) FROM veiculos WHERE tipo='Carro'")
    total_carros = cur.fetchone()[0] or 0
    cur.execute("SELECT COUNT(*) FROM veiculos WHERE tipo='Moto'")
    total_motos = cur.fetchone()[0] or 0
    cur.execute("""
        SELECT COUNT(*) FROM itens_checklist
        WHERE status='Danificado' OR status IN ('Desgastado','Calibrar','Baixo','Alto')
    """)
    total_criticos = cur.fetchone()[0] or 0

    cur.execute("""
        SELECT substr(data, 4, 2) || '/' || substr(data, 7, 4) as mes, COUNT(*) as qtd
        FROM veiculos
        WHERE data IS NOT NULL AND data <> ''
        GROUP BY mes
        ORDER BY substr(data, 7, 4) ASC, substr(data, 4, 2) ASC
    """)
    meses_rows = cur.fetchall()
    meses_labels = [r[0] for r in meses_rows]
    meses_data = [r[1] for r in meses_rows]

    cur.execute("""
        SELECT nome_item, COUNT(*) as qtd
        FROM itens_checklist
        WHERE status='Danificado' OR status IN ('Desgastado','Calibrar','Baixo','Alto')
        GROUP BY nome_item
        ORDER BY qtd DESC
        LIMIT 5
    """)
    criticos_rows = cur.fetchall()
    criticos_labels = [r[0] for r in criticos_rows]
    criticos_data = [r[1] for r in criticos_rows]

    conn.close()
    return render_template("dashboard.html",
        total_checklists=total_checklists,
        total_carros=total_carros,
        total_motos=total_motos,
        total_criticos=total_criticos,
        meses_labels=meses_labels,
        meses_data=meses_data,
        criticos_labels=criticos_labels,
        criticos_data=criticos_data
    )

@app.route("/index")
@login_required
def index():
    pneus = [i for i in ITENS_CARRO if "Pneu" in i or "Pneus" in i or "Estepe" in i]
    fluidos = [i for i in ITENS_CARRO if "Fluido" in i or "Óleo" in i]
    return render_template("index.html", itens_carro=ITENS_CARRO, itens_moto=ITENS_MOTO, pneus=pneus, fluidos=fluidos)

@app.route("/salvar", methods=["POST"])
def salvar():
    try:
        veic_id = salvar_checklist(request.form, request.files)
        flash(f"Checklist salvo com sucesso! ID: {veic_id}", "success")
        return redirect(url_for("detalhes", veiculo_id=veic_id))
    except Exception as e:
        flash(f"Erro ao salvar checklist: {e}", "error")
        return redirect(url_for("index"))

@app.route("/historico", methods=["GET", "POST"])
@login_required
def historico():
    resultados = []
    try:
        if request.method == "POST":
            placa = request.form.get("placa")
            data_ini = request.form.get("data_ini")
            data_fim = request.form.get("data_fim")
            resultados = listar_historico(placa, data_ini, data_fim)
        else:
            resultados = listar_historico(None, None, None)
    except Exception as e:
        flash(f"Erro ao buscar histórico: {e}", "error")
    return render_template("historico.html", resultados=resultados)

@app.route("/detalhes/<int:veiculo_id>")
@login_required
def detalhes(veiculo_id):
    reg = obter_registro(veiculo_id)
    if not reg:
        flash("Registro não encontrado.", "error")
        return redirect(url_for("historico"))
    return render_template("detalhes.html", reg=reg)

@app.route("/pdf/<int:veiculo_id>")
@login_required
def pdf(veiculo_id):
    reg = obter_registro(veiculo_id)
    if not reg:
        flash("Registro não encontrado.", "error")
        return redirect(url_for("historico"))
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    tmp.close()
    gerar_pdf_registro(reg, tmp.name)
    filename = f"checklist_{reg.get('placa','sem_placa')}_{(reg.get('data') or '').replace('/','-')}.pdf"
    return send_file(tmp.name, as_attachment=True, download_name=filename)

@app.route("/uploads/<path:filename>")
def uploads(filename):
    return send_from_directory(ANEXOS_DIR, filename, as_attachment=False)

# API com busca e paginação e contagem otimizada para críticos
@app.route("/api/veiculos")
@login_required
def api_veiculos():
    tipo = request.args.get("tipo")
    criticos = request.args.get("criticos")
    q = (request.args.get("q") or "").strip()
    try:
        page = max(1, int(request.args.get("page", 1)))
    except ValueError:
        page = 1
    try:
        per_page = max(5, min(100, int(request.args.get("per_page", 10))))
    except ValueError:
        per_page = 10

    conn = get_conn()
    cur = conn.cursor()

    where_clauses = []
    params = []

    if tipo:
        where_clauses.append("v.tipo = ?")
        params.append(tipo)

    if q:
        where_clauses.append("(v.placa LIKE ? OR v.condutor LIKE ? OR v.modelo LIKE ?)")
        like = f"%{q}%"
        params.extend([like, like, like])

    where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

    # Conta total
    if criticos == "1":
        crit_query = f"""
            SELECT COUNT(DISTINCT v.id) FROM veiculos v
            {where_sql and 'WHERE ' + ' AND '.join(where_clauses) or ''}
            AND EXISTS (
                SELECT 1 FROM itens_checklist it
                WHERE it.veiculo_id = v.id
                AND (it.status = 'Danificado' OR it.status IN ('Desgastado','Calibrar','Baixo','Alto'))
            )
        """
        # Ajuste: se where_sql vazio, crit_query terá 'AND EXISTS' sem WHERE; corrigimos montando condicionalmente
        if where_clauses:
            crit_query = f"""
                SELECT COUNT(DISTINCT v.id) FROM veiculos v
                WHERE {' AND '.join(where_clauses)}
                AND EXISTS (
                    SELECT 1 FROM itens_checklist it
                    WHERE it.veiculo_id = v.id
                    AND (it.status = 'Danificado' OR it.status IN ('Desgastado','Calibrar','Baixo','Alto'))
                )
            """
            cur.execute(crit_query, params)
        else:
            crit_query = """
                SELECT COUNT(DISTINCT v.id) FROM veiculos v
                WHERE EXISTS (
                    SELECT 1 FROM itens_checklist it
                    WHERE it.veiculo_id = v.id
                    AND (it.status = 'Danificado' OR it.status IN ('Desgastado','Calibrar','Baixo','Alto'))
                )
            """
            cur.execute(crit_query)
        total = cur.fetchone()[0] or 0

        # Busca paginada veículos críticos
        offset = (page - 1) * per_page
        if where_clauses:
            data_query = f"""
                SELECT v.id, v.condutor, v.placa, v.modelo, v.data, v.quilometragem, v.tipo
                FROM veiculos v
                WHERE {' AND '.join(where_clauses)}
                AND EXISTS (
                    SELECT 1 FROM itens_checklist it
                    WHERE it.veiculo_id = v.id
                    AND (it.status = 'Danificado' OR it.status IN ('Desgastado','Calibrar','Baixo','Alto'))
                )
                ORDER BY v.id DESC
                LIMIT ? OFFSET ?
            """
            cur.execute(data_query, params + [per_page, offset])
        else:
            data_query = """
                SELECT v.id, v.condutor, v.placa, v.modelo, v.data, v.quilometragem, v.tipo
                FROM veiculos v
                WHERE EXISTS (
                    SELECT 1 FROM itens_checklist it
                    WHERE it.veiculo_id = v.id
                    AND (it.status = 'Danificado' OR it.status IN ('Desgastado','Calibrar','Baixo','Alto'))
                )
                ORDER BY v.id DESC
                LIMIT ? OFFSET ?
            """
            cur.execute(data_query, [per_page, offset])
        rows = cur.fetchall()
    else:
        # total simples
        count_query = f"SELECT COUNT(*) FROM veiculos {'WHERE ' + ' AND '.join(where_clauses) if where_clauses else ''}"
        cur.execute(count_query, params)
        total = cur.fetchone()[0] or 0
        offset = (page - 1) * per_page
        data_query = f"""
            SELECT id, condutor, placa, modelo, data, quilometragem, tipo
            FROM veiculos
            {where_sql}
            ORDER BY id DESC
            LIMIT ? OFFSET ?
        """
        cur.execute(data_query, params + [per_page, offset])
        rows = cur.fetchall()

    items = []
    # calcula indicador de troca de óleo por item (com base em quilometragem atual e oleo_km)
    def _to_int(val):
        try:
            s = str(val or "")
            nums = ''.join(ch for ch in s if ch.isdigit())
            return int(nums) if nums else None
        except Exception:
            return None

    for r in rows:
        quil = _to_int(r['quilometragem']) if 'quilometragem' in r.keys() else None
        oleo_km = _to_int(r['oleo_km']) if 'oleo_km' in r.keys() and r['oleo_km'] is not None else None
        if quil is not None and oleo_km is not None:
            diff = quil - oleo_km
            oleo_alert = diff >= 6000
            oleo_due_in = max(0, 6000 - diff)
        else:
            diff = None
            oleo_alert = False
            oleo_due_in = None

        items.append({
            "id": r["id"],
            "condutor": r["condutor"],
            "placa": r["placa"],
            "modelo": r["modelo"],
            "data": r["data"],
            "quilometragem": r["quilometragem"],
            "tipo": r["tipo"],
            "oleo_km": (r["oleo_km"] if 'oleo_km' in r.keys() else None),
            "oleo_data": (r["oleo_data"] if 'oleo_data' in r.keys() else None),
            "oleo_alert": oleo_alert,
            "oleo_diff": diff,
            "oleo_due_in": oleo_due_in
        })

    conn.close()
    total_pages = max(1, math.ceil(total / per_page)) if total else 1

    return jsonify({
        "items": items,
        "page": page,
        "per_page": per_page,
        "total": total,
        "total_pages": total_pages
    })

# Rota administrativa para limpar uploads órfãos
@app.route("/admin/cleanup-uploads", methods=["GET"])
@admin_required
def cleanup_uploads():
    confirm = request.args.get("confirm") == "1"
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT foto_carro FROM veiculos
        UNION
        SELECT caminho_foto FROM itens_checklist
        UNION
        SELECT caminho_thumb FROM itens_checklist
    """)
    referenced = {row[0] for row in cur.fetchall() if row[0]}
    conn.close()

    all_files = set(os.listdir(ANEXOS_DIR))
    orphans = sorted(list(all_files - referenced))

    result = {"total_files": len(all_files), "referenced": len(referenced), "orphans_count": len(orphans), "orphans_sample": orphans[:200]}

    if confirm and orphans:
        removed = []
        errors = []
        for fname in orphans:
            path = os.path.join(ANEXOS_DIR, fname)
            try:
                os.remove(path)
                removed.append(fname)
            except Exception as e:
                errors.append({"file": fname, "error": str(e)})
        result["removed_count"] = len(removed)
        result["removed_sample"] = removed[:200]
        result["errors"] = errors

    return jsonify(result)

# Rotas para manutenção de veículos
@app.route("/manutencao")
@login_required
def manutencao():
    """Lista todas as manutenções"""
    manutencoes = Manutencao.get_all()
    return render_template("manutencao/listar.html", manutencoes=manutencoes)

@app.route("/manutencao/novo/<int:veiculo_id>", methods=["GET", "POST"])
@login_required
def nova_manutencao(veiculo_id):
    """Adiciona uma nova manutenção para um veículo"""
    from services import obter_registro
    veiculo = obter_registro(veiculo_id)
    
    if not veiculo:
        flash("Veículo não encontrado.", "error")
        return redirect(url_for("historico"))
    
    if request.method == "POST":
        try:
            manutencao = Manutencao.create(
                veiculo_id=veiculo_id,
                nome_peca=request.form.get("nome_peca"),
                data_manutencao=request.form.get("data_manutencao"),
                quilometragem_atual=request.form.get("quilometragem_atual"),
                vida_util_km=request.form.get("vida_util_km") or None,
                proxima_manutencao_km=request.form.get("proxima_manutencao_km") or None,
                valor_peca=request.form.get("valor_peca") or None,
                mao_de_obra=request.form.get("mao_de_obra") or None,
                observacoes=request.form.get("observacoes") or None
            )
            flash("Manutenção registrada com sucesso!", "success")
            return redirect(url_for("manutencoes_veiculo", veiculo_id=veiculo_id))
        except Exception as e:
            flash(f"Erro ao registrar manutenção: {e}", "error")
    
    return render_template("manutencao/novo.html", veiculo=veiculo)

@app.route("/manutencao/veiculo/<int:veiculo_id>")
@login_required
def manutencoes_veiculo(veiculo_id):
    """Lista todas as manutenções de um veículo específico"""
    from services import obter_registro
    veiculo = obter_registro(veiculo_id)
    
    if not veiculo:
        flash("Veículo não encontrado.", "error")
        return redirect(url_for("historico"))
    
    manutencoes = Manutencao.get_by_veiculo(veiculo_id)
    return render_template("manutencao/veiculo.html", veiculo=veiculo, manutencoes=manutencoes)

@app.route("/manutencao/editar/<int:manutencao_id>", methods=["GET", "POST"])
@login_required
def editar_manutencao(manutencao_id):
    """Edita uma manutenção existente"""
    manutencao = Manutencao.get_by_id(manutencao_id)
    
    if not manutencao:
        flash("Manutenção não encontrada.", "error")
        return redirect(url_for("manutencao"))
    
    if request.method == "POST":
        try:
            manutencao.nome_peca = request.form.get("nome_peca")
            manutencao.data_manutencao = request.form.get("data_manutencao")
            manutencao.quilometragem_atual = request.form.get("quilometragem_atual")
            manutencao.vida_util_km = request.form.get("vida_util_km") or None
            manutencao.proxima_manutencao_km = request.form.get("proxima_manutencao_km") or None
            manutencao.valor_peca = request.form.get("valor_peca") or None
            manutencao.mao_de_obra = request.form.get("mao_de_obra") or None
            manutencao.observacoes = request.form.get("observacoes") or None
            
            manutencao.update()
            flash("Manutenção atualizada com sucesso!", "success")
            return redirect(url_for("manutencoes_veiculo", veiculo_id=manutencao.veiculo_id))
        except Exception as e:
            flash(f"Erro ao atualizar manutenção: {e}", "error")
    
    return render_template("manutencao/editar.html", manutencao=manutencao)

@app.route("/manutencao/excluir/<int:manutencao_id>", methods=["POST"])
@login_required
def excluir_manutencao(manutencao_id):
    """Exclui uma manutenção"""
    manutencao = Manutencao.get_by_id(manutencao_id)
    
    if not manutencao:
        flash("Manutenção não encontrada.", "error")
        return redirect(url_for("manutencao"))
    
    try:
        veiculo_id = manutencao.veiculo_id
        manutencao.delete()
        flash("Manutenção excluída com sucesso!", "success")
        return redirect(url_for("manutencoes_veiculo", veiculo_id=veiculo_id))
    except Exception as e:
        flash(f"Erro ao excluir manutenção: {e}", "error")
        return redirect(url_for("manutencoes_veiculo", veiculo_id=manutencao.veiculo_id))

def create_admin_user():
    """Cria o usuário administrador padrão se não existir"""
    admin = User.find_by_username("vip")
    
    if not admin:
        try:
            admin = User.create(
                username="vip",
                password="vip123",
                email="vip@example.com",
                is_admin=True
            )
            print("\n" + "="*60)
            print("USUÁRIO ADMINISTRADOR CRIADO COM SUCESSO")
            print("="*60)
            print(f"Usuário: vip")
            print(f"Senha: vip123")
            print("\nIMPORTANTE: Altere esta senha após o primeiro login!")
            print("="*60 + "\n")
        except Exception as e:
            print(f"Erro ao criar usuário administrador: {e}")
    else:
        print("Usuário administrador 'vip' já existe no banco de dados.")

if __name__ == "__main__":
    # Criar tabelas e usuário admin padrão se não existirem
    with app.app_context():
        conn = get_conn()
        cur = conn.cursor()
        
        # Criar tabela de usuários se não existir
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                email TEXT,
                is_admin BOOLEAN DEFAULT 0,
                reset_token TEXT,
                reset_token_expiration TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        
        # Criar usuário administrador padrão
        create_admin_user()
    
    # Iniciar o servidor
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)