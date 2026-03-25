# 🔧 Guia de Integração dos Novos Módulos

## 📌 Resumo de Mudanças no app.py

O arquivo `app.py` foi **refatorado de forma retrocompatível**. Aqui estão as mudanças-chave:

### ✅ Alterações Já Implementadas

1. **Removido prints de credenciais**
   ```python
   # ANTES (⚠️ INSEGURO)
   print("MAIL_USERNAME:", os.getenv("MAIL_USERNAME"))
   print("MAIL_PASSWORD:", os.getenv("MAIL_PASSWORD"))
   
   # DEPOIS (✅ SEGURO)
   import logging
   logger = logging.getLogger(__name__)
   # Nenhum print de credenciais
   ```

2. **Removida duplicação de registrar_log()**
   ```python
   # ANTES (⚠️ DUPLICADO)
   def registrar_log(unidade_id, etapa, status, ...):
       # primeira versão
   
   def registrar_log(unidade_id, etapa, acao, ...):  # DUPLICADO!
       # segunda versão
   
   # DEPOIS (✅ UNIFICADO)
   def registrar_log(unidade_id, etapa, acao, observacao=None):
       """Versão corrigida com logging"""
       try:
           log = LogEtapa(...)
           db.session.add(log)
           db.session.commit()
           logger.info(f"Log registrado: ...")
       except Exception as e:
           logger.error(f"Erro ao registrar log: {str(e)}")
           db.session.rollback()
   ```

3. **Retry logic em enviar_email_async()**
   ```python
   # ANTES (⚠️ SEM RETRY)
   def enviar_email_async(app_context, msg):
       try:
           mail.send(msg)
           print("✅ Email enviado")
       except Exception as e:
           print("❌ ERRO", str(e))
           return False
   
   # DEPOIS (✅ COM RETRY)
   def enviar_email_async(app_context, msg, retries=3):
       for tentativa in range(retries):
           try:
               mail.send(msg)
               logger.info("✅ Email enviado")
               return True
           except Exception as e:
               if tentativa < retries - 1:
                   logger.warning(f"Tentativa {tentativa + 1}/{retries}...")
                   import time
                   time.sleep(2 ** tentativa)  # Exponential backoff
               else:
                   logger.error(f"❌ Falha após {retries} tentativas")
                   return False
   ```

4. **Validação centralizada de email**
   ```python
   # ANTES (⚠️ ESPALHADO)
   # No function enviar_email:
   if re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
   
   # Em outro lugar (gerenciar):
   if item_config['campo'] == 'email' and valor:
       padrao_email = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
   
   # DEPOIS (✅ CENTRALIZADO)
   def validar_email(email):
       """Função reutilizável"""
       padrao = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
       return re.match(padrao, email) is not None
   ```

---

## 🎯 Próximos Passos (Integração Gradual)

### Fase 1: Usar Config (Opcional)

Se desejar centralizar configurações:

```python
# No início do app.py, substituir:
# basedir = os.path.abspath(...)
# load_dotenv(...)
# app.config['...'] = ...

# Por:
from config import get_config

app = Flask(__name__, ...)
app.config.from_object(get_config())  # ← Carrega tudo de uma vez
```

### Fase 2: Usar Models (Opcional)

Se desejar usar os modelos organizados:

```python
# ANTES (app.py linha 1)
from flask_sqlalchemy import SQLAlchemy
db = SQLAlchemy(app)

class Unidade(db.Model):
    # ...

class LogEtapa(db.Model):
    # ...

# DEPOIS (app.py linha 1)
from models import db, Unidade, LogEtapa
db.init_app(app)
```

### Fase 3: Usar Utils (Recomendado)

Substituir funções duplicadas por utils:

```python
# ANTES
def gerar_id_seguro(texto):
    texto_limpo = re.sub(r'[^\w\s]', '', texto)
    texto_limpo = re.sub(r'\s+', '_', texto_limpo)
    return texto_limpo.lower()

# DEPOIS
from utils import gerar_id_seguro
```

### Fase 4: Usar Email Service (Recomendado)

Usar o novo serviço de email:

```python
from email_service import email_service

# Na inicialização
email_service.init_app(app, mail)

# Na função enviar_email (substituir implementação):
def enviar_email(destinatarios, assunto, corpo_html, corpo_text=None):
    return email_service.enviar(
        destinatarios=destinatarios,
        assunto=assunto,
        corpo_html=corpo_html,
        corpo_text=corpo_text,
        async_envio=True
    )
```

