"""Formulários com validação para o sistema de checklist"""
from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, TextAreaField, BooleanField, DateField
from wtforms.validators import DataRequired, Email, Length, Optional, Regexp
from wtforms.widgets import HiddenInput
import re

class AdicionarUnidadeForm(FlaskForm):
    """Formulário para adicionar nova unidade"""
    nome = StringField(
        'Nome',
        validators=[
            DataRequired(message='Nome é obrigatório'),
            Length(min=3, max=100, message='Nome deve ter entre 3 e 100 caracteres')
        ]
    )
    cidade = StringField(
        'Cidade',
        validators=[
            DataRequired(message='Cidade é obrigatória'),
            Length(min=2, max=50, message='Cidade deve ter entre 2 e 50 caracteres')
        ]
    )
    uf = SelectField(
        'UF',
        validators=[DataRequired(message='UF é obrigatório')],
        choices=[
            ('AC', 'AC'), ('AL', 'AL'), ('AP', 'AP'), ('AM', 'AM'),
            ('BA', 'BA'), ('CE', 'CE'), ('DF', 'DF'), ('ES', 'ES'),
            ('GO', 'GO'), ('MA', 'MA'), ('MT', 'MT'), ('MS', 'MS'),
            ('MG', 'MG'), ('PA', 'PA'), ('PB', 'PB'), ('PR', 'PR'),
            ('PE', 'PE'), ('PI', 'PI'), ('RJ', 'RJ'), ('RN', 'RN'),
            ('RS', 'RS'), ('RO', 'RO'), ('RR', 'RR'), ('SC', 'SC'),
            ('SP', 'SP'), ('SE', 'SE'), ('TO', 'TO')
        ]
    )
    tipo = SelectField(
        'Tipo de Unidade',
        validators=[DataRequired(message='Tipo é obrigatório')],
        choices=[
            ('CO', 'Centro de Operações'),
            ('FL', 'Filial'),
            ('LJ', 'Loja Própria'),
            ('PA', 'Posto de Atendimento'),
            ('HB', 'Hub'),
            ('JE', 'Franquia Light'),
            ('MATRIZ', 'Matriz')
        ]
    )
    status_unidade = SelectField(
        'Status',
        choices=[
            ('processo', '🔄 Em Processo'),
            ('pronta', '✅ Pronta para Abrir'),
            ('aberta', '🟢 Aberta'),
            ('fechada', '🔴 Fechada')
        ],
        default='processo'
    )

class EmailForm(FlaskForm):
    """Formulário para enviar emails"""
    emails = StringField(
        'Emails (separados por vírgula)',
        validators=[Optional()]
    )
    tipo = SelectField(
        'Destinatários',
        choices=[
            ('franqueado', 'Email Franqueado'),
            ('time', 'Email Time'),
            ('todos', 'Ambos')
        ],
        default='todos'
    )

class StatusUnidadeForm(FlaskForm):
    """Formulário para atualizar apenas o status"""
    status_unidade = SelectField(
        'Status',
        validators=[DataRequired(message='Status é obrigatório')],
        choices=[
            ('processo', '🔄 Em Processo'),
            ('pronta', '✅ Pronta para Abrir'),
            ('aberta', '🟢 Aberta'),
            ('fechada', '🔴 Fechada')
        ]
    )
    apenas_status = StringField(widget=HiddenInput(), default='sim')

def validar_email_custom(email_str):
    """Valida uma string contendo um ou múltiplos emails separados por vírgula"""
    if not email_str.strip():
        return []
    
    emails = [e.strip() for e in email_str.split(',')]
    validos = []
    invalidos = []
    
    padrao = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    
    for email in emails:
        if re.match(padrao, email):
            validos.append(email)
        else:
            invalidos.append(email)
    
    return validos, invalidos
