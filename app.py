import os
from flask import Flask, render_template, request, redirect, url_for, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
import json
import re
from datetime import datetime, date, timedelta
from collections import Counter
from flask_mail import Mail, Message
import threading
import traceback
from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv




basedir = os.path.abspath(os.path.dirname(__file__))

load_dotenv(os.path.join(basedir, ".env"))
print("MAIL_USERNAME:", os.getenv("MAIL_USERNAME"))
print("MAIL_PASSWORD:", os.getenv("MAIL_PASSWORD"))


app = Flask(
    __name__,
    template_folder=os.path.join(basedir, 'templates'),
    static_folder=os.path.join(basedir, 'static') if os.path.exists(os.path.join(basedir, 'static')) else None
)


@app.context_processor
def utility_processor():
    return dict(
        now=datetime.now,
        email_franqueado=os.environ.get('EMAIL_FRANQUEADO', 'Não configurado'),
        email_time=os.environ.get('EMAIL_TIME', 'Não configurado')
    )


# Configuração do Banco de Dados
database_url = os.environ.get('DATABASE_URL')
if database_url:
    database_url = database_url.replace('postgres://', 'postgresql://', 1)
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
    print("✅ Usando PostgreSQL (Produção)")
    
    if 'postgresql' in database_url and 'asyncpg' not in database_url:
        database_url = database_url.replace('postgresql://', 'postgresql+asyncpg://')
    
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'pool_pre_ping': True,
        'pool_recycle': 300,
        'connect_args': {
            'connect_timeout': 10
        }
    }
else:
    # Ambiente de desenvolvimento (local)
    db_path = os.path.join(basedir, 'instance', 'checklist.db')
    # Garante que o diretório instance existe
    os.makedirs(os.path.join(basedir, 'instance'), exist_ok=True)
    
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'pool_pre_ping': True,
    }
    print(f"✅ Usando SQLite (Desenvolvimento Local): {db_path}")

# Configurações comuns
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'chave-desenvolvimento-local-temporaria')

# Configuração do Mail - CORRIGIDA
app.config['MAIL_SERVER'] = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
app.config['MAIL_PORT'] = int(os.environ.get('MAIL_PORT', 587))
app.config['MAIL_USE_TLS'] = os.environ.get('MAIL_USE_TLS', 'True').lower() == 'true'
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_DEFAULT_SENDER', app.config['MAIL_USERNAME'])
app.config['MAIL_MAX_EMAILS'] = None

db = SQLAlchemy(app)
migrate = Migrate(app, db)
mail = Mail(app)

# Cache para evitar emails duplicados
ultimo_envio = {}

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
    

