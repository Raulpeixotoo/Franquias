"""Funções utilitárias para o sistema de checklist"""
import json
import re
from datetime import date, datetime
from collections import Counter

def gerar_id_seguro(texto: str) -> str:
    """Gera um ID seguro removendo caracteres especiais"""
    texto_limpo = re.sub(r'[^\w\s]', '', texto)
    texto_limpo = re.sub(r'\s+', '_', texto_limpo)
    return texto_limpo.lower()

def verificar_atrasados(checklist_json: str) -> list:
    """Verifica items atrasados em um checklist"""
    if not checklist_json or checklist_json == "{}":
        return []
    
    try:
        dados = json.loads(checklist_json)
    except (json.JSONDecodeError, TypeError):
        return []
    
    atrasados = []
    hoje = date.today().isoformat()
    
    for item, info in dados.items():
        if isinstance(info, dict):
            concluido = info.get('concluido', False)
            previsao = info.get('previsao', '')
            if not concluido and previsao and previsao < hoje:
                atrasados.append({
                    'nome': item,
                    'previsao': previsao,
                    'dias_atraso': (date.today() - date.fromisoformat(previsao)).days
                })
    
    return atrasados

def calcular_status_categorias(checklist_json: str, categorias: dict) -> dict:
    """Calcula o status de cada categoria do checklist"""
    if not checklist_json or checklist_json == "{}":
        return {
            cat: {"status": "nao_iniciado", "total": len(itens), "concluidos": 0} 
            for cat, itens in categorias.items()
        }
    
    try:
        dados = json.loads(checklist_json)
    except (json.JSONDecodeError, TypeError):
        return {}
    
    hoje = date.today().isoformat()
    resultado = {}
    
    for categoria, itens in categorias.items():
        total = len(itens)
        concluidos = 0
        tem_atraso = False
        
        for item_config in itens:
            item_nome = item_config['nome']
            info = dados.get(item_nome, {})
            
            if item_config['tipo'] == 'checkbox':
                if isinstance(info, dict):
                    if info.get('concluido', False):
                        concluidos += 1
                    else:
                        previsao = info.get('previsao', '')
                        if previsao and previsao < hoje:
                            tem_atraso = True
            else:
                if info and info != '':
                    concluidos += 1
        
        if concluidos == total:
            status = "concluido"
        elif tem_atraso:
            status = "atrasado"
        elif concluidos > 0:
            status = "andamento"
        else:
            status = "pendente"
        
        resultado[categoria] = {
            "status": status,
            "total": total,
            "concluidos": concluidos
        }
    
    return resultado

def gerar_resumos(unidades: list) -> dict:
    """Gera resumo de estatísticas das unidades"""
    total = len(unidades)
    abertas = sum(1 for u in unidades if u.status_unidade == "aberta")
    fechadas = sum(1 for u in unidades if u.status_unidade == "fechada")
    em_processo = total - abertas - fechadas
    
    ufs = Counter(u.uf for u in unidades)
    tipos = Counter(u.tipo for u in unidades)
    
    return {
        'total': total,
        'abertas': abertas,
        'em_processo': em_processo,
        'fechadas': fechadas,
        'ufs': dict(ufs),
        'tipos': dict(tipos)
    }

def classificar_prazos(unidades: list, categorias: dict) -> list:
    """Classifica todos os prazos por urgência"""
    hoje = date.today()
    todos_prazos = []
    
    for u in unidades:
        try:
            dados = json.loads(u.checklist_status) if u.checklist_status else {}
            for item_nome, info in dados.items():
                if isinstance(info, dict):
                    previsao = info.get('previsao', '')
                    concluido = info.get('concluido', False)
                    
                    if previsao and not concluido:
                        data_prev = date.fromisoformat(previsao)
                        dias = (data_prev - hoje).days
                        urgencia = (
                            'atrasado' if dias < 0 
                            else ('proximo' if dias <= 7 else 'futuro')
                        )
                        
                        categoria = 'Outros'
                        for cat, itens in categorias.items():
                            for item_config in itens:
                                if item_config['nome'] == item_nome:
                                    categoria = cat
                                    break
                        
                        todos_prazos.append({
                            'unidade': u.nome,
                            'unidade_id': u.id,
                            'item': item_nome,
                            'categoria': categoria.split(' ')[-1],
                            'previsao': previsao,
                            'dias': dias,
                            'urgencia': urgencia
                        })
        except Exception:
            pass
    
    todos_prazos.sort(key=lambda x: (x['urgencia'] != 'atrasado', x['previsao']))
    return todos_prazos

def verificar_prazos_e_notificar(unidade, status_salvo: dict) -> list:
    """Verifica itens próximos ao vencimento e retorna alertas"""
    hoje = datetime.now().date()
    alertas = []
    
    for item_nome, item_valor in status_salvo.items():
        if isinstance(item_valor, dict):
            previsao = item_valor.get('previsao', '')
            concluido = item_valor.get('concluido', False)
            
            if previsao and not concluido:
                try:
                    data_previsao = datetime.strptime(previsao, '%Y-%m-%d').date()
                    dias_para_vencer = (data_previsao - hoje).days
                    
                    # Alerta se vencer hoje ou amanhã
                    if 0 <= dias_para_vencer <= 1:
                        alertas.append({
                            'item': item_nome,
                            'dias': dias_para_vencer,
                            'previsao': previsao,
                            'status': 'vencimento'
                        })
                    # Alerta se já venceu
                    elif dias_para_vencer < 0:
                        alertas.append({
                            'item': item_nome,
                            'dias': abs(dias_para_vencer),
                            'previsao': previsao,
                            'status': 'vencido'
                        })
                except ValueError:
                    pass
    
    return alertas

def notificar_aprovacoes_pendentes(unidade, status_salvo: dict) -> list:
    """Verifica aprovações pendentes"""
    pendentes = []
    
    for item_nome, item_valor in status_salvo.items():
        if ('aprovacao' in item_nome.lower() or 'Aprovação' in item_nome) and item_valor == 'pendente':
            pendentes.append(item_nome.replace('aprovacao_', ''))
    
    return pendentes
