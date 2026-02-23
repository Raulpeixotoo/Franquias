from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
import os
import json
import re
from datetime import datetime, date
from collections import Counter

# ✅ CORREÇÃO: __file__ com underscores
basedir = os.path.abspath(os.path.dirname(__file__))
app = Flask(
    __name__,  # ✅ CORREÇÃO: __name__ com underscores
    template_folder=os.path.join(basedir, 'templates'),
    static_folder=os.path.join(basedir, 'static') if os.path.exists(os.path.join(basedir, 'static')) else None
)

# Configuração do Banco de Dados
database_url = os.environ.get('DATABASE_URL')
if database_url:
    # Corrige a URL do PostgreSQL
    database_url = database_url.replace('postgres://', 'postgresql://', 1)
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
    print("✅ Usando PostgreSQL")
    
    # 🔥 FIX: Força o uso de psycopg2 com configuração adicional
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'pool_pre_ping': True,
        'pool_recycle': 300,
        'connect_args': {
            'connect_timeout': 10,
            'keepalives_idle': 30,
            'keepalives_interval': 10,
            'keepalives_count': 5
        }
    }
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'banco.db')
    print("⚠️ Usando SQLite")

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# 🔥 FIX: Inicialização correta do SQLAlchemy
db = SQLAlchemy()
db.init_app(app)

# Resto do seu código permanece IGUAL...
# (todo o código das linhas 26 até o final permanece o mesmo)

TIPOS_UNIDADE = {
    "CO": "Centro de Operações",
    "FL": "Filial",
    "LJ": "Loja Própria",
    "PA": "Posto de Atendimento",
    "HB": "Hub",
    "JE": "Franquia Light",
    "MATRIZ": "Matriz"
}

STATUS_UNIDADE = {
    "processo": {"label": "🔄 Em Processo", "class": "warning"},
    "pronta": {"label": "✅ Pronta para Abrir", "class": "success"},
    "aberta": {"label": "🟢 Aberta", "class": "info"},
    "fechada": {"label": "🔴 Fechada", "class": "secondary"}
}

