# 📧 Configurar Email (SMTP Gmail) no Render.com

## ⚠️ PROBLEMA COMUM

O email funciona em desenvolvimento local, mas não funciona no Render porque as **variáveis de ambiente não estão configuradas**.

---

## ✅ SOLUÇÃO PASSO A PASSO

### **1. Obter Senha de App do Gmail**

O Gmail não permite usar sua senha regular em aplicativos. Você precisa da **"App Password"**.

#### Como gerar:

1. **Acesse sua conta Google:**
   - https://myaccount.google.com

2. **Ative autenticação de dois fatores (se não tiver):**
   - Clique em "Segurança" na esquerda
   - Procure por "Autenticação de duas etapas"
   - Siga as instruções

3. **Gere a App Password:**
   - Acesse https://myaccount.google.com/apppasswords
   - Selecione:
     - **App**: Mail
     - **Device**: Windows Computer (ou seu tipo de server)
   - Clique em "Gerar"
   - **COPIE a senha de 16 caracteres** (com espaços)
   - Exemplo: `abcd efgh ijkl mnop`

---

### **2. Configurar Variáveis no Render**

1. **Acesse seu projeto no Render.com**
2. **Clique em "Environment"** (ou "Settings" → "Environment")
3. **Clique em "Add Environment Variable"**

Adicione **CADA UMA DESTAS VARIÁVEIS:**

| Variável | Valor | Descrição |
|----------|-------|-----------|
| `MAIL_SERVER` | `smtp.gmail.com` | Servidor SMTP do Gmail |
| `MAIL_PORT` | `587` | Porta TLS para Gmail |
| `MAIL_USE_TLS` | `True` | Ativar TLS (segurança) |
| `MAIL_USERNAME` | seu-email@gmail.com | Seu email Gmail completo |
| `MAIL_PASSWORD` | `abcd efgh ijkl mnop` | Senha de App (16 chars) |
| `MAIL_DEFAULT_SENDER` | seu-email@gmail.com | Email de origem |
| `EMAIL_FRANQUEADO` | seu-email@gmail.com | Email para notificações |
| `EMAIL_TIME` | seu-email@gmail.com | Email para alertas internos |

**🔴 IMPORTANTE:** 
- Use a **Senha de App**, NÃO sua senha de conta
- Não coloque aspas nas variáveis
- Mantenha os espaços na senha de app

---

### **3. Fazer Deploy no Render**

1. Depois de adicionar as variáveis, **clique em "Save"**
2. O Render vai **redeploy automaticamente**
3. Aguarde a implantação ser concluída
4. Teste acessando: `https://seu-app.onrender.com/status-email`

Se a resposta mostrar:
```json
{
  "configurado": true,
  "mensagem": "✅ Email está configurado corretamente"
}
```

**Pronto!** O email agora deve funcionar. 🎉

---

## 🧪 TESTANDO O EMAIL

### **Opção 1: Verificar Status**

Acesse no navegador:
```
https://seu-app.onrender.com/status-email
```

### **Opção 2: Enviar Email de Teste**

1. Vá para a página principal da app
2. Acesse a unidade e clique em **"Notificar"**
3. Envie um email de teste
4. Verifique sua caixa de entrada

### **Opção 3: Ver Logs do Render**

Se ainda não funcionar:
1. Acesse seu projeto no Render
2. Clique em **"Logs"**
3. Procure por mensagens de erro com "MAIL_" ou "email"
4. Isso vai mostrar exatamente o que está falhando

---

## ❌ RESOLVENDO PROBLEMAS

### **Erro: "MAIL_USERNAME não configurado"**
- Você não adicionou a variável `MAIL_USERNAME` no Render
- Adicione-a e refaça o deploy

### **Erro: "MAIL_PASSWORD não configurado"**
- Você não adicionou a variável `MAIL_PASSWORD` no Render
- Use a **Senha de App** do Gmail (16 caracteres)

### **Erro: "Connection refused" ou timeout**
- Pode ser bloqueio de firewall
- Tente usar porta `465` em vez de `587`
- Altere `MAIL_PORT=465` e `MAIL_USE_TLS=False`

### **Erro: "Invalid credentials"**
- A senha de app está errada
- Gere uma nova em https://myaccount.google.com/apppasswords
- Tecle certinho, com espaços

### **Erro: "Too many login attempts"**
- Gmail bloqueou por segurança
- Aguarde 24 horas
- Ou use um email diferente

---

## 📝 RESUMO RÁPIDO

```bash
# Variáveis obrigatórias para email funcionar:
MAIL_USERNAME=seu-email@gmail.com
MAIL_PASSWORD=sua-app-password-16-chars
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=True
MAIL_DEFAULT_SENDER=seu-email@gmail.com
```

**✅ Depois de adicionar, clique SAVE e aguarde o redeploy!**

---

## 🔗 LINKS ÚTEIS

- 📧 Gmail App Passwords: https://myaccount.google.com/apppasswords
- 🔐 Google Security: https://myaccount.google.com/security
- 📊 Render Dashboard: https://dashboard.render.com
- 📖 Render Docs: https://render.com/docs
