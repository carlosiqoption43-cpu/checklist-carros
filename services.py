import os
from datetime import datetime
from PIL import Image
from werkzeug.utils import secure_filename
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader

from db import get_conn
from config import ANEXOS_DIR

# Itens padrão (ajuste conforme necessário)
ITENS_CARRO = [
    "Farol Esq.", "Farol Dir.", "Pisca Esq.", "Pisca Dir.",
    "Lanterna Esq.", "Lanterna Dir.", "Luz de ré", "Luz de freio",
    "Retrovisor Esq.", "Retrovisor Dir.", "Pneus Dianteiros", "Pneus Traseiros",
    "Estepe", "Triângulo", "Macaco", "Chave de roda", "Limpador de para-brisa",
    "Vidros", "Lataria", "Interior", "Fluido de freio"
]

ITENS_MOTO = [
    "Farol", "Pisca Esq.", "Pisca Dir.", "Lanterna", "Luz de freio",
    "Retrovisor Esq.", "Retrovisor Dir.", "Pneus Dianteiros", "Pneus Traseiros",
    "Estepe (se aplicável)", "Triângulo (se aplicável)", "Macaco (se aplicável)",
    "Limpador de para-brisa", "Vidros", "Lataria", "Interior", "Fluido de freio"
]

ALLOWED_EXT = {"png", "jpg", "jpeg", "gif", "webp"}


def _is_allowed(filename: str) -> bool:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return ext in ALLOWED_EXT


def _save_file_storage(file_storage, prefix="file"):
    """
    Salva arquivo em ANEXOS_DIR com nome sanitizado e timestamp.
    Retorna (filename, thumb_filename) — nomes relativos (não caminhos absolutos).
    """
    if not file_storage:
        return None, None
    filename = getattr(file_storage, "filename", None)
    if not filename:
        return None, None

    filename_secure = secure_filename(filename)
    if not _is_allowed(filename_secure):
        return None, None

    ts = datetime.utcnow().strftime("%Y%m%d%H%M%S%f")
    base, ext = os.path.splitext(filename_secure)
    safe_name = f"{prefix}_{ts}_{base}{ext}"
    dest_path = os.path.join(ANEXOS_DIR, safe_name)

    # salva arquivo
    try:
        file_storage.save(dest_path)
    except Exception:
        return None, None

    # gera thumbnail otimizada
    thumb_name = None
    try:
        img = Image.open(dest_path)
        img.thumbnail((1200, 1200))
        thumb_base = f"thumb_{safe_name}"
        thumb_path = os.path.join(ANEXOS_DIR, thumb_base)
        img.save(thumb_path, optimize=True, quality=85)
        thumb_name = thumb_base
    except Exception:
        thumb_name = None

    return safe_name, thumb_name


def salvar_checklist(form, files):
    """
    Salva veículo e itens no banco. Espera campos:
      - tipo, condutor, placa, modelo, quilometragem, observacoes, foto_carro
      - status_<idx>, coment_<idx>, foto_<idx>, itemname_<idx>
    Retorna id do veículo salvo.
    """
    conn = get_conn()
    cur = conn.cursor()

    tipo = form.get("tipo") or "Carro"
    condutor = form.get("condutor")
    placa = form.get("placa")
    modelo = form.get("modelo")
    quilometragem = form.get("quilometragem")
    observacoes = form.get("observacoes")
    data = datetime.now().strftime("%d/%m/%Y %H:%M")

    foto_carro_file = files.get("foto_carro")
    foto_carro_name, foto_thumb = _save_file_storage(foto_carro_file, prefix="veic")

    cur.execute("""
        INSERT INTO veiculos (condutor, placa, modelo, data, quilometragem, observacoes, foto_carro, tipo)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (condutor, placa, modelo, data, quilometragem, observacoes, foto_carro_name, tipo))
    veic_id = cur.lastrowid

    # percorre status_*
    for key in list(form.keys()):
        if key.startswith("status_"):
            idx = key.split("_", 1)[1]
            status = form.get(key)
            comentario = form.get(f"coment_{idx}") or ""
            nome_item = form.get(f"itemname_{idx}") or f"Item {idx}"
            file_field = files.get(f"foto_{idx}")
            caminho_foto, caminho_thumb = _save_file_storage(file_field, prefix=f"item_{idx}")
            cur.execute("""
                INSERT INTO itens_checklist (veiculo_id, nome_item, status, comentario, caminho_foto, caminho_thumb)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (veic_id, nome_item, status, comentario, caminho_foto, caminho_thumb))

    conn.commit()
    conn.close()
    return veic_id