CATEGORIAS_REQUISITOS = {
    "abertura/fechamento": [
        {"nome": "Data de Abertura ou Fechamento", "tipo": "checkbox"},
    ],
    "🚚 DADOS": [
        {"nome": "Inicio dos Processos", "tipo": "field", "campo": "date"},
        {"nome": "Nome do Candidato", "tipo": "field", "campo": "text"},
        {"nome": "E-mail", "tipo": "field", "campo": "email"},
        {"nome": "Telefone do Candidato", "tipo": "field", "campo": "tel"}
    ],
    "📄 Documentos": [
        {"nome": "Cnpj", "tipo": "checkbox"},
        {"nome": "Contrato Social", "tipo": "checkbox"},
        {"nome": "I.M.", "tipo": "checkbox"},
        {"nome": "I.E.", "tipo": "checkbox"},
        {"nome": "Sócios RG", "tipo": "checkbox"},
        {"nome": "Sócios CPF", "tipo": "checkbox"},
        {"nome": "Sócios Comprov. Residencia", "tipo": "checkbox"},
        {"nome": "Fiador RG", "tipo": "checkbox"},
        {"nome": "Fiador CPF", "tipo": "checkbox"},
        {"nome": "Fiador Comprov. Residencia", "tipo": "checkbox"},
        {"nome": "Escritura Imóvel", "tipo": "checkbox"},
        {"nome": "Dados Bancários", "tipo": "checkbox"},
        {"nome": "Imóvel Franquia", "tipo": "checkbox"},
        {"nome": "MAE (Manual Assinatura Eletronica)", "tipo": "checkbox"}
    ],
    "💰 Financeiro": [
        {"nome": "Data Solicitação", "tipo": "checkbox"},
        {"nome": "Pedido Ativação Financeiro", "tipo": "checkbox"},
        {"nome": "Confirma Ativação Financeiro", "tipo": "checkbox"},
        {"nome": "Aprovação Financeira", "tipo": "approval"}
    ],
    "💻 TI": [
        {"nome": "E-mail Oficial", "tipo": "checkbox"},
        {"nome": "Ponto da Unidade", "tipo": "checkbox"},
        {"nome": "Código Etiqueta Teca", "tipo": "checkbox"},
        {"nome": "Solicitação do email oficial", "tipo": "checkbox"},
        {"nome": "Retorno email oficial", "tipo": "checkbox"},
        {"nome": "N° do Contrato", "tipo": "checkbox"},
        {"nome": "Subir Projuris", "tipo": "checkbox"},
        {"nome": "Assinado Projuris", "tipo": "checkbox"},
        {"nome": "Envio E-mail Oficial", "tipo": "checkbox"}
    ],
    "🏗️ Inetum": [
        {"nome": "Solicitação SALESFORCE", "tipo": "checkbox"},
        {"nome": "Solicitação FractionWeb", "tipo": "checkbox"}
    ],
    "🚚 Rodobens": [
        {"nome": "Pedido GRIS", "tipo": "checkbox"},
        {"nome": "Feedback GRIS", "tipo": "checkbox"}
    ],
    "Marketing": [
        {"nome": "Pedido GRIS", "tipo": "checkbox"},
        {"nome": "Feedback GRIS", "tipo": "checkbox"}
    ],
    "📝 Assinatura 4Design": [
        {"nome": "Uniformes Entregues", "tipo": "checkbox"},
        {"nome": "Treinamento Operacional Concluído", "tipo": "checkbox"},
        {"nome": "Escala de Trabalho Definida", "tipo": "checkbox"},
        {"nome": "Envio da PAF", "tipo": "checkbox"},
        {"nome": "Assinatura PAF", "tipo": "checkbox"},
        {"nome": "Envio da CCF", "tipo": "checkbox"},
        {"nome": "Assinatura CCF", "tipo": "checkbox"},
        {"nome": "Envio da COF", "tipo": "checkbox"},
        {"nome": "Assinatura COF", "tipo": "checkbox"}
    ],
    "Outros": [
        {"nome": "e-mail equips", "tipo": "checkbox"},
        {"nome": "Marketing - Proj. Arquitetura", "tipo": "checkbox"},
        {"nome": "Pagamento Adesão", "tipo": "checkbox"},
        {"nome": "2° Meeting", "tipo": "checkbox"},
        {"nome": "Treinamento", "tipo": "checkbox"},
        {"nome": "Jira Alt CEPS e OC's", "tipo": "checkbox"},
        {"nome": "Central Lat&Long", "tipo": "checkbox"}
    ]
}

def gerar_id_seguro(texto):
    texto_limpo = re.sub(r'[^\w\s]', '', texto)
    texto_limpo = re.sub(r'\s+', '_', texto_limpo)
    return texto_limpo.lower()

