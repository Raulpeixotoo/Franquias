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
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


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
    logger.info("✅ Usando PostgreSQL (Produção)")
    
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
    logger.info(f"✅ Usando SQLite (Desenvolvimento Local): {db_path}")

# Configurações 
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'chave-desenvolvimento-local-temporaria')

# Configuração do Mail
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

def enviar_email_async(app_context, msg, retries=3):
    """Envia email em background com retry logic"""
    for tentativa in range(retries):
        try:
            with app_context:
                mail.send(msg)
                logger.info(f"✅ Email enviado com sucesso para: {', '.join(msg.recipients)}")
                return True
        except Exception as e:
            if tentativa < retries - 1:
                logger.warning(f"Tentativa {tentativa + 1}/{retries} falhou. Tentando novamente...")
                import time
                time.sleep(2 ** tentativa)  # Exponential backoff
            else:
                logger.error(f"❌ Falha ao enviar email após {retries} tentativas: {str(e)}")
                return False

def validar_email(email):
    """Valida formato de email"""
    padrao = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(padrao, email) is not None

def enviar_email(destinatarios, assunto, corpo_html, corpo_text=None):
    """Função principal para enviar emails"""
    try:
        # Validar configuração
        if not app.config['MAIL_USERNAME'] or not app.config['MAIL_PASSWORD']:
            logger.error("❌ MAIL_USERNAME ou MAIL_PASSWORD não configurados")
            return False, "Configuração de email incompleta"
        
        # Garantir que destinatários seja uma lista
        if isinstance(destinatarios, str):
            destinatarios = [d.strip() for d in destinatarios.split(',') if d.strip()]
        
        # Validar emails
        emails_validos = []
        for email in destinatarios:
            if validar_email(email):
                emails_validos.append(email)
            else:
                logger.warning(f"Email inválido ignorado: {email}")
        
        if not emails_validos:
            logger.warning("Nenhum email válido para enviar")
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
        
        logger.info(f"Email agendado para envio: {', '.join(emails_validos)}")
        return True, f"Enviando para: {', '.join(emails_validos)}"
        
    except Exception as e:
        logger.error(f"Erro ao preparar email: {str(e)}")
        return False, str(e)

def registrar_log(unidade_id, etapa, acao, observacao=None):
    """Registra um log de etapa para auditoria"""
    try:
        log = LogEtapa(
            unidade_id=unidade_id,
            etapa=etapa,
            acao=acao,
            observacao=observacao
        )
        db.session.add(log)
        db.session.commit()
        logger.info(f"Log registrado: Unidade {unidade_id} - {etapa} - {acao}")
    except Exception as e:
        logger.error(f"Erro ao registrar log: {str(e)}")
        db.session.rollback()


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

# Dashboard removido - usar /adm para gerenciar backups

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
    """Verifica configuração atual de email e retorna diagnóstico completo"""
    mail_configured = bool(app.config.get('MAIL_USERNAME') and app.config.get('MAIL_PASSWORD'))
    
    diagnostico = {
        'configurado': mail_configured,
        'config': {
            'MAIL_SERVER': app.config['MAIL_SERVER'],
            'MAIL_PORT': app.config['MAIL_PORT'],
            'MAIL_USE_TLS': app.config['MAIL_USE_TLS'],
            'MAIL_USERNAME': app.config['MAIL_USERNAME'] or '❌ NÃO CONFIGURADO',
            'MAIL_PASSWORD': '✅ Configurado' if app.config['MAIL_PASSWORD'] else '❌ NÃO CONFIGURADO',
            'MAIL_DEFAULT_SENDER': app.config['MAIL_DEFAULT_SENDER'],
            'EMAIL_FRANQUEADO': os.environ.get('EMAIL_FRANQUEADO', 'Não configurado'),
            'EMAIL_TIME': os.environ.get('EMAIL_TIME', 'Não configurado'),
        },
        'mensagem': ''
    }
    
    if not mail_configured:
        diagnostico['mensagem'] = (
            '❌ Email NÃO está configurado. '
            'Adicione MAIL_USERNAME e MAIL_PASSWORD nas variáveis de ambiente do Render.'
        )
    else:
        diagnostico['mensagem'] = '✅ Email está configurado corretamente'
    
    return diagnostico


