"""Serviço de backup e restore do banco de dados"""
import os
import shutil
import sqlite3
import json
from datetime import datetime
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class BackupService:
    """Serviço para fazer backup e restore do banco de dados"""
    
    def __init__(self, db_path: str, backup_dir: str = None):
        """
        Inicializa o serviço de backup
        
        Args:
            db_path: Caminho do arquivo .db (ex: instance/checklist.db)
            backup_dir: Diretório para armazenar backups (padrão: backups/)
        """
        self.db_path = db_path
        self.backup_dir = backup_dir or os.path.join(
            os.path.dirname(db_path), '..', 'backups'
        )
        os.makedirs(self.backup_dir, exist_ok=True)
    
    def criar_backup(self) -> tuple[bool, str]:
        """
        Cria um backup do banco de dados
        
        Returns:
            (sucesso: bool, nome_arquivo: str)
        """
        try:
            if not os.path.exists(self.db_path):
                return False, f"Banco de dados não encontrado: {self.db_path}"
            
            # Nome do arquivo com timestamp
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            nome_backup = f"checklist_backup_{timestamp}.db"
            caminho_backup = os.path.join(self.backup_dir, nome_backup)
            
            # Copiar arquivo
            shutil.copy2(self.db_path, caminho_backup)
            
            tamanho_mb = os.path.getsize(caminho_backup) / (1024 * 1024)
            logger.info(f"✅ Backup criado: {nome_backup} ({tamanho_mb:.2f} MB)")
            
            return True, nome_backup
        except Exception as e:
            logger.error(f"❌ Erro ao criar backup: {str(e)}")
            return False, str(e)
    
    def listar_backups(self) -> list:
        """Lista todos os backups disponíveis"""
        backups = []
        
        try:
            if not os.path.exists(self.backup_dir):
                return backups
            
            for arquivo in sorted(os.listdir(self.backup_dir), reverse=True):
                if arquivo.endswith('.db'):
                    caminho = os.path.join(self.backup_dir, arquivo)
                    tamanho = os.path.getsize(caminho)
                    data_modif = datetime.fromtimestamp(os.path.getmtime(caminho))
                    
                    backups.append({
                        'nome': arquivo,
                        'caminho': caminho,
                        'tamanho_mb': round(tamanho / (1024 * 1024), 2),
                        'data': data_modif.strftime('%d/%m/%Y %H:%M:%S'),
                        'timestamp': int(os.path.getmtime(caminho))
                    })
        except Exception as e:
            logger.error(f"❌ Erro ao listar backups: {str(e)}")
        
        return backups
    
    def restaurar_backup(self, nome_backup: str) -> tuple[bool, str]:
        """
        Restaura um backup do banco de dados
        
        Args:
            nome_backup: Nome do arquivo backup
        
        Returns:
            (sucesso: bool, mensagem: str)
        """
        try:
            caminho_backup = os.path.join(self.backup_dir, nome_backup)
            
            # Validar segurança - não permitir path traversal
            backup_real = os.path.realpath(caminho_backup)
            backup_dir_real = os.path.realpath(self.backup_dir)
            
            if not backup_real.startswith(backup_dir_real):
                return False, "Arquivo de backup inválido"
            
            if not os.path.exists(caminho_backup):
                return False, f"Backup não encontrado: {nome_backup}"
            
            # Criar backup do backup (segurança)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            nome_backup_seguranca = f"backup_antes_restore_{timestamp}.db"
            caminho_backup_seguranca = os.path.join(self.backup_dir, nome_backup_seguranca)
            
            # Copiar DB atual como backup de segurança
            if os.path.exists(self.db_path):
                shutil.copy2(self.db_path, caminho_backup_seguranca)
                logger.info(f"✅ Backup de segurança criado: {nome_backup_seguranca}")
            
            # Restaurar
            shutil.copy2(caminho_backup, self.db_path)
            logger.info(f"✅ Banco de dados restaurado de: {nome_backup}")
            
            return True, f"Banco restaurado com sucesso! Salvo como: {nome_backup_seguranca}"
        
        except Exception as e:
            logger.error(f"❌ Erro ao restaurar backup: {str(e)}")
            return False, str(e)
    
    def exportar_json(self) -> tuple[bool, dict]:
        """
        Exporta dados do banco em formato JSON
        
        Returns:
            (sucesso: bool, dados: dict)
        """
        try:
            from app import Unidade, LogEtapa, db
            
            with db.app.app_context():
                # Coletar unidades
                unidades = Unidade.query.all()
                logs = LogEtapa.query.all()
                
                dados = {
                    'tipo': 'checklist_backup',
                    'data_export': datetime.now().isoformat(),
                    'total_unidades': len(unidades),
                    'total_logs': len(logs),
                    'unidades': [],
                    'logs': []
                }
                
                # Serializar unidades
                for u in unidades:
                    dados['unidades'].append({
                        'id': u.id,
                        'nome': u.nome,
                        'cidade': u.cidade,
                        'uf': u.uf,
                        'tipo': u.tipo,
                        'status_unidade': u.status_unidade,
                        'checklist_status': u.checklist_status,
                        'criado_em': u.criado_em.isoformat() if hasattr(u, 'criado_em') else None,
                        'atualizado_em': u.atualizado_em.isoformat() if hasattr(u, 'atualizado_em') else None
                    })
                
                # Serializar logs
                for log in logs:
                    dados['logs'].append({
                        'id': log.id,
                        'unidade_id': log.unidade_id,
                        'etapa': log.etapa,
                        'acao': log.acao,
                        'observacao': log.observacao,
                        'data': log.data.isoformat()
                    })
                
                logger.info(f"✅ Dados exportados: {len(unidades)} unidades, {len(logs)} logs")
                return True, dados
        
        except Exception as e:
            logger.error(f"❌ Erro ao exportar JSON: {str(e)}")
            return False, {}
    
    def importar_json(self, dados: dict) -> tuple[bool, str]:
        """
        Importa dados de JSON para o banco
        
        Args:
            dados: Dicionário com dados exportados
        
        Returns:
            (sucesso: bool, mensagem: str)
        """
        try:
            from app import Unidade, LogEtapa, db
            
            # Validar formato
            if not isinstance(dados, dict) or dados.get('tipo') != 'checklist_backup':
                return False, "Formato de arquivo inválido"
            
            with db.app.app_context():
                # Contar registros existentes antes
                unidades_antes = Unidade.query.count()
                logs_antes = LogEtapa.query.count()
                
                # Importar unidades
                for u_data in dados.get('unidades', []):
                    try:
                        # Verificar se já existe (por ID)
                        u_existente = Unidade.query.get(u_data['id'])
                        if u_existente:
                            # Atualizar
                            u_existente.nome = u_data['nome']
                            u_existente.cidade = u_data['cidade']
                            u_existente.uf = u_data['uf']
                            u_existente.tipo = u_data['tipo']
                            u_existente.status_unidade = u_data['status_unidade']
                            u_existente.checklist_status = u_data['checklist_status']
                        else:
                            # Criar novo
                            nova_u = Unidade(
                                id=u_data['id'],
                                nome=u_data['nome'],
                                cidade=u_data['cidade'],
                                uf=u_data['uf'],
                                tipo=u_data['tipo'],
                                status_unidade=u_data['status_unidade'],
                                checklist_status=u_data['checklist_status']
                            )
                            db.session.add(nova_u)
                    except Exception as e:
                        logger.warning(f"Erro ao importar unidade {u_data.get('id')}: {str(e)}")
                        continue
                
                # Importar logs
                for log_data in dados.get('logs', []):
                    try:
                        log_existente = LogEtapa.query.get(log_data['id'])
                        if not log_existente:
                            novo_log = LogEtapa(
                                id=log_data['id'],
                                unidade_id=log_data['unidade_id'],
                                etapa=log_data['etapa'],
                                acao=log_data['acao'],
                                observacao=log_data['observacao'],
                                data=datetime.fromisoformat(log_data['data'])
                            )
                            db.session.add(novo_log)
                    except Exception as e:
                        logger.warning(f"Erro ao importar log {log_data.get('id')}: {str(e)}")
                        continue
                
                # Commit
                db.session.commit()
                
                unidades_depois = Unidade.query.count()
                logs_depois = LogEtapa.query.count()
                
                msg = f"✅ Importação concluída:\n"
                msg += f"   Unidades: {unidades_antes} → {unidades_depois}\n"
                msg += f"   Logs: {logs_antes} → {logs_depois}"
                logger.info(msg)
                
                return True, msg
        
        except Exception as e:
            logger.error(f"❌ Erro ao importar JSON: {str(e)}")
            db.session.rollback()
            return False, str(e)
    
    def deletar_backup(self, nome_backup: str) -> tuple[bool, str]:
        """Deleta um arquivo de backup"""
        try:
            caminho_backup = os.path.join(self.backup_dir, nome_backup)
            
            # Validar segurança
            backup_real = os.path.realpath(caminho_backup)
            backup_dir_real = os.path.realpath(self.backup_dir)
            
            if not backup_real.startswith(backup_dir_real):
                return False, "Arquivo de backup inválido"
            
            if not os.path.exists(caminho_backup):
                return False, "Backup não encontrado"
            
            os.remove(caminho_backup)
            logger.info(f"✅ Backup deletado: {nome_backup}")
            return True, f"Backup deletado: {nome_backup}"
        
        except Exception as e:
            logger.error(f"❌ Erro ao deletar backup: {str(e)}")
            return False, str(e)


# Instância global
backup_service = None

def init_backup_service(app):
    """Inicializa o serviço de backup"""
    global backup_service
    db_path = app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
    backup_service = BackupService(db_path)
    return backup_service