class Unidade(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    cidade = db.Column(db.String(50), nullable=False)
    uf = db.Column(db.String(2), nullable=False)
    tipo = db.Column(db.String(10), nullable=False)
    status_unidade = db.Column(db.String(20), default="processo")
    checklist_status = db.Column(db.Text, default="{}")

def verificar_atrasados(checklist_json):
    if not checklist_json or checklist_json == "{}":
        return []
    try:
        dados = json.loads(checklist_json)
    except:
        return []
    
    atrasados = []
    hoje = date.today().isoformat()
    
    for item, info in dados.items():
        if isinstance(info, dict):
            concluido = info.get('concluido', False)
            previsao = info.get('previsao', '')
            if not concluido and previsao and previsao < hoje:
                atrasados.append({
                    'nome': item,
                    'previsao': previsao,
                    'dias_atraso': (date.today() - date.fromisoformat(previsao)).days
                })
    return atrasados

def calcular_status_categorias(checklist_json, categorias):
    if not checklist_json or checklist_json == "{}":
        return {cat: {"status": "nao_iniciado", "total": len(itens), "concluidos": 0} for cat, itens in categorias.items()}
    try:
        dados = json.loads(checklist_json)
    except:
        return {}
    
    hoje = date.today().isoformat()
    resultado = {}
    
    for categoria, itens in categorias.items():
        total = len(itens)
        concluidos = 0
        tem_atraso = False
        
        for item_config in itens:
            item_nome = item_config['nome']
            info = dados.get(item_nome, {})
            if item_config['tipo'] == 'checkbox':
                if isinstance(info, dict):
                    if info.get('concluido', False):
                        concluidos += 1
                    else:
                        previsao = info.get('previsao', '')
                        if previsao and previsao < hoje:
                            tem_atraso = True
            else:
                if info and info != '':
                    concluidos += 1
        
        if concluidos == total:
            status = "concluido"
        elif tem_atraso:
            status = "atrasado"
        elif concluidos > 0:
            status = "andamento"
        else:
            status = "pendente"
        
        resultado[categoria] = {"status": status, "total": total, "concluidos": concluidos}
    return resultado

def gerar_resumos(unidades):
    total = len(unidades)
    abertas = sum(1 for u in unidades if u.status_unidade == "aberta")
    fechadas = sum(1 for u in unidades if u.status_unidade == "fechada")
    em_processo = total - abertas - fechadas
    
    ufs = Counter(u.uf for u in unidades)
    tipos = Counter(u.tipo for u in unidades)
    
    return {
        'total': total,
        'abertas': abertas,
        'em_processo': em_processo,
        'fechadas': fechadas,
        'ufs': dict(ufs),
        'tipos': dict(tipos)
    }

def classificar_prazos(unidades, categorias):
    hoje = date.today()
    todos_prazos = []
    for u in unidades:
        try:
            dados = json.loads(u.checklist_status) if u.checklist_status else {}
            for item_nome, info in dados.items():
                if isinstance(info, dict):
                    previsao = info.get('previsao', '')
                    concluido = info.get('concluido', False)
                    if previsao and not concluido:
                        data_prev = date.fromisoformat(previsao)
                        dias = (data_prev - hoje).days
                        urgencia = 'atrasado' if dias < 0 else ('proximo' if dias <= 7 else 'futuro')
                        categoria = 'Outros'
                        for cat, itens in categorias.items():
                            for item_config in itens:
                                if item_config['nome'] == item_nome:
                                    categoria = cat
                                    break
                        todos_prazos.append({
                            'unidade': u.nome,
                            'unidade_id': u.id,
                            'item': item_nome,
                            'categoria': categoria.split(' ')[-1],
                            'previsao': previsao,
                            'dias': dias,
                            'urgencia': urgencia
                        })
        except:
            pass
    todos_prazos.sort(key=lambda x: (x['urgencia'] != 'atrasado', x['previsao']))
    return todos_prazos

@app.route('/')
def index():
    filtro_status = request.args.get('status', '')
    filtro_uf = request.args.get('uf', '')
    filtro_tipo = request.args.get('tipo', '')
    filtro_atraso = request.args.get('atraso', '')
    busca_nome = request.args.get('busca', '')
    
    unidades = Unidade.query.order_by(Unidade.nome.asc()).all()
    unidades_filtradas = []
    
    for u in unidades:
        if filtro_status and u.status_unidade != filtro_status:
            continue
        if filtro_uf and u.uf != filtro_uf:
            continue
        if filtro_tipo and u.tipo != filtro_tipo:
            continue
        if filtro_atraso == 'sim':
            atrasados = verificar_atrasados(u.checklist_status)
            if not atrasados:
                continue
        if busca_nome and busca_nome.lower() not in u.nome.lower():
            continue
        unidades_filtradas.append(u)
    
    resumos = gerar_resumos(unidades_filtradas)
    unidades_info = []
    
    for u in unidades_filtradas:
        try:
            dados = json.loads(u.checklist_status) if u.checklist_status else {}
            total = sum(len(itens) for itens in CATEGORIAS_REQUISITOS.values())
            concluidos = 0
            for item_config in sum(CATEGORIAS_REQUISITOS.values(), []):
                item_nome = item_config['nome']
                info = dados.get(item_nome, {})
                if item_config['tipo'] == 'checkbox':
                    if isinstance(info, dict) and info.get('concluido', False):
                        concluidos += 1
                else:
                    if info and info != '':
                        concluidos += 1
            progresso = int((concluidos / total) * 100) if total > 0 else 0
        except:
            progresso = 0
        
        aprovacao_financeira = dados.get('Aprovação Financeira', 'pendente') if dados else 'pendente'
        status_categorias = calcular_status_categorias(u.checklist_status, CATEGORIAS_REQUISITOS)
        atrasados = verificar_atrasados(u.checklist_status)
        
        unidades_info.append({
            'unidade': u,
            'progresso': progresso,
            'status_categorias': status_categorias,
            'atrasados': atrasados,
            'qtd_atrasados': len(atrasados),
            'aprovacao_financeira': aprovacao_financeira
        })
    
    todas_ufs = sorted(set(u.uf for u in Unidade.query.all()))
    todos_tipos = sorted(set(u.tipo for u in Unidade.query.all()))
    todos_prazos = classificar_prazos(unidades_filtradas, CATEGORIAS_REQUISITOS)
    
    return render_template('index.html', 
                           unidades_info=unidades_info, 
                           resumos=resumos,
                           tipos_unidade=TIPOS_UNIDADE,
                           status_unidade_opts=STATUS_UNIDADE,
                           filtro_status=filtro_status,
                           filtro_uf=filtro_uf,
                           filtro_tipo=filtro_tipo,
                           filtro_atraso=filtro_atraso,
                           busca_nome=busca_nome,
                           todas_ufs=todas_ufs,
                           todos_tipos=todos_tipos,
                           todos_prazos=todos_prazos)

@app.route('/adicionar', methods=['GET', 'POST'])
def adicionar():
    if request.method == 'POST':
        nome = request.form['nome']
        cidade = request.form['cidade']
        uf = request.form['uf']
        tipo = request.form['tipo']
        status = request.form.get('status_unidade', 'processo')
        nova_unidade = Unidade(nome=nome, cidade=cidade, uf=uf, tipo=tipo, status_unidade=status)
        db.session.add(nova_unidade)
        db.session.commit()
        return redirect(url_for('index'))
    return render_template('adicionar.html', tipos_unidade=TIPOS_UNIDADE, status_unidade_opts=STATUS_UNIDADE)

@app.route('/gerenciar/<int:id>', methods=['GET', 'POST'])
def gerenciar(id):
    unidade = Unidade.query.get_or_404(id)
    
    if request.method == 'POST':
        apenas_status = request.form.get('apenas_status', '')
        
        if apenas_status == 'sim':
            unidade.status_unidade = request.form.get('status_unidade', unidade.status_unidade)
            db.session.commit()
            return redirect(url_for('gerenciar', id=id))
        
        unidade.status_unidade = request.form.get('status_unidade', unidade.status_unidade)
        dados_form = request.form.to_dict()
        status_atualizado = {}
        
        for item_config in sum(CATEGORIAS_REQUISITOS.values(), []):
            item_nome = item_config['nome']
            item_id = gerar_id_seguro(item_nome)
            
            if item_config['tipo'] == 'checkbox':
                valor = dados_form.get(f'req_{item_id}', '')
                conclusao = dados_form.get(f'conclusao_{item_id}', '')
                previsao = dados_form.get(f'previsao_{item_id}', '')
                obs = dados_form.get(f'obs_{item_id}', '')
                
                status_atualizado[item_nome] = {
                    'concluido': (valor == 'on'),
                    'previsao': previsao,
                    'conclusao': conclusao,
                    'obs': obs if obs else None
                }
            elif item_config['tipo'] == 'approval':
                valor = dados_form.get(f'aprovacao_{item_id}', 'pendente')
                obs = dados_form.get(f'obs_{item_id}', '')
                status_atualizado[item_nome] = valor
                if obs:
                    status_atualizado[f'obs_{item_nome}'] = obs
            else:
                valor = dados_form.get(f'dado_{item_id}', '')
                obs = dados_form.get(f'obs_{item_id}', '')
                if item_config['campo'] == 'email' and valor:
                    padrao_email = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
                    if not re.match(padrao_email, valor):
                        valor = ''
                status_atualizado[item_nome] = valor
                if obs:
                    status_atualizado[f'obs_{item_nome}'] = obs
        
        unidade.checklist_status = json.dumps(status_atualizado, ensure_ascii=False)
        db.session.commit()
        return redirect(url_for('index'))
    
    status_salvo = {}
    if unidade.checklist_status and unidade.checklist_status != "{}":
        try:
            status_salvo = json.loads(unidade.checklist_status)
        except:
            status_salvo = {}
    
    atrasados = verificar_atrasados(unidade.checklist_status)
    
    return render_template('checklist.html', 
                           unidade=unidade, 
                           categorias=CATEGORIAS_REQUISITOS, 
                           status_salvo=status_salvo,
                           status_unidade_opts=STATUS_UNIDADE,
                           atrasados=atrasados,
                           hoje=date.today().isoformat(),
                           gerar_id_seguro=gerar_id_seguro)

@app.route('/dashboard')
def dashboard():
    unidades = Unidade.query.all()
    total = len(unidades)
    abertas = sum(1 for u in unidades if u.status_unidade == 'aberta')
    em_processo = sum(1 for u in unidades if u.status_unidade in ['processo', 'pronta'])
    fechadas = sum(1 for u in unidades if u.status_unidade == 'fechada')
    
    progressos = []
    for u in unidades:
        try:
            dados = json.loads(u.checklist_status) if u.checklist_status else {}
            total_itens = sum(len(itens) for itens in CATEGORIAS_REQUISITOS.values())
            concluidos = 0
            for item_config in sum(CATEGORIAS_REQUISITOS.values(), []):
                item_nome = item_config['nome']
                info = dados.get(item_nome, {})
                if item_config['tipo'] == 'checkbox':
                    if isinstance(info, dict) and info.get('concluido', False):
                        concluidos += 1
                else:
                    if info and info != '':
                        concluidos += 1
            progresso = (concluidos / total_itens * 100) if total_itens > 0 else 0
            progressos.append(progresso)
        except:
            progressos.append(0)
    
    progresso_medio = sum(progressos) / len(progressos) if progressos else 0
    ufs = Counter(u.uf for u in unidades)
    tipos = Counter(u.tipo for u in unidades)
    
    atrasos_por_categoria = {cat: 0 for cat in CATEGORIAS_REQUISITOS.keys()}
    for u in unidades:
        atrasados = verificar_atrasados(u.checklist_status)
        for item_atrasado in atrasados:
            for cat, itens in CATEGORIAS_REQUISITOS.items():
                for item_config in itens:
                    if item_config['nome'] == item_atrasado['nome']:
                        atrasos_por_categoria[cat] += 1
    
    hoje = date.today()
    proximos_vencimentos = []
    for u in unidades:
        try:
            dados = json.loads(u.checklist_status) if u.checklist_status else {}
            for item_nome, info in dados.items():
                if isinstance(info, dict):
                    previsao = info.get('previsao', '')
                    concluido = info.get('concluido', False)
                    if previsao and not concluido:
                        data_prev = date.fromisoformat(previsao)
                        dias_para_vencer = (data_prev - hoje).days
                        if 0 <= dias_para_vencer <= 7:
                            proximos_vencimentos.append({
                                'unidade': u.nome,
                                'item': item_nome,
                                'data': previsao,
                                'dias': dias_para_vencer
                            })
        except:
            pass
    
    proximos_vencimentos.sort(key=lambda x: x['dias'])
    
    return render_template('dashboard.html',
                           total=total,
                           abertas=abertas,
                           em_processo=em_processo,
                           fechadas=fechadas,
                           progresso_medio=round(progresso_medio, 1),
                           ufs=dict(ufs),
                           tipos=dict(tipos),
                           atrasos_por_categoria=atrasos_por_categoria,
                           proximos_vencimentos=proximos_vencimentos[:10],
                           status_unidade_opts=STATUS_UNIDADE,
                           tipos_unidade=TIPOS_UNIDADE)

@app.route('/deletar/<int:id>', methods=['POST'])
def deletar(id):
    unidade = Unidade.query.get_or_404(id)
    db.session.delete(unidade)
    db.session.commit()
    return redirect(url_for('index'))

def encontrar_nome_por_id(id_item):
    for categoria, itens in CATEGORIAS_REQUISITOS.items():
        for item_config in itens:
            if gerar_id_seguro(item_config['nome']) == id_item:
                return item_config['nome']
    return None

with app.app_context():
    db.create_all()

@app.context_processor
def utility_processor():
    def now():
        return datetime.now()
    return dict(now=now)

# ✅ CORREÇÃO: __name__ e __main__ com underscores
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)