@app.route("/logs/<int:unidade_id>")
def ver_logs(unidade_id):

    logs = LogEtapa.query.filter_by(unidade_id=unidade_id)\
        .order_by(LogEtapa.data.desc()).all()

    unidade = Unidade.query.get_or_404(unidade_id)

    return render_template("logs.html", logs=logs, unidade=unidade)

# ==================== PAINEL ADMINISTRATIVO (BACKUP) ====================

def autenticar_adm(senha):
    """Verifica autenticação do painel ADM"""
    senha_correta = os.environ.get('ADM_PASSWORD', 'admin123')
    return senha == senha_correta

@app.route('/adm', methods=['GET', 'POST'])
def adm():
    """Painel administrativo com backup/restore"""
    # Se for POST, validar senha
    if request.method == 'POST':
        senha = request.form.get('senha', '')
        if not autenticar_adm(senha):
            return render_template('adm.html', 
                                 erro='Senha incorreta!',
                                 autenticado=False), 401
    
    # Verificar se está autenticado (via sessão)
    autenticado = request.args.get('auth') == '1' or \
                  request.cookies.get('adm_auth') == 'true'
    
    if request.method == 'POST' and autenticar_adm(request.form.get('senha', '')):
        autenticado = True
    
    if not autenticado:
        return render_template('adm.html', 
                             erro=None,
                             autenticado=False)
    
    # Inicializar serviço de backup
    from backup_service import init_backup_service
    backup_service = init_backup_service(app)
    
    # Listar backups disponíveis
    backups = backup_service.listar_backups()
    
    return render_template('adm.html',
                         autenticado=True,
                         backups=backups,
                         erro=None)

@app.route('/adm/criar-backup')
def criar_backup():
    """Cria um novo backup"""
    if request.cookies.get('adm_auth') != 'true':
        return redirect(url_for('adm'))
    
    from backup_service import init_backup_service
    backup_service = init_backup_service(app)
    
    sucesso, nome_arquivo = backup_service.criar_backup()
    
    if sucesso:
        logger.info(f"✅ Backup criado: {nome_arquivo}")
        return redirect(url_for('adm', msg='Backup criado com sucesso!'))
    else:
        logger.error(f"❌ Erro ao criar backup: {nome_arquivo}")
        return redirect(url_for('adm', erro=nome_arquivo))

@app.route('/adm/download-backup/<nome_backup>')
def download_backup(nome_backup):
    """Baixa um arquivo de backup como JSON"""
    if request.cookies.get('adm_auth') != 'true':
        return redirect(url_for('adm')), 401
    
    from backup_service import init_backup_service
    backup_service = init_backup_service(app)
    
    # Validar segurança
    if '..' in nome_backup or '/' in nome_backup or '\\' in nome_backup:
        return 'Acesso negado', 403
    
    sucesso, nome_arquivo, conteudo = backup_service.fazer_download_backup(nome_backup)
    
    if not sucesso:
        return 'Backup não encontrado', 404
    
    from flask import send_file
    from io import BytesIO
    
    # Criar objeto filelike
    dados = BytesIO(conteudo)
    
    return send_file(
        dados,
        as_attachment=True,
        download_name=nome_arquivo,
        mimetype='application/json'
    )

@app.route('/adm/restaurar/<nome_backup>', methods=['POST'])
def restaurar_backup(nome_backup):
    """Restaura um backup"""
    if request.cookies.get('adm_auth') != 'true':
        return jsonify({'sucesso': False, 'erro': 'Não autenticado'}), 401
    
    from backup_service import init_backup_service
    backup_service = init_backup_service(app)
    
    # Validar segurança
    if '..' in nome_backup or '/' in nome_backup or '\\' in nome_backup:
        return jsonify({'sucesso': False, 'erro': 'Nome de arquivo inválido'}), 403
    
    sucesso, mensagem = backup_service.restaurar_backup(nome_backup)
    
    if sucesso:
        logger.info(f"✅ Backup restaurado: {nome_backup}")
        return jsonify({'sucesso': True, 'mensagem': mensagem})
    else:
        logger.error(f"❌ Erro ao restaurar: {mensagem}")
        return jsonify({'sucesso': False, 'erro': mensagem}), 400