### Fase 5: Usar Forms (Recomendado)

Integrar validação em rotas:

```python
from forms import AdicionarUnidadeForm

@app.route('/adicionar', methods=['GET', 'POST'])
def adicionar():
    form = AdicionarUnidadeForm()
    
    if request.method == 'POST':
        if form.validate_on_submit():  # Valida automaticamente
            nova_unidade = Unidade(
                nome=form.nome.data,
                cidade=form.cidade.data,
                uf=form.uf.data,
                tipo=form.tipo.data,
                status_unidade=form.status_unidade.data
            )
            db.session.add(nova_unidade)
            db.session.commit()
            return redirect(url_for('index'))
        else:
            # form.errors contém os erros
            for field, errors in form.errors.items():
                for error in errors:
                    logger.warning(f"Erro em {field}: {error}")
    
    return render_template('adicionar.html', form=form, ...)
```

---

## 📝 Template HTML Atualizado (Exemplo)

Se usar Flask-WTF em template:

```html
<!-- ANTES (manual) -->
<form method="POST">
    <input type="text" name="nome" required>
    <input type="email" name="email" pattern="...">
    <button type="submit">Enviar</button>
</form>

<!-- DEPOIS (com Flask-WTF) -->
<form method="POST" novalidate>
    {{ form.hidden_tag() }}  <!-- CSRF token -->
    
    {{ form.nome.label }}
    {{ form.nome(size=32) }}
    {% if form.nome.errors %}
        <ul class="errors">
        {% for error in form.nome.errors %}
            <li>{{ error }}</li>
        {% endfor %}
        </ul>
    {% endif %}
    
    {{ form.submit() }}
</form>
```

---

## 🔄 Compatibilidade

### ✅ O que FUNCIONA sem mudanças:
- Todas as rotas existentes
- Todos os templates
- Banco de dados atual
- Lógica de negócio

### ⚠️ O que PODE ser melhorado:
- Validação de formulários (use forms.py)
- Envio de email (use email_service.py)
- Organização de código (use utils.py)
- Configurações (use config.py)

### ❌ O que FOI CORRIGIDO:
- Remoção de prints de credenciais
- Duplicação de registrar_log()
- Falta de retry em emails
- Validação de email espalhada

---

## 📦 Instalação de Dependências Novas

```bash
# Instalar as novas dependências
pip install Flask-WTF==1.2.1 WTForms==3.1.1

# Ou, se usar requirements.txt
pip install -r requirements.txt
```

---

## 🧪 Teste Rápido

Para verificar se tudo está funcionando:

```python
# 1. Testar logging
python -c "import logging; logger = logging.getLogger(); logger.info('OK')"

# 2. Testar validação
python -c "from utils import gerar_id_seguro; print(gerar_id_seguro('Teste @#!'))"

# 3. Testar models
python -c "from models import Unidade, LogEtapa; print('Models OK')"

# 4. Testar forms
python -c "from forms import AdicionarUnidadeForm; print('Forms OK')"

# 5. Testar email_service
python -c "from email_service import email_service; print('EmailService OK')"

# 6. Testar config
python -c "from config import get_config; print(get_config().__name__)"
```

---

## 💡 Dicas Importantes

1. **Continue usando app.py como está** - Funciona normalmente
2. **Adicione novos módulos gradualmente** - Não precisa refatorar tudo de uma vez
3. **Use logging em vez de print()** - Para debug e produção
4. **Teste novas features** - Use pytest se quiser adicionar testes
5. **Revise emails enviados** - O retry logic os reenvia automaticamente

---

## ❓ FAQ

**P: Preciso refatorar todo o app.py?**
R: Não! As mudanças são opcionais. O código existente funciona.

**P: Como faço para usar Flask-WTF?**
R: Veja a Fase 5 acima. É gradual.

**P: O que fazer com o cache anterior (ultimo_envio)?**
R: Continua funcionando. Será migrado para Redis depois (Sugestão 5).

**P: Como isso afeta produção?**
R: Não afeta! Todas as mudanças são retrocompatíveis.

**P: E se não usar os novos módulos?**
R: Tudo continua funcionando normalmente com app.py refatorado.