class LogEtapa(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    unidade_id = db.Column(db.Integer)
    etapa = db.Column(db.String(200))
    acao = db.Column(db.String(50))
    observacao = db.Column(db.Text)
    data = db.Column(db.DateTime, default=datetime.utcnow)



    @property
    def status(self):
        try:
            return json.loads(self.checklist_status) if self.checklist_status else {}
        except:
            return {}

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

# ==================== FUNÇÕES DE EMAIL CORRIGIDAS ====================

def enviar_email_async(app_context, msg):
    """Envia email em background para não travar a aplicação"""
    try:
        with app_context:
            mail.send(msg)
            print(f"✅ Email enviado com sucesso para: {', '.join(msg.recipients)}")
            return True
    except Exception as e:
        print(f"❌ ERRO DETALHADO AO ENVIAR EMAIL:")
        traceback.print_exc()
        print(f"Configuração atual: Servidor={app.config['MAIL_SERVER']}, Porta={app.config['MAIL_PORT']}, TLS={app.config['MAIL_USE_TLS']}")
        return False

def enviar_email(destinatarios, assunto, corpo_html, corpo_text=None):
    """Função principal para enviar emails"""
    try:
        # Validar configuração
        if not app.config['MAIL_USERNAME'] or not app.config['MAIL_PASSWORD']:
            print("❌ MAIL_USERNAME ou MAIL_PASSWORD não configurados")
            return False, "Configuração de email incompleta"
        
        # Garantir que destinatários seja uma lista
        if isinstance(destinatarios, str):
            destinatarios = [d.strip() for d in destinatarios.split(',') if d.strip()]
        
        # Validar emails
        emails_validos = []
        for email in destinatarios:
            if re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
                emails_validos.append(email)
            else:
                print(f"Email inválido ignorado: {email}")
        
        if not emails_validos:
            print("Nenhum email válido para enviar")
            return False, "Nenhum email válido"
        
        msg = Message(
            subject=assunto,
            recipients=emails_validos,
            html=corpo_html,
            body=corpo_text or "Por favor, visualize este email em um cliente HTML."
        )

        
        # Envia em background
        app_context = app.app_context()
        thread = threading.Thread(target=enviar_email_async, args=(app_context, msg))
        thread.daemon = True
        thread.start()
        
        return True, f"Enviando para: {', '.join(emails_validos)}"
        
    except Exception as e:
        print(f"Erro ao preparar email: {str(e)}")
        traceback.print_exc()
        return False, str(e)

def registrar_log(unidade_id, etapa, status, observacao=None):

    log = LogEtapa(
        unidade_id=unidade_id,
        etapa=etapa,
        acao=status,
        observacao=observacao
    )



    db.session.add(log)
    db.session.commit()

def registrar_log(unidade_id, etapa, acao, observacao=None):

    log = LogEtapa(
        unidade_id=unidade_id,
        etapa=etapa,
        acao=acao,
        observacao=observacao
    )

    db.session.add(log)
    db.session.commit()


def verificar_prazos_e_notificar(unidade, status_salvo):
    """Verifica itens próximos ao vencimento e envia notificações"""
    hoje = datetime.now().date()
    alertas = []
    
    for item_nome, item_valor in status_salvo.items():
        if isinstance(item_valor, dict):
            previsao = item_valor.get('previsao', '')
            concluido = item_valor.get('concluido', False)
            
            if previsao and not concluido:
                try:
                    data_previsao = datetime.strptime(previsao, '%Y-%m-%d').date()
                    dias_para_vencer = (data_previsao - hoje).days
                    
                    # Alerta se vencer hoje ou amanhã
                    if 0 <= dias_para_vencer <= 1:
                        alertas.append({
                            'item': item_nome,
                            'dias': dias_para_vencer,
                            'previsao': previsao,
                            'status': 'vencimento'
                        })
                    # Alerta se já venceu
                    elif dias_para_vencer < 0:
                        alertas.append({
                            'item': item_nome,
                            'dias': abs(dias_para_vencer),
                            'previsao': previsao,
                            'status': 'vencido'
                        })
                except:
                    pass
    
    return alertas

def notificar_aprovacoes_pendentes(unidade, status_salvo):
    """Verifica aprovações pendentes e notifica a equipe"""
    pendentes = []
    
    for item_nome, item_valor in status_salvo.items():
        if 'aprovacao_' in item_nome or item_valor == 'pendente':
            pendentes.append(item_nome.replace('aprovacao_', ''))
    
    return pendentes

def verificar_todas_unidades():
    """Verifica todas as unidades e envia notificações"""
    with app.app_context():
        unidades = Unidade.query.all()
        hoje = date.today()
        
        for unidade in unidades:
            status_salvo = unidade.checklist_status

            alertas = verificar_prazos_e_notificar(unidade, status_salvo)
            
            # Envia se houver alertas (evita spam - a cada 24h)
            chave_cache = f"unidade_{unidade.id}_{hoje}"
            if alertas and ultimo_envio.get(chave_cache) != hoje:
                email_franqueado = os.environ.get('EMAIL_FRANQUEADO')
                if email_franqueado:
                    html = render_template('emails/alerta_prazo.html', 
                                         unidade=unidade, 
                                         alertas=alertas)
                    enviar_email(email_franqueado, f"🔔 Resumo de Prazos - {unidade.nome}", html)
                    ultimo_envio[chave_cache] = hoje

# Inicia o scheduler (apenas se não estiver no modo debug ou em produção)
if not app.debug or os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
    scheduler = BackgroundScheduler()
    scheduler.add_job(func=verificar_todas_unidades, trigger="interval", hours=24)
    scheduler.start()

# ==================== ROTAS ====================

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

        registrar_log(
            nova_unidade.id,
            "Unidade criada",
            "criado",
            "Nova unidade adicionada ao sistema"
        )

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

        registrar_log(
            unidade.id,
            "Checklist atualizado",
            "update",
            "Checklist da unidade foi atualizado"
        )

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
                           gerar_id_seguro=gerar_id_seguro,
                           email_franqueado=os.environ.get('EMAIL_FRANQUEADO', 'Não configurado'),
                           email_time=os.environ.get('EMAIL_TIME', 'Não configurado'))

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

