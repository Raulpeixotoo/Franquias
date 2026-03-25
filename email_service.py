"""Serviço de email com retry logic e formatação melhorada"""
import os
import re
from datetime import datetime
import threading
import time
import logging
from flask import Flask
from flask_mail import Mail, Message

logger = logging.getLogger(__name__)

class EmailService:
    """Serviço centralizado para envio de emails"""
    
    def __init__(self, app: Flask = None, mail: Mail = None):
        self.app = app
        self.mail = mail
        self.ultimo_envio = {}  # Cache para evitar duplicatas
    
    def init_app(self, app: Flask, mail: Mail):
        """Inicializa o serviço com app e mail"""
        self.app = app
        self.mail = mail
    
    @staticmethod
    def validar_email(email: str) -> bool:
        """Valida formato de email"""
        padrao = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(padrao, email) is not None
    
    @staticmethod
    def validar_multiplos_emails(emails_str: str) -> tuple[list, list]:
        """Valida múltiplos emails separados por vírgula. Retorna (válidos, inválidos)"""
        if not emails_str or not emails_str.strip():
            return [], []
        
        emails = [e.strip() for e in emails_str.split(',') if e.strip()]
        validos = []
        invalidos = []
        
        for email in emails:
            if EmailService.validar_email(email):
                validos.append(email)
            else:
                invalidos.append(email)
        
        return validos, invalidos
    
    def enviar_com_retry(self, msg: Message, retries: int = 3, delay: int = 2) -> bool:
        """Envia email com retry usando exponential backoff"""
        for tentativa in range(retries):
            try:
                with self.app.app_context():
                    self.mail.send(msg)
                    logger.info(f"✅ Email enviado com sucesso para: {', '.join(msg.recipients)}")
                    return True
            except Exception as e:
                if tentativa < retries - 1:
                    tempo_espera = delay ** tentativa
                    logger.warning(f"Tentativa {tentativa + 1}/{retries} falhou. Aguardando {tempo_espera}s...")
                    time.sleep(tempo_espera)
                else:
                    logger.error(f"❌ Falha ao enviar email após {retries} tentativas: {str(e)}")
        
        return False
    
    def enviar_email_async(self, msg: Message, retries: int = 3) -> None:
        """Envia email em background com retry"""
        self.enviar_com_retry(msg, retries=retries)
    
    def enviar(self, destinatarios, assunto: str, corpo_html: str, 
               corpo_text: str = None, async_envio: bool = True) -> tuple[bool, str]:
        """
        Função principal para enviar emails
        
        Args:
            destinatarios: string com emails (separados por vírgula) ou lista
            assunto: assunto do email
            corpo_html: conteúdo em HTML
            corpo_text: conteúdo em texto plano (opcional)
            async_envio: se True, envia em background
        
        Returns:
            (sucesso: bool, mensagem: str)
        """
        try:
            # Validar configuração
            if not self.app.config.get('MAIL_USERNAME'):
                logger.error("❌ MAIL_USERNAME não configurado")
                logger.error("   Adicione a variável MAIL_USERNAME no Render Environment")
                return False, "MAIL_USERNAME não configurado"
            
            if not self.app.config.get('MAIL_PASSWORD'):
                logger.error("❌ MAIL_PASSWORD não configurado")
                logger.error("   Adicione a variável MAIL_PASSWORD no Render Environment")
                return False, "MAIL_PASSWORD não configurado"
            
            # Log das configurações (sem expor senha)
            logger.info(f"📧 Email config: server={self.app.config.get('MAIL_SERVER')}, "
                       f"port={self.app.config.get('MAIL_PORT')}, "
                       f"user={self.app.config.get('MAIL_USERNAME')}")
            
            # Garantir que destinatários seja uma lista
            if isinstance(destinatarios, str):
                emails_validos, emails_invalidos = self.validar_multiplos_emails(destinatarios)
            else:
                emails_validos = [e for e in destinatarios if self.validar_email(e)]
                emails_invalidos = [e for e in destinatarios if not self.validar_email(e)]
            
            if emails_invalidos:
                logger.warning(f"Emails inválidos ignorados: {', '.join(emails_invalidos)}")
            
            if not emails_validos:
                logger.warning("Nenhum email válido para enviar")
                return False, "Nenhum email válido"
            
            msg = Message(
                subject=assunto,
                recipients=emails_validos,
                html=corpo_html,
                body=corpo_text or "Por favor, visualize este email em um cliente HTML."
            )
            
            if async_envio:
                # Envia em background
                thread = threading.Thread(
                    target=self.enviar_email_async,
                    args=(msg,)
                )
                thread.daemon = True
                thread.start()
                logger.info(f"Email agendado para envio: {', '.join(emails_validos)}")
                return True, f"Email agendado para envio para: {', '.join(emails_validos)}"
            else:
                # Envia de forma síncrona
                if not self.enviar_com_retry(msg):
                    return False, "Falha ao enviar email"
                return True, f"Email enviado com sucesso para: {', '.join(emails_validos)}"
            
        except Exception as e:
            logger.error(f"Erro ao preparar email: {str(e)}")
            return False, str(e)
    
    def registrar_cache(self, chave: str, valor=True) -> None:
        """Registra no cache para evitar duplicatas"""
        self.ultimo_envio[chave] = valor
    
    def verificar_cache(self, chave: str) -> bool:
        """Verifica se já foi enviado (para evitar duplicatas)"""
        return chave in self.ultimo_envio and self.ultimo_envio[chave]


# Instância global
email_service = EmailService()