import os
import math
import tempfile
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, send_file, jsonify, send_from_directory
from db import init_db, get_conn
from services import (
    salvar_checklist,
    listar_historico,
    obter_registro,
    gerar_pdf_registro,
    ITENS_CARRO,
    ITENS_MOTO,
    limpar_arquivos_orfaos
)
from config import ANEXOS_DIR

# Inicializa DB (cria tabelas e índices)
init_db()

app = Flask(__name__, static_folder="static", template_folder="templates")
app.secret_key = os.environ.get("SECRET_KEY", "troque-esta-chave")

@app.context_processor
def inject_year():
    return {"current_year": datetime.now().year}

@app.route("/")
def home():
    return redirect(url_for("dashboard"))

@app.route("/dashboard")
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
def detalhes(veiculo_id):
    reg = obter_registro(veiculo_id)
    if not reg:
        flash("Registro não encontrado.", "error")
        return redirect(url_for("historico"))
    return render_template("detalhes.html", reg=reg)

@app.route("/pdf/<int:veiculo_id>")
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

# Serve uploads (anexos)
@app.route("/uploads/<path:filename>")
def uploads(filename):
    return send_from_directory(ANEXOS_DIR, filename, as_attachment=False)

# API com busca e paginação e contagem otimizada para críticos
@app.route("/api/veiculos")
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
    for r in rows:
        items.append({
            "id": r["id"],
            "condutor": r["condutor"],
            "placa": r["placa"],
            "modelo": r["modelo"],
            "data": r["data"],
            "quilometragem": r["quilometragem"],
            "tipo": r["tipo"]
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

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)