import os
from dotenv import load_dotenv
load_dotenv()

# Configurações de teste
print("=== TESTE DE CONFIGURAÇÃO DE EMAIL ===")
print(f"MAIL_USERNAME: {os.getenv('MAIL_USERNAME')}")
print(f"MAIL_SERVER: {os.getenv('MAIL_SERVER', 'smtp.gmail.com')}")
print(f"MAIL_PORT: {os.getenv('MAIL_PORT', 587)}")
print(f"MAIL_USE_TLS: {os.getenv('MAIL_USE_TLS', 'True')}")