def listar_historico(placa=None, data_ini=None, data_fim=None):
    conn = get_conn()
    cur = conn.cursor()
    query = "SELECT id, condutor, placa, modelo, data, quilometragem, tipo FROM veiculos WHERE 1=1"
    params = []
    if placa:
        query += " AND placa LIKE ?"
        params.append(f"%{placa}%")
    if data_ini:
        try:
            d = datetime.strptime(data_ini, "%d/%m/%Y").strftime("%Y-%m-%d")
            query += " AND date(substr(data,7,4)||'-'||substr(data,4,2)||'-'||substr(data,1,2)) >= date(?)"
            params.append(d)
        except Exception:
            pass
    if data_fim:
        try:
            d = datetime.strptime(data_fim, "%d/%m/%Y").strftime("%Y-%m-%d")
            query += " AND date(substr(data,7,4)||'-'||substr(data,4,2)||'-'||substr(data,1,2)) <= date(?)"
            params.append(d)
        except Exception:
            pass
    query += " ORDER BY id DESC"
    cur.execute(query, params)
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def obter_registro(veiculo_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM veiculos WHERE id = ?", (veiculo_id,))
    v = cur.fetchone()
    if not v:
        conn.close()
        return None
    cur.execute("SELECT * FROM itens_checklist WHERE veiculo_id = ?", (veiculo_id,))
    itens = cur.fetchall()
    conn.close()
    reg = dict(v)
    reg["itens"] = [dict(i) for i in itens]
    return reg


def gerar_pdf_registro(registro, caminho_saida):
    """
    Gera um PDF com:
      - Cabeçalho com dados do veículo
      - Foto principal do veículo (se existir)
      - Lista de itens com status, comentário e miniatura da foto (thumb ou foto)
      - Duas linhas de assinatura ao final: quem realizou o checklist e quem estava com o veículo
    Projetado para visualização em celular: imagens otimizadas e layout vertical.
    """
    width, height = A4
    margin = 40
    y = height - margin

    c = canvas.Canvas(caminho_saida, pagesize=A4)
    c.setTitle(f"Checklist_{registro.get('placa','sem_placa')}")

    # Cabeçalho
    c.setFont("Helvetica-Bold", 16)
    c.drawString(margin, y, "Checklist Veicular")
    c.setFont("Helvetica", 10)
    y -= 22
    c.drawString(margin, y, f"ID: {registro.get('id')}")
    c.drawString(margin + 200, y, f"Data: {registro.get('data') or '-'}")
    y -= 16
    c.drawString(margin, y, f"Placa: {registro.get('placa') or '-'}")
    c.drawString(margin + 200, y, f"Condutor: {registro.get('condutor') or '-'}")
    y -= 16
    c.drawString(margin, y, f"Modelo: {registro.get('modelo') or '-'}")
    c.drawString(margin + 200, y, f"KM: {registro.get('quilometragem') or '-'}")
    y -= 20

    # Foto principal do veículo (se existir) - otimizada para celular (não ocupa página inteira)
    foto_carro = registro.get("foto_carro")
    if foto_carro:
        foto_path = os.path.join(ANEXOS_DIR, foto_carro)
        if os.path.exists(foto_path):
            try:
                max_width = width - 2 * margin
                max_height = 200  # mantém razoável para leitura em celular
                img = Image.open(foto_path)
                img_w, img_h = img.size
                ratio = min(max_width / img_w, max_height / img_h, 1)
                draw_w = img_w * ratio
                draw_h = img_h * ratio
                img_reader = ImageReader(foto_path)
                c.drawImage(img_reader, margin, y - draw_h, width=draw_w, height=draw_h, preserveAspectRatio=True, mask='auto')
                y -= (draw_h + 12)
            except Exception:
                y -= 12
        else:
            y -= 12
    else:
        y -= 6

    # Observações (se houver)
    obs = registro.get("observacoes")
    if obs:
        c.setFont("Helvetica-Oblique", 9)
        text_obj = c.beginText(margin, y)
        text_obj.textLines(f"Observações: {obs}")
        c.drawText(text_obj)
        y -= (12 * (obs.count("\n") + 1) + 6)

    # Espaço antes da lista de itens
    y -= 6
    c.setFont("Helvetica-Bold", 12)
    c.drawString(margin, y, "Itens")
    y -= 16
    c.setFont("Helvetica", 10)

    # Layout para itens com miniaturas (pensado para celular: uma coluna)
    thumb_size = 80
    gap = 8

    for item in registro.get("itens", []):
        nome = item.get("nome_item") or "-"
        status = item.get("status") or "-"
        comentario = item.get("comentario") or ""
        thumb = item.get("caminho_thumb") or item.get("caminho_foto")

        # calcula espaço necessário
        needed_height = max(thumb_size, 36) + 12
        # reserva espaço extra para assinaturas: se faltar, cria nova página
        if y - needed_height < margin + 120:
            c.showPage()
            y = height - margin
            c.setFont("Helvetica", 10)

        # desenha miniatura (se existir)
        draw_w = draw_h = 0
        if thumb:
            thumb_path = os.path.join(ANEXOS_DIR, thumb)
            if os.path.exists(thumb_path):
                try:
                    img = Image.open(thumb_path)
                    img_w, img_h = img.size
                    ratio = min(thumb_size / img_w, thumb_size / img_h, 1)
                    draw_w = img_w * ratio
                    draw_h = img_h * ratio
                    img_reader = ImageReader(thumb_path)
                    c.drawImage(img_reader, margin, y - draw_h, width=draw_w, height=draw_h, preserveAspectRatio=True, mask='auto')
                except Exception:
                    draw_w = draw_h = 0

        # texto do item ao lado da miniatura
        text_x = margin + (draw_w + gap if draw_w else 0)
        c.setFont("Helvetica-Bold", 10)
        c.drawString(text_x, y - 2, nome)
        c.setFont("Helvetica", 9)
        c.drawString(text_x, y - 16, f"Status: {status}")
        if comentario:
            # quebra simples de comentário para caber
            max_chars = 90
            lines = []
            words = comentario.split()
            line = ""
            for w in words:
                test = (line + " " + w).strip()
                if len(test) > max_chars:
                    lines.append(line)
                    line = w
                else:
                    line = test
            if line:
                lines.append(line)
            c.setFont("Helvetica-Oblique", 8)
            ly = y - 30
            for i, ln in enumerate(lines[:3]):  # limita a 3 linhas por item
                c.drawString(text_x, ly - (i * 10), ln)
            used_h = max(draw_h, 30 + (len(lines[:3]) * 10))
            y -= (used_h + 12)
        else:
            used_h = max(draw_h, 30)
            y -= (used_h + 12)

    # Antes de inserir as assinaturas, garante espaço na página atual
    signature_block_height = 80  # espaço reservado para as duas linhas de assinatura
    if y - signature_block_height < margin:
        c.showPage()
        y = height - margin
        c.setFont("Helvetica", 10)

    # Linha separadora antes das assinaturas
    y -= 10
    c.setStrokeColorRGB(0.6, 0.6, 0.6)
    c.setLineWidth(0.5)
    c.line(margin, y, width - margin, y)
    y -= 18

    # Desenha duas áreas de assinatura lado a lado
    sig_width = (width - 2 * margin - 20) / 2  # 20 px gap entre assinaturas
    left_x = margin
    right_x = margin + sig_width + 20

    line_y = y - 20  # posição da linha de assinatura

    # Linha para quem realizou o checklist
    c.setStrokeColorRGB(0, 0, 0)
    c.setLineWidth(1)
    c.line(left_x, line_y, left_x + sig_width, line_y)
    c.setFont("Helvetica", 9)
    c.drawString(left_x, line_y - 14, "Assinatura (quem realizou o checklist)")

    # Linha para quem estava com o veículo
    c.line(right_x, line_y, right_x + sig_width, line_y)
    c.drawString(right_x, line_y - 14, "Assinatura (quem estava com o veículo)")

    # Espaço final
    y = line_y - 40

    c.showPage()
    c.save()


def limpar_arquivos_orfaos(dry_run=True, limit=None):
    """
    Retorna lista de arquivos órfãos. Se dry_run=False, remove os arquivos.
    limit opcional limita quantos arquivos remover/listar.
    """
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

    all_files = sorted(os.listdir(ANEXOS_DIR))
    orphans = [f for f in all_files if f not in referenced]
    if limit:
        orphans = orphans[:limit]

    if dry_run:
        return {"orphans": orphans, "count": len(orphans)}
    removed = []
    errors = []
    for fname in orphans:
        path = os.path.join(ANEXOS_DIR, fname)
        try:
            os.remove(path)
            removed.append(fname)
        except Exception as e:
            errors.append({"file": fname, "error": str(e)})
    return {"removed": removed, "errors": errors, "removed_count": len(removed)}