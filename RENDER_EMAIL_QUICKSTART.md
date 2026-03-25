# ⚡ GUIA RÁPIDO: Configurar Email no Render em 5 Minutos

## 🎯 O QUE FAZER

### **PASSO 1: Gerar Senha de App Gmail (2 min)**
```
1. Clique >>> https://myaccount.google.com/apppasswords
2. Selecione:
   ✓ App: "Mail"
   ✓ Device: "Windows Computer" (ou seu tipo)
3. Copie a senha com 16 caracteres (com espaços)
   Exemplo: "abcd efgh ijkl mnop"
```

### **PASSO 2: Entrar no Render (30 sec)**
```
1. Acesse >>> https://dashboard.render.com
2. Clique no seu projeto "franquias"
3. Clique em "Environment" no menu esquerdo
```

### **PASSO 3: Adicionar Variáveis de Ambiente (2 min)**

Clique **"Add Environment Variable"** e preencha CADA UMA:

```
┌─────────────────────────────────────────┐
│ MAIL_SERVER              │ smtp.gmail.com │
├─────────────────────────────────────────┤
│ MAIL_PORT                │ 587            │
├─────────────────────────────────────────┤
│ MAIL_USE_TLS             │ True           │
├─────────────────────────────────────────┤
│ MAIL_USERNAME            │ seu-email@gmail.com     │
├─────────────────────────────────────────┤
│ MAIL_PASSWORD            │ abcd efgh ijkl mnop (16 chars) │
├─────────────────────────────────────────┤
│ MAIL_DEFAULT_SENDER      │ seu-email@gmail.com     │
├─────────────────────────────────────────┤
│ EMAIL_FRANQUEADO         │ seu-email@gmail.com     │
├─────────────────────────────────────────┤
│ EMAIL_TIME               │ seu-email@gmail.com     │
├─────────────────────────────────────────┤
│ ADM_PASSWORD             │ sua-senha-admin (você escolhe) │
├─────────────────────────────────────────┤
│ SECRET_KEY               │ chave-aleatória-longa (você escolhe) │
└─────────────────────────────────────────┘
```

### **PASSO 4: Salvar e Redeploy (30 sec)**

```
1. Clique em "Save" (ou "Update")
2. Render vai começar o redeploy automaticamente
3. Aguarde ~2-5 minutos
4. Aparecerá "✅ Deployed" quando acabar
```

### **PASSO 5: Testar Email** ⚡

Abra no navegador:
```
https://seu-app.onrender.com/status-email
```

Deve aparecer:
```json
{
  "configurado": true,
  "mensagem": "✅ Email está configurado corretamente"
}
```

---

## ✅ PRONTO!

Seu email agora funciona no Render! 🎉

Você pode:
- ✅ Enviar notificações de unidades
- ✅ Alertar sobre prazos atrasados
- ✅ Fazer uploads de backup e restaurar dados

---

## 🔴 SE NÃO FUNCIONAR

### **Verificar Logs (Debug)**
1. Render Dashboard → seu projeto
2. "Logs" (embaixo do código)
3. Procure por "MAIL_" ou "error"
4. Isso mostra o erro exato

### **Erro: "MAIL_USERNAME não configurado"**
→ Você não adicionou a variável. Volte ao PASSO 3

### **Erro: "MAIL_PASSWORD não configurado"**
→ Você não adicionou MAIL_PASSWORD. Volte ao PASSO 3

### **Erro: "Invalid credentials"**
→ A senha de app está errada. Gere nova em myaccount.google.com/apppasswords

### **Erro: "Connection timeout"**
→ Tente porta 465 em vez de 587:
- `MAIL_PORT = 465`
- `MAIL_USE_TLS = False`

---

## 📚 DOCUMENTAÇÃO COMPLETA

Veja **SETUP_EMAIL_RENDER.md** para explicações mais detalhadas.

---

## 🎯 RESUMO (copie e cole se quiser):

```
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=True
MAIL_USERNAME=seu-email@gmail.com
MAIL_PASSWORD=sua-app-password-16-chars
MAIL_DEFAULT_SENDER=seu-email@gmail.com
EMAIL_FRANQUEADO=seu-email@gmail.com
EMAIL_TIME=seu-email@gmail.com
ADM_PASSWORD=escolha-uma-senha
SECRET_KEY=escolha-uma-chave-aleatoria
```
