"""Modelos do banco de dados para o sistema de checklist"""
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import json

db = SQLAlchemy()

class Unidade(db.Model):
    """Modelo para unidades (lojas, filiais, etc)"""
    __tablename__ = 'unidade'
    
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False, unique=False, index=True)
    cidade = db.Column(db.String(50), nullable=False, index=True)
    uf = db.Column(db.String(2), nullable=False, index=True)
    tipo = db.Column(db.String(10), nullable=False, index=True)
    status_unidade = db.Column(db.String(20), default="processo", index=True)
    checklist_status = db.Column(db.Text, default="{}")
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    atualizado_em = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relacionamento
    logs = db.relationship('LogEtapa', cascade='all, delete-orphan', lazy=True)
    
    def __repr__(self):
        return f'<Unidade {self.nome} ({self.tipo})>'
    
    @property
    def status(self):
        """Retorna o status do checklist como dicionário"""
        try:
            return json.loads(self.checklist_status) if self.checklist_status else {}
        except (json.JSONDecodeError, TypeError):
            return {}


class LogEtapa(db.Model):
    """Modelo para logs de auditoria"""
    __tablename__ = 'log_etapa'
    
    id = db.Column(db.Integer, primary_key=True)
    unidade_id = db.Column(db.Integer, db.ForeignKey('unidade.id'), nullable=False, index=True)
    etapa = db.Column(db.String(200), nullable=False)
    acao = db.Column(db.String(50), nullable=False)
    observacao = db.Column(db.Text)
    data = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    
    # Relacionamento
    unidade = db.relationship('Unidade', back_populates='logs')
    
    def __repr__(self):
        return f'<LogEtapa {self.unidade_id} - {self.etapa} ({self.data})>'