@app.route('/notificar/<int:unidade_id>', methods=['POST'])
def notificar_unidade(unidade_id):
    
    unidade = Unidade.query.get_or_404(unidade_id)

    status_salvo = json.loads(unidade.checklist_status or "{}")
    
    # Pega os dados do POST
    data = request.get_json()
    if not data:
        return {'success': False, 'message': 'Dados não recebidos'}
    
    tipo = data.get('tipo', '')
    emails_manuais = data.get('emails', '')
    
    # Se for apenas preview, retorna contagem
    if tipo == 'preview':
        alertas = verificar_prazos_e_notificar(unidade, status_salvo)
        pendentes = notificar_aprovacoes_pendentes(unidade, status_salvo)
        return {
            'success': True,
            'alertas': len(alertas),
            'pendentes': len(pendentes)
        }
    
    # Lista de destinatários
    destinatarios = []
    
    if emails_manuais:
        destinatarios = [email.strip() for email in emails_manuais.split(',') if email.strip()]
    else:
        if tipo in ['franqueado', 'todos']:
            email_franqueado = os.environ.get('EMAIL_FRANQUEADO')
            if email_franqueado:
                destinatarios.append(email_franqueado)
        
        if tipo in ['time', 'todos']:
            email_time = os.environ.get('EMAIL_TIME')
            if email_time:
                destinatarios.append(email_time)
    
    if not destinatarios:
        return {'success': False, 'message': 'Nenhum destinatário configurado'}
    
    # Verifica prazos e aprovações
    alertas = []
    pendentes = []
    hoje = datetime.now().date()
    
    for item_nome, item_valor in status_salvo.items():
        if isinstance(item_valor, dict):
            previsao = item_valor.get('previsao', '')
            concluido = item_valor.get('concluido', False)
            
            if previsao and not concluido:
                try:
                    data_previsao = datetime.strptime(previsao, '%Y-%m-%d').date()
                    dias_para_vencer = (data_previsao - hoje).days
                    
                    if dias_para_vencer < 0:
                        alertas.append({
                            'item': item_nome,
                            'dias': abs(dias_para_vencer),
                            'previsao': previsao,
                            'status': 'vencido',
                            'tipo': 'prazo'
                        })
                    elif dias_para_vencer <= 2:
                        alertas.append({
                            'item': item_nome,
                            'dias': dias_para_vencer,
                            'previsao': previsao,
                            'status': 'vencimento',
                            'tipo': 'prazo'
                        })
                except:
                    pass
        
        if 'Aprovação' in item_nome or 'aprovacao' in item_nome.lower():
            if item_valor == 'pendente':
                pendentes.append({
                    'item': item_nome,
                    'tipo': 'aprovacao'
                })
    
    if not alertas and not pendentes:
        return {'success': False, 'message': 'Nenhum item para notificar'}
    
    # Construir HTML dos itens
    prazos_html = ""
    for alerta in alertas:
        classe = "vencido" if alerta['status'] == 'vencido' else "alerta"
        icone = "⛔" if alerta['status'] == 'vencido' else "⚠️"
        texto_dias = f"VENCIDO há {alerta['dias']} dias" if alerta['status'] == 'vencido' else f"Vence em {alerta['dias']} dias"
        cor = "#dc3545" if alerta['status'] == 'vencido' else "#ffc107"
        
        prazos_html += f"""
        <div style="background-color: #f8f9fa; border-left: 4px solid {cor}; padding: 15px; margin: 10px 0; border-radius: 4px;">
            <div style="display: flex; align-items: center; gap: 10px;">
                <span style="font-size: 20px;">{icone}</span>
                <div>
                    <strong style="font-size: 16px;">{alerta['item']}</strong><br>
                    <span style="color: {cor}; font-weight: bold;">{texto_dias}</span><br>
                    <small style="color: #6c757d;">📅 Previsão: {alerta['previsao']}</small>
                </div>
            </div>
        </div>
        """
    
    aprovacoes_html = ""
    for item in pendentes:
        aprovacoes_html += f"""
        <div style="background-color: #e2f3ff; border-left: 4px solid #0d6efd; padding: 15px; margin: 10px 0; border-radius: 4px;">
            <div style="display: flex; align-items: center; gap: 10px;">
                <span style="font-size: 20px;">⏳</span>
                <div>
                    <strong style="font-size: 16px;">{item['item']}</strong><br>
                    <span style="color: #0d6efd;">Pendente de Aprovação</span>
                </div>
            </div>
        </div>
        """
    
    data_atual = datetime.now().strftime('%d/%m/%Y %H:%M')
    
    # Montar corpo do email (sem Jinja2, apenas Python)
    corpo_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            body {{ font-family: 'Segoe UI', Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ 
                background: linear-gradient(135deg, #dc0032 0%, #b8002a 100%);
                color: white; 
                padding: 30px; 
                border-radius: 10px 10px 0 0;
                text-align: center;
            }}
            .header h1 {{ margin: 0; font-size: 28px; }}
            .header p {{ margin: 10px 0 0; opacity: 0.9; }}
            .content {{ background: white; padding: 30px; border-radius: 0 0 10px 10px; }}
            .info-unidade {{ 
                background: #f8f9fa; 
                padding: 20px; 
                border-radius: 8px; 
                margin-bottom: 25px;
                border: 1px solid #dee2e6;
            }}
            .info-unidade h3 {{ margin: 0 0 15px; color: #dc0032; }}
            .info-grid {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 15px; }}
            .info-item {{ margin-bottom: 10px; }}
            .info-label {{ font-weight: bold; color: #6c757d; font-size: 14px; }}
            .info-value {{ font-size: 16px; }}
            .badge {{
                display: inline-block;
                padding: 5px 10px;
                border-radius: 20px;
                font-size: 12px;
                font-weight: bold;
                text-transform: uppercase;
            }}
            .badge-processo {{ background: #ffc107; color: #000; }}
            .badge-pronta {{ background: #17a2b8; color: white; }}
            .badge-aberta {{ background: #28a745; color: white; }}
            .badge-fechada {{ background: #6c757d; color: white; }}
            .secao {{ margin-top: 30px; }}
            .secao h4 {{ 
                color: #dc0032; 
                border-bottom: 2px solid #dc0032; 
                padding-bottom: 10px;
                margin-bottom: 20px;
            }}
            .botao {{
                display: inline-block;
                background: #dc0032;
                color: white;
                padding: 12px 30px;
                text-decoration: none;
                border-radius: 5px;
                font-weight: bold;
                margin-top: 25px;
                text-align: center;
            }}
            .botao:hover {{ background: #b8002a; }}
            .footer {{
                margin-top: 30px;
                padding-top: 20px;
                border-top: 1px solid #dee2e6;
                text-align: center;
                color: #6c757d;
                font-size: 12px;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>📋 Checklist de Abertura</h1>
                <p>Notificação Automática</p>
            </div>
            
            <div class="content">
                <div class="info-unidade">
                    <h3>📍 {unidade.nome}</h3>
                    <div class="info-grid">
                        <div class="info-item">
                            <div class="info-label">Cidade/UF</div>
                            <div class="info-value">{unidade.cidade} - {unidade.uf}</div>
                        </div>
                        <div class="info-item">
                            <div class="info-label">Tipo</div>
                            <div class="info-value">{TIPOS_UNIDADE.get(unidade.tipo, unidade.tipo)}</div>
                        </div>
                        <div class="info-item">
                            <div class="info-label">Status da Unidade</div>
                            <div class="info-value">
                                <span class="badge badge-{unidade.status_unidade}">
                                    {STATUS_UNIDADE.get(unidade.status_unidade, {'label': unidade.status_unidade})['label']}
                                </span>
                            </div>
                        </div>
                        <div class="info-item">
                            <div class="info-label">Data/Hora</div>
                            <div class="info-value">{data_atual}</div>
                        </div>
                    </div>
                </div>
                
                {f'<div class="secao"><h4>🔔 Prazos ({len(alertas)})</h4>{prazos_html}</div>' if alertas else ''}
                
                {f'<div class="secao"><h4>⏳ Aprovações Pendentes ({len(pendentes)})</h4>{aprovacoes_html}</div>' if pendentes else ''}
                
                <div style="text-align: center;">
                    <a href="https://seudominio.com/gerenciar/{unidade.id}" class="botao">
                        🔍 Acessar Checklist Completo
                    </a>
                </div>
                
                <div class="footer">
                    <p>Este é um email automático do sistema de Checklist.</p>
                    <p>© {datetime.now().year} - Todos os direitos reservados</p>
                </div>
            </div>
        </div>
    </body>
    </html>
    """
    
    # Definir assunto do email
    if alertas and pendentes:
        assunto = f"🔔 Prazos e Aprovações Pendentes - {unidade.nome}"
    elif alertas:
        assunto = f"🔔 {len(alertas)} Item(ns) com Prazo - {unidade.nome}"
    elif pendentes:
        assunto = f"⏳ {len(pendentes)} Aprovação(ões) Pendente(s) - {unidade.nome}"
    else:
        assunto = f"📋 Resumo do Checklist - {unidade.nome}"
    
    # Envia o email
    success, message = enviar_email(destinatarios, assunto, corpo_html)
    
    return {
        'success': success,
        'message': message,
        'alertas': len(alertas),
        'pendentes': len(pendentes),
        'destinatarios': destinatarios
    }

# ==================== TESTE DE EMAIL ====================

@app.route('/testar-email')
def testar_email():
    """Rota para testar configuração de email"""
    try:
        destinatario = os.environ.get('MAIL_USERNAME')
        if not destinatario:
            return {
                'success': False,
                'message': 'MAIL_USERNAME não configurado'
            }
        
        assunto = "🔧 Teste de Configuração de Email"
        corpo = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; }}
                .success {{ 
                    background: #d4edda; 
                    border: 1px solid #c3e6cb; 
                    color: #155724; 
                    padding: 20px; 
                    border-radius: 5px;
                }}
            </style>
        </head>
        <body>
            <div class="success">
                <h2>✅ Teste de Email - Checklist</h2>
                <p>Se você está vendo esta mensagem, a configuração de email está funcionando corretamente!</p>
                <p><strong>Data/Hora:</strong> {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}</p>
                <p><strong>Servidor:</strong> {app.config['MAIL_SERVER']}</p>
                <p><strong>Porta:</strong> {app.config['MAIL_PORT']}</p>
                <p><strong>TLS:</strong> {app.config['MAIL_USE_TLS']}</p>
            </div>
        </body>
        </html>
        """
        
        success, message = enviar_email(destinatario, assunto, corpo)
        
        if success:
            return {'success': True, 'message': f'Email de teste enviado para {destinatario}'}
        else:
            return {'success': False, 'message': f'Falha ao enviar: {message}'}
            
    except Exception as e:
        return {'success': False, 'message': f'Erro: {str(e)}'}

# ==================== STATUS EMAIL ====================

@app.route('/status-email')
def status_email():
    """Verifica configuração atual de email"""
    config = {
        'MAIL_SERVER': app.config['MAIL_SERVER'],
        'MAIL_PORT': app.config['MAIL_PORT'],
        'MAIL_USE_TLS': app.config['MAIL_USE_TLS'],
        'MAIL_USERNAME': app.config['MAIL_USERNAME'],
        'MAIL_DEFAULT_SENDER': app.config['MAIL_DEFAULT_SENDER'],
        'EMAIL_FRANQUEADO': os.environ.get('EMAIL_FRANQUEADO', 'Não configurado'),
        'EMAIL_TIME': os.environ.get('EMAIL_TIME', 'Não configurado'),
        'MAIL_PASSWORD': '******' if app.config['MAIL_PASSWORD'] else 'Não configurado'
    }
    return {'success': True, 'config': config}


@app.route("/logs/<int:unidade_id>")
def ver_logs(unidade_id):

    logs = LogEtapa.query.filter_by(unidade_id=unidade_id)\
        .order_by(LogEtapa.data.desc()).all()

    unidade = Unidade.query.get_or_404(unidade_id)

    return render_template("logs.html", logs=logs, unidade=unidade)

# ==================== INICIALIZAÇÃO ====================

with app.app_context():
    db.create_all()
    print("✅ Banco de dados inicializado")

@app.context_processor
def utility_processor():
    def now():
        return datetime.now()
    return dict(now=now)


# ==================== EXECUÇÃO ====================

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"\n{'='*50}")
    print(f"🚀 Servidor iniciado em: http://localhost:{port}")
    print(f"📧 Status do Email: {app.config['MAIL_USERNAME']}")
    print(f"{'='*50}\n")
    
    app.run(host='0.0.0.0', port=port, debug=False)