@app.route('/adm/deletar-backup/<nome_backup>', methods=['POST'])
def deletar_backup(nome_backup):
    """Deleta um backup"""
    if request.cookies.get('adm_auth') != 'true':
        return jsonify({'sucesso': False, 'erro': 'Não autenticado'}), 401
    
    from backup_service import init_backup_service
    backup_service = init_backup_service(app)
    
    # Validar segurança
    if '..' in nome_backup or '/' in nome_backup or '\\' in nome_backup:
        return jsonify({'sucesso': False, 'erro': 'Nome de arquivo inválido'}), 403
    
    sucesso, mensagem = backup_service.deletar_backup(nome_backup)
    
    if sucesso:
        logger.info(f"✅ Backup deletado: {nome_backup}")
        return jsonify({'sucesso': True, 'mensagem': mensagem})
    else:
        logger.error(f"❌ Erro ao deletar: {mensagem}")
        return jsonify({'sucesso': False, 'erro': mensagem}), 400

@app.route('/adm/upload-backup', methods=['POST'])
def upload_backup():
    """Faz upload de um arquivo de backup (JSON)"""
    if request.cookies.get('adm_auth') != 'true':
        return jsonify({'sucesso': False, 'erro': 'Não autenticado'}), 401
    
    if 'arquivo' not in request.files:
        return jsonify({'sucesso': False, 'erro': 'Nenhum arquivo enviado'}), 400
    
    arquivo = request.files['arquivo']
    
    if arquivo.filename == '':
        return jsonify({'sucesso': False, 'erro': 'Arquivo vazio'}), 400
    
    # Aceitar .json ou .db
    if not (arquivo.filename.endswith('.json') or arquivo.filename.endswith('.db')):
        return jsonify({'sucesso': False, 'erro': 'Arquivo deve ser .json ou .db'}), 400
    
    try:
        from backup_service import init_backup_service
        backup_service = init_backup_service(app)
        
        # Ler conteúdo do arquivo
        conteudo = arquivo.read()
        
        # Fazer upload
        sucesso, mensagem = backup_service.fazer_upload_backup(conteudo)
        
        if sucesso:
            logger.info(f"✅ Backup importado: {arquivo.filename}")
            return jsonify({
                'sucesso': True,
                'mensagem': mensagem
            })
        else:
            logger.error(f"❌ Erro ao importar: {mensagem}")
            return jsonify({'sucesso': False, 'erro': mensagem}), 400
    
    except Exception as e:
        logger.error(f"❌ Erro ao fazer upload: {str(e)}")
        return jsonify({'sucesso': False, 'erro': str(e)}), 400

# ==================== INICIALIZAÇÃO ====================

with app.app_context():
    db.create_all()
    logger.info("✅ Banco de dados inicializado")

@app.context_processor
def utility_processor():
    def now():
        return datetime.now()
    return dict(now=now)


# ==================== PAINEL DE DIAGNÓSTICO ====================

@app.route('/diagnostico')
def painel_diagnostico():
    """Painel de diagnóstico com interface visual"""
    return render_template('diagnostico.html')


