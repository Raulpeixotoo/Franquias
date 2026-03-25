"""Serviço de backup e restore do banco de dados
Compatível com ambientes read-only (Render, Heroku) - sem uso de arquivos
"""
from datetime import datetime
import logging
import json

logger = logging.getLogger(__name__)

# Armazena backups em memória
backups_em_memoria = {}


class BackupService:
    """Serviço de backup baseado em dados (sem arquivos)"""
    
    def __init__(self, app=None):
        """Inicializa o serviço de backup"""
        self.app = app
    
    def criar_backup(self) -> tuple[bool, str]:
        """
        Cria um backup dos dados do banco (JSON em memória)
        
        Returns:
            (sucesso: bool, id_backup: str)
        """
        try:
            if not self.app:
                return False, "App não configurado"
            
            # Exportar dados
            sucesso, dados = self.exportar_json()
            if not sucesso:
                return False, "Erro ao exportar dados"
            
            # Gerar ID único
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_id = f"backup_{timestamp}"
            
            # Armazenar em memória
            backups_em_memoria[backup_id] = {
                'dados': dados,
                'criado_em': datetime.now(),
                'tamanho_bytes': len(json.dumps(dados).encode('utf-8'))
            }
            
            tamanho_kb = backups_em_memoria[backup_id]['tamanho_bytes'] / 1024
            logger.info(f"✅ Backup criado: {backup_id} ({tamanho_kb:.2f} KB)")
            
            return True, backup_id
        
        except Exception as e:
            logger.error(f"❌ Erro ao criar backup: {str(e)}")
            return False, str(e)
    
    def listar_backups(self) -> list:
        """Lista todos os backups disponíveis"""
        backups = []
        
        try:
            for backup_id, info in sorted(backups_em_memoria.items(), reverse=True):
                tamanho_kb = info['tamanho_bytes'] / 1024
                backups.append({
                    'nome': backup_id,
                    'id': backup_id,
                    'tamanho_mb': round(tamanho_kb / 1024, 2),
                    'tamanho_kb': round(tamanho_kb, 2),
                    'data': info['criado_em'].strftime('%d/%m/%Y %H:%M:%S'),
                    'timestamp': int(info['criado_em'].timestamp())
                })
        except Exception as e:
            logger.error(f"❌ Erro ao listar backups: {str(e)}")
        
        return backups
    
    def restaurar_backup(self, backup_id: str) -> tuple[bool, str]:
        """
        Restaura um backup do banco de dados
        
        Args:
            backup_id: ID do backup
        
        Returns:
            (sucesso: bool, mensagem: str)
        """
        try:
            if backup_id not in backups_em_memoria:
                return False, f"Backup não encontrado: {backup_id}"
            
            dados = backups_em_memoria[backup_id]['dados']
            
            # Importar dados
            sucesso, mensagem = self.importar_json(dados)
            
            if sucesso:
                logger.info(f"✅ Banco restaurado de: {backup_id}")
                return True, f"Restaurado com sucesso de: {backup_id}\n{mensagem}"
            else:
                return False, f"Erro ao restaurar: {mensagem}"
        
        except Exception as e:
            logger.error(f"❌ Erro ao restaurar backup: {str(e)}")
            return False, str(e)
    
    def fazer_download_backup(self, backup_id: str) -> tuple[bool, str, bytes]:
        """
        Retorna dados do backup como arquivo JSON para download
        
        Args:
            backup_id: ID do backup
        
        Returns:
            (sucesso: bool, nome_arquivo: str, conteudo: bytes)
        """
        try:
            if backup_id not in backups_em_memoria:
                return False, "", b""
            
            dados = backups_em_memoria[backup_id]['dados']
            
            # Gerar arquivo JSON
            conteudo = json.dumps(dados, indent=2, ensure_ascii=False).encode('utf-8')
            nome_arquivo = f"{backup_id}.json"
            
            logger.info(f"✅ Download preparado: {nome_arquivo}")
            return True, nome_arquivo, conteudo
        
        except Exception as e:
            logger.error(f"❌ Erro ao preparar download: {str(e)}")
            return False, "", b""
    
    def fazer_upload_backup(self, arquivo_conteudo: bytes) -> tuple[bool, str]:
        """
        Faz upload de um arquivo JSON de backup
        
        Args:
            arquivo_conteudo: Conteúdo do arquivo em bytes
        
        Returns:
            (sucesso: bool, mensagem: str)
        """
        try:
            # Tentar desserializar JSON
            dados = json.loads(arquivo_conteudo.decode('utf-8'))
            
            if not isinstance(dados, dict) or dados.get('tipo') != 'checklist_backup':
                return False, "Arquivo inválido! Certifique-se que é um backup válido."
            
            # Gerar ID para novo backup
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_id = f"backup_upload_{timestamp}"
            
            # Armazenar
            backups_em_memoria[backup_id] = {
                'dados': dados,
                'criado_em': datetime.now(),
                'tamanho_bytes': len(arquivo_conteudo)
            }
            
            logger.info(f"✅ Backup restaurado do upload: {backup_id}")
            return True, f"Arquivo importado com sucesso! ID: {backup_id}"
        
        except json.JSONDecodeError:
            return False, "Arquivo não é um JSON válido"
        except Exception as e:
            logger.error(f"❌ Erro ao fazer upload: {str(e)}")
            return False, str(e)
    
    def exportar_json(self) -> tuple[bool, dict]:
        """
        Exporta dados do banco em formato JSON
        
        Returns:
            (sucesso: bool, dados: dict)
        """
        try:
            from models import Unidade, LogEtapa
            
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
            from models import Unidade, LogEtapa, db
            
            # Validar formato
            if not isinstance(dados, dict) or dados.get('tipo') != 'checklist_backup':
                return False, "Formato de arquivo inválido"
            
            # Contar registros existentes antes
            unidades_antes = Unidade.query.count()
            logs_antes = LogEtapa.query.count()
            
            unidades_importadas = 0
            logs_importados = 0
            
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
                    unidades_importadas += 1
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
                    logs_importados += 1
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
    
    def deletar_backup(self, backup_id: str) -> tuple[bool, str]:
        """Deleta um backup em memória"""
        try:
            if backup_id not in backups_em_memoria:
                return False, "Backup não encontrado"
            
            del backups_em_memoria[backup_id]
            logger.info(f"✅ Backup deletado: {backup_id}")
            return True, f"Backup deletado: {backup_id}"
        
        except Exception as e:
            logger.error(f"❌ Erro ao deletar backup: {str(e)}")
            return False, str(e)


# Instância global
backup_service = None


def init_backup_service(app):
    """Inicializa o serviço de backup"""
    global backup_service
    backup_service = BackupService(app)
    return backup_service
