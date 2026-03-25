#!/usr/bin/env python
"""Script para testar configuração SMTP e diagnosticar problemas"""

import smtplib
import os
from dotenv import load_dotenv

load_dotenv()

# Configurações
MAIL_SERVER = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
MAIL_PORT = int(os.getenv('MAIL_PORT', 587))
MAIL_USE_TLS = os.getenv('MAIL_USE_TLS', 'True').lower() == 'true'
MAIL_USERNAME = os.getenv('MAIL_USERNAME')
MAIL_PASSWORD = os.getenv('MAIL_PASSWORD')

print("=" * 60)
print("🔍 TESTE DE CONFIGURAÇÃO SMTP")
print("=" * 60)
print(f"\n📍 Servidor: {MAIL_SERVER}")
print(f"📍 Porta: {MAIL_PORT}")
print(f"📍 TLS: {MAIL_USE_TLS}")
print(f"📍 Username: {MAIL_USERNAME}")
print(f"📍 Password: {'*' * len(MAIL_PASSWORD) if MAIL_PASSWORD else 'NÃO CONFIGURADO'}\n")

# Teste 1: Verificar se credenciais estão configuradas
print("✓ Teste 1: Verificar Credenciais")
if not MAIL_USERNAME or not MAIL_PASSWORD:
    print("❌ ERRO: MAIL_USERNAME ou MAIL_PASSWORD não configurados")
    print("   Configure as variáveis no arquivo .env")
    exit(1)
else:
    print("✅ Credenciais configuradas")

# Teste 2: Testar conexão SMTP
print("\n✓ Teste 2: Conectar ao Servidor SMTP")
try:
    if MAIL_USE_TLS:
        print(f"   Conectando com TLS em {MAIL_SERVER}:{MAIL_PORT}...")
        server = smtplib.SMTP(MAIL_SERVER, MAIL_PORT, timeout=10)
        server.starttls()
    else:
        print(f"   Conectando sem TLS em {MAIL_SERVER}:{MAIL_PORT}...")
        server = smtplib.SMTP_SSL(MAIL_SERVER, MAIL_PORT, timeout=10)
    
    print("✅ Conexão com servidor estabelecida")
except smtplib.SMTPException as e:
    print(f"❌ ERRO SMTP: {str(e)}")
    print("\n📋 Possíveis soluções:")
    print("   1. Verifique se a porta está correta (Gmail: 587 ou 465)")
    print("   2. Verifique TLS/SSL (Gmail usa TLS na porta 587)")
    print("   3. Verifique se seu firewall permite conexões na porta 587")
    exit(1)
except TimeoutError:
    print("❌ ERRO: Timeout ao conectar (servidor não respondeu)")
    print("\n📋 Possíveis soluções:")
    print("   1. Verifique conexão com internet")
    print("   2. Verifique se firewall/VPN está bloqueando")
    print("   3. Tente servidor alternativo")
    exit(1)
except Exception as e:
    print(f"❌ ERRO de conexão: {str(e)}")
    exit(1)

# Teste 3: Testar autenticação
print("\n✓ Teste 3: Autenticar com credenciais")
try:
    server.login(MAIL_USERNAME, MAIL_PASSWORD)
    print("✅ Autenticação bem-sucedida")
except smtplib.SMTPAuthenticationError as e:
    print(f"❌ ERRO DE AUTENTICAÇÃO: {str(e)}")
    print("\n📋 Possíveis soluções para Gmail:")
    print("   1. Use uma 'Senha de App' ao invés da senha normal")
    print("   2. Vá em: https://myaccount.google.com/apppasswords")
    print("   3. Gere uma nova senha para sua aplicação")
    print("   4. Use essa senha no arquivo .env")
    server.quit()
    exit(1)
except Exception as e:
    print(f"❌ ERRO na autenticação: {str(e)}")
    server.quit()
    exit(1)

# Teste 4: Testar envio de email de teste
print("\n✓ Teste 4: Enviar Email de Teste")
try:
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    
    msg = MIMEMultipart('alternative')
    msg['Subject'] = "🔧 Teste SMTP - Sucesso!"
    msg['From'] = MAIL_USERNAME
    msg['To'] = MAIL_USERNAME
    
    corpo_html = """
    <html>
        <body>
            <h2 style="color: green;">✅ Teste de Email Funcionando!</h2>
            <p>Se você recebeu este email, sua configuração SMTP está correta.</p>
            <p><strong>Data:</strong> """ + str(__import__('datetime').datetime.now()) + """</p>
            <p><strong>Servidor:</strong> """ + MAIL_SERVER + """</p>
        </body>
    </html>
    """
    
    msg.attach(MIMEText(corpo_html, 'html'))
    
    server.sendmail(MAIL_USERNAME, [MAIL_USERNAME], msg.as_string())
    print(f"✅ Email enviado com sucesso para: {MAIL_USERNAME}")
    print("\n   Verifique sua caixa de entrada (ou spam)")
    
except Exception as e:
    print(f"❌ ERRO ao enviar email: {str(e)}")
    server.quit()
    exit(1)

# Finalizar
server.quit()

print("\n" + "=" * 60)
print("🎉 TODOS OS TESTES PASSARAM!")
print("=" * 60)
print("\n✅ Sua configuração SMTP está correta e funcionando.")
print("✅ O app Flask agora conseguirá enviar emails.")