@app.route('/api/diagnostico')
def api_diagnostico():
    """API com informações de diagnóstico completas"""
    try:
        # Status do Banco de Dados
        db_status = {
            'conectado': True,
            'tipo': 'SQLite' if 'sqlite' in app.config.get('SQLALCHEMY_DATABASE_URI', '').lower() else 'PostgreSQL',
            'unidades_total': Unidade.query.count(),
            'logs_total': LogEtapa.query.count(),
        }
    except Exception as e:
        logger.error(f"❌ Erro ao verificar BD: {str(e)}")
        db_status = {
            'conectado': False,
            'erro': str(e)
        }
    
    try:
        # Status de Email
        email_configurado = bool(app.config.get('MAIL_USERNAME') and app.config.get('MAIL_PASSWORD'))
        email_status = {
            'configurado': email_configurado,
            'server': app.config.get('MAIL_SERVER'),
            'port': app.config.get('MAIL_PORT'),
            'username': app.config.get('MAIL_USERNAME') or 'Não configurado',
        }
    except Exception as e:
        logger.error(f"❌ Erro ao verificar Email: {str(e)}")
        email_status = {'erro': str(e)}
    
    try:
        # Status de Backup
        from backup_service import backups_em_memoria
        backup_status = {
            'funcional': True,
            'backups_total': len(backups_em_memoria),
            'backups': [
                {
                    'nome': backup_id,
                    'tamanho_kb': info['tamanho_bytes'] / 1024,
                    'data': info['criado_em'].isoformat()
                }
                for backup_id, info in list(backups_em_memoria.items())[:5]  # Últimos 5
            ]
        }
    except Exception as e:
        logger.error(f"❌ Erro ao verificar Backup: {str(e)}")
        backup_status = {
            'funcional': False,
            'erro': str(e)
        }
    
    # Compilar diagnóstico completo
    diagnostico = {
        'timestamp': datetime.now().isoformat(),
        'ambiente': os.environ.get('FLASK_ENV', 'development'),
        'banco_dados': db_status,
        'email': email_status,
        'backup': backup_status,
        'sistema': {
            'python_version': '3.12',
            'flask_version': '3.1.3',
            'running': True
        }
    }
    
    return jsonify(diagnostico)


@app.route('/testar-email', methods=['GET', 'POST'])
def testar_email_completo():
    """Testa o envio de email com log detalhado"""
    try:
        # Verificar configuração
        if not app.config.get('MAIL_USERNAME'):
            logger.error("❌ MAIL_USERNAME não configurado")
            return jsonify({
                'sucesso': False,
                'erro': 'MAIL_USERNAME não configurado nas variáveis de ambiente',
                'dica': 'Configure no Render → Environment → MAIL_USERNAME'
            }), 400
        
        if not app.config.get('MAIL_PASSWORD'):
            logger.error("❌ MAIL_PASSWORD não configurado")
            return jsonify({
                'sucesso': False,
                'erro': 'MAIL_PASSWORD não configurado nas variáveis de ambiente',
                'dica': 'Configure no Render → Environment → MAIL_PASSWORD (use Senha App do Gmail)'
            }), 400
        
        logger.info(f"📧 Iniciando teste de email para: {app.config.get('MAIL_DEFAULT_SENDER')}")
        
        # Inicializar serviço de email
        from email_service import EmailService
        email_service = EmailService(app)
        
        # Enviar email de teste
        assunto = "🧪 Email de Teste - Control System"
        corpo = f"""
        <h2>Teste de Email</h2>
        <p>Este é um email de teste do Control System.</p>
        <p><strong>Timestamp:</strong> {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}</p>
        <p><strong>Ambiente:</strong> {os.environ.get('FLASK_ENV', 'development')}</p>
        <p>Se você recebeu este email, o sistema de notificações está funcionando corretamente!</p>
        """
        
        destinatario = app.config.get('MAIL_DEFAULT_SENDER')
        
        sucesso, mensagem = email_service.enviar(
            assunto=assunto,
            corpo_html=corpo,
            destinatarios=destinatario
        )
        
        if sucesso:
            logger.info(f"✅ Email de teste enviado com sucesso para {destinatario}")
            return jsonify({
                'sucesso': True,
                'mensagem': f'Email enviado com sucesso para {destinatario}',
                'timestamp': datetime.now().isoformat()
            })
        else:
            logger.error(f"❌ Falha ao enviar email: {mensagem}")
            return jsonify({
                'sucesso': False,
                'erro': mensagem,
                'dica': 'Verifique o painel /diagnostico para mais detalhes'
            }), 400
    
    except Exception as e:
        logger.error(f"❌ ERRO ao testar email: {str(e)}")
        return jsonify({
            'sucesso': False,
            'erro': str(e),
            'tipo_erro': type(e).__name__,
            'dica': 'Verifique os logs do Render'
        }), 500


# ==================== EXECUÇÃO ====================

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    logger.info(f"\n{'='*50}")
    logger.info(f"🚀 Servidor iniciado em: http://localhost:{port}")
    logger.info(f"📧 Email configurado: {bool(app.config['MAIL_USERNAME'])}")
    logger.info(f"{'='*50}\n")
    
    app.run(host='0.0.0.0', port=port, debug=False)