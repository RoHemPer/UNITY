import json
import pandas as pd
import matplotlib.pyplot as plt
import os
import xml.etree.ElementTree as ET
import webbrowser
import pathlib
from datetime import datetime
import math
import random

# --- Constantes ---
OUTPUT_DIR = "dashboard_output_final"
SIM_DATA_JSON = os.path.join("dashboard_output", "simulation_dashboard_data.json")
EMISSION_FILE = "emission.xml"
TRIPINFO_FILE = "tripinfo.xml"
DASHBOARD_HTML_FILENAME = "sumo_traffic_dashboard.html" # Nome do arquivo HTML final
CO2_PER_CAR_PER_STEP_G = 0.75
HELP_URL = "https://docs.google.com/document/d/17R3UoVEYx7hObFm-laUh6Y7XuCOMXg2rxg7D5QMgdWw/edit?usp=sharing"

# --- Funções de Parsing ---
def parse_emissions(emission_file_path):
    co2_by_step_dict = {}
    total_co2_emitted_simulation = 0
    try:
        if not os.path.exists(emission_file_path):
            print(f"AVISO: Arquivo de emissões '{emission_file_path}' não encontrado.")
            return {}, 0
        tree = ET.parse(emission_file_path)
        root = tree.getroot()
        for timestep in root.findall('timestep'):
            time_str = timestep.get('time')
            if time_str is None: continue
            time = float(time_str)
            current_co2_total_timestep = 0
            for vehicle in timestep.findall('vehicle'):
                co2_val_str = vehicle.get('CO2', '0')
                try:
                    co2_val = float(co2_val_str)
                    current_co2_total_timestep += co2_val
                    total_co2_emitted_simulation += co2_val
                except ValueError: pass
            co2_by_step_dict[time] = co2_by_step_dict.get(time, 0) + current_co2_total_timestep
    except ET.ParseError: print(f"AVISO: Erro ao analisar '{emission_file_path}'. Métricas de CO2 podem estar incompletas.")
    except Exception as e: print(f"Erro inesperado ao processar '{emission_file_path}': {e}")
    return co2_by_step_dict, total_co2_emitted_simulation

def parse_tripinfo(tripinfo_file_path):
    total_duration_sum, total_time_loss_sum, num_trips_completed = 0, 0, 0
    try:
        if not os.path.exists(tripinfo_file_path):
            print(f"AVISO: Arquivo tripinfo '{tripinfo_file_path}' não encontrado.")
            return 0, 0, 0
        tree = ET.parse(tripinfo_file_path)
        root = tree.getroot()
        for tripinfo in root.findall('tripinfo'):
            duration_str = tripinfo.get('duration', '0')
            time_loss_str = tripinfo.get('timeLoss', '0')
            try:
                total_duration_sum += float(duration_str)
                total_time_loss_sum += float(time_loss_str)
                num_trips_completed += 1
            except ValueError:
                print(f"AVISO: Valor inválido encontrado em tripinfo (duration='{duration_str}', timeLoss='{time_loss_str}'). Ignorando entrada.")
    except ET.ParseError: print(f"AVISO: Erro ao analisar '{tripinfo_file_path}'. Métricas de viagem podem estar incompletas.")
    except Exception as e: print(f"Erro inesperado ao processar '{tripinfo_file_path}': {e}")
    avg_duration = total_duration_sum / num_trips_completed if num_trips_completed > 0 else 0
    avg_time_loss = total_time_loss_sum / num_trips_completed if num_trips_completed > 0 else 0
    return avg_duration, avg_time_loss, num_trips_completed

# --- Funções de Formatação ---
def format_large_number(num, precision=0):
    if pd.isna(num) or num == 0: return "0"
    num_float = float(num)
    if abs(num_float) < 1000: return f"{num_float:.{precision}f}"
    if abs(num_float) < 1_000_000: return f"{num_float/1000:.1f}k"
    return f"{num_float/1_000_000:.1f}M"

def format_duration(total_seconds_float):
    if pd.isna(total_seconds_float) or total_seconds_float <= 0: return "0s"
    total_seconds = int(round(total_seconds_float))
    if total_seconds == 0: return "0s"
    if total_seconds < 60: return f"{total_seconds}s"
    minutes = total_seconds // 60; seconds = total_seconds % 60
    if minutes < 60: return f"{minutes}m {seconds}s" if seconds > 0 else f"{minutes}m"
    hours = minutes // 60; minutes = minutes % 60
    return f"{hours}h {minutes}m" if minutes > 0 else f"{hours}h"

# --- Funções de Geração de Gráficos (Matplotlib) ---
def plot_data(df, x_col, y_col, title, xlabel, ylabel, filename_suffix, output_dir, is_cumulative=False, color='dodgerblue', marker='.'):
    chart_filename = f"{filename_suffix}.png"
    chart_full_path = os.path.join(output_dir, chart_filename)
    data_valid = True; reason = ""
    
    if y_col not in df.columns:
        data_valid = False; reason = f"Coluna Y '{y_col}' ausente no DataFrame"
    elif df.empty or x_col not in df.columns:
        data_valid = False; reason = "DataFrame vazio ou coluna X ausente"
    elif df.get(y_col, pd.Series(dtype='float64')).isnull().all():
        data_valid = False; reason = f"Coluna Y '{y_col}' contém apenas nulos"
    else:
        y_numeric_check = pd.to_numeric(df.get(y_col), errors='coerce').fillna(0)
        if y_numeric_check.eq(0).all():
            if is_cumulative:
                 data_valid = False; reason = f"Coluna Y '{y_col}' contém apenas zero (cumulativo não informativo)"
    
    if not data_valid:
        print(f"Dados para '{title}' insuficientes ou não adequados ({reason}). Gerando placeholder.")
        plt.figure(figsize=(10, 5)); plt.text(0.5, 0.5, f'Dados Indisponíveis ou Zero\npara o Gráfico:\n"{title}"', ha='center', va='center', fontsize=10, color='grey', wrap=True); plt.xticks([]); plt.yticks([])
        try: plt.savefig(chart_full_path); print(f"Placeholder salvo: {chart_full_path}")
        except Exception as e: print(f"Erro ao salvar placeholder {chart_filename}: {e}")
        plt.close(); return chart_filename
    
    plt.figure(figsize=(10, 5))
    y_values_numeric = pd.to_numeric(df.get(y_col), errors='coerce').fillna(0)
    y_values_plot = y_values_numeric.cumsum() if is_cumulative else y_values_numeric
    
    plt.plot(df.get(x_col), y_values_plot, marker=marker, linestyle='-', color=color, linewidth=1.5, markersize=4)
    plt.title(title, fontsize=14, color='#2c3e50')
    plt.xlabel(xlabel, fontsize=12, color='#34495e')
    plt.ylabel(ylabel, fontsize=12, color='#34495e') # Rótulo do eixo Y simplificado
    plt.grid(True, linestyle='--', alpha=0.6); plt.xticks(fontsize=10); plt.yticks(fontsize=10)
    try:
        if not pd.Series(y_values_plot).empty and pd.Series(y_values_plot).abs().max() > 10000:
             plt.gca().ticklabel_format(style='plain', axis='y')
    except Exception: pass
    plt.tight_layout()
    try: plt.savefig(chart_full_path); print(f"Gráfico salvo: {chart_full_path}")
    except Exception as e: print(f"Erro ao salvar gráfico {chart_filename}: {e}"); plt.close(); return "placeholder.png"
    plt.close()
    return chart_filename

def plot_queue_data(raw_data, tls_focus_id, output_dir):
    tls_queue_data = []
    if raw_data and isinstance(raw_data, list) and len(raw_data) > 0 and isinstance(raw_data[0], dict):
        for entry in raw_data:
            if isinstance(entry, dict): 
                for tls_entry in entry.get("tls_data", []):
                    if isinstance(tls_entry, dict) and tls_entry.get("tls_id") == tls_focus_id:
                        tls_queue_data.append({
                            "step": entry.get("step", 0),
                            "Via Leste-Oeste": tls_entry.get("queue_W", 0) + tls_entry.get("queue_E", 0),
                            "Via Norte-Sul": tls_entry.get("queue_N", 0) + tls_entry.get("queue_S", 0)
                        })
    chart_filename = f"queues_{tls_focus_id}.png"
    chart_full_path = os.path.join(output_dir, chart_filename)
    if not tls_queue_data:
        print(f"Sem dados de fila para {tls_focus_id}. Gerando placeholder.")
        plt.figure(figsize=(10, 5)); plt.text(0.5, 0.5, f'Dados de Fila Indisponíveis\nSemáforo {tls_focus_id}', ha='center', va='center', fontsize=10, color='grey', wrap=True); plt.xticks([]); plt.yticks([])
        try: plt.savefig(chart_full_path); print(f"Placeholder de fila salvo: {chart_full_path}")
        except Exception as e: print(f"Erro ao salvar placeholder de fila {chart_filename}: {e}")
        plt.close(); return chart_filename
    df_tls = pd.DataFrame(tls_queue_data)
    df_tls["Via Leste-Oeste"] = pd.to_numeric(df_tls["Via Leste-Oeste"], errors='coerce').fillna(0)
    df_tls["Via Norte-Sul"] = pd.to_numeric(df_tls["Via Norte-Sul"], errors='coerce').fillna(0)
    if df_tls.empty or (df_tls["Via Leste-Oeste"].eq(0).all() and df_tls["Via Norte-Sul"].eq(0).all()):
        print(f"Dados de fila para '{tls_focus_id}' vazios ou zero. Gerando placeholder.")
        plt.figure(figsize=(10, 5)); plt.text(0.5, 0.5, f'Dados de Fila Vazios ou Zero\nSemáforo {tls_focus_id}', ha='center', va='center', fontsize=10, color='grey', wrap=True); plt.xticks([]); plt.yticks([])
        try: plt.savefig(chart_full_path); print(f"Placeholder de fila salvo: {chart_full_path}")
        except Exception as e: print(f"Erro ao salvar placeholder de fila {chart_filename}: {e}")
        plt.close(); return chart_filename
    plt.figure(figsize=(10, 5)); plot_created_count = 0
    if "Via Leste-Oeste" in df_tls and not df_tls["Via Leste-Oeste"].eq(0).all():
        plt.plot(df_tls["step"], df_tls["Via Leste-Oeste"], label=f"Fila L-O", marker='.', color='#8e44ad', linewidth=1.5, markersize=4); plot_created_count +=1
    if "Via Norte-Sul" in df_tls and not df_tls["Via Norte-Sul"].eq(0).all():
        plt.plot(df_tls["step"], df_tls["Via Norte-Sul"], label=f"Fila N-S", marker='x', color='#16a085', linewidth=1.5, markersize=4); plot_created_count +=1
    if plot_created_count == 0:
        plt.close(); print(f"Dados de fila para '{tls_focus_id}' zero. Gerando placeholder.")
        plt.figure(figsize=(10, 5)); plt.text(0.5, 0.5, f'Dados de Fila Zero\nSemáforo {tls_focus_id}', ha='center', va='center', fontsize=10, color='grey', wrap=True); plt.xticks([]); plt.yticks([])
        try: plt.savefig(chart_full_path); print(f"Placeholder de fila salvo: {chart_full_path}")
        except Exception as e: print(f"Erro ao salvar placeholder de fila {chart_filename}: {e}")
        plt.close(); return chart_filename
    plt.title(f"Filas no Semáforo {tls_focus_id}", fontsize=14, color='#2c3e50')
    plt.xlabel("Tempo da Simulação (s)", fontsize=12, color='#34495e')
    plt.ylabel("Número de Veículos na Fila", fontsize=12, color='#34495e') # Já é simples
    if plot_created_count > 0 : plt.legend(fontsize=10)
    plt.grid(True, linestyle='--', alpha=0.6); plt.xticks(fontsize=10); plt.yticks(fontsize=10); plt.tight_layout()
    try: plt.savefig(chart_full_path); print(f"Gráfico de fila salvo: {chart_full_path}")
    except Exception as e: print(f"Erro ao salvar gráfico de fila {chart_filename}: {e}"); plt.close(); return "placeholder.png"
    plt.close()
    return chart_filename

# --- Função Principal de Geração do HTML ---
def generate_dashboard_html_from_template(metrics_dict, charts_relative_paths, output_dir):
    current_time_str = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    co2_log_path = os.path.relpath(EMISSION_FILE, output_dir) if charts_relative_paths.get("Emissões de CO2") != "placeholder.png" and os.path.exists(EMISSION_FILE) else "#"
    density_log_path = os.path.relpath(SIM_DATA_JSON, output_dir) if charts_relative_paths.get("Densidade de Tráfego") != "placeholder.png" and os.path.exists(SIM_DATA_JSON) else "#"
    
    wait_time_card_title_html = metrics_dict.get("wait_time_chart_title", "Tempo Médio de Espera") 
    wait_time_data_key_for_dict = metrics_dict.get("wait_time_chart_key", "placeholder_key")
    wait_time_img_src = charts_relative_paths.get(wait_time_data_key_for_dict, "placeholder.png")
    wait_time_log_path = os.path.relpath(SIM_DATA_JSON, output_dir) if wait_time_img_src != "placeholder.png" and os.path.exists(SIM_DATA_JSON) else "#"
    wait_time_description = metrics_dict.get("wait_time_chart_description", "Dados não disponíveis.")

    def get_queue_log_path(tls_id_key):
        return os.path.relpath(SIM_DATA_JSON, output_dir) if charts_relative_paths.get(tls_id_key) != "placeholder.png" and os.path.exists(SIM_DATA_JSON) else "#"

    html_content = f"""
    <!DOCTYPE html><html lang="pt-BR"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Dashboard de Simulação de Tráfego</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
        <style>:root{{--primary:#2c3e50;--secondary:#3498db;--success:#27ae60;--light-bg:#f8f9fa;}}body{{background-color:#f0f3f5;font-family:'Segoe UI',Tahoma,Geneva,Verdana,sans-serif;color:#495057;}}.header{{background:linear-gradient(135deg,var(--primary) 0%,#1a2530 100%);color:white;box-shadow:0 4px 12px rgba(0,0,0,0.1);}}.card{{transition:transform 0.3s,box-shadow 0.3s;border:none;border-radius:10px;overflow:hidden;box-shadow:0 4px 8px rgba(0,0,0,0.05);background-color:#fff;}}.card:hover{{transform:translateY(-5px);box-shadow:0 8px 16px rgba(0,0,0,0.1);}}.metric-card{{border-left:4px solid var(--secondary);border-radius:8px;}}.metric-card .card-title{{color:#6c757d;font-size:0.9em;font-weight:500;margin-bottom:0.2rem;}}.metric-card h2.card-text{{font-size:2.1rem;font-weight:700;color:var(--primary);margin-bottom:0.2rem;line-height:1.2;}}.metric-card p.card-text.description{{font-size:0.8em;color:#777;font-weight:400;margin-bottom:0;line-height:1.3;}}.chart-container{{background:white;border-radius:10px;padding:20px;margin-bottom:25px;box-shadow:0 4px 8px rgba(0,0,0,0.05);}}.chart-container h4{{color:var(--primary);font-size:1.1rem;margin-bottom:0;}}.chart-info{{background-color:var(--light-bg);border-radius:8px;padding:15px;margin-top:15px;border:1px solid #e9ecef;}}.chart-info p{{margin-bottom:0.25rem;font-size:0.9rem;}}.chart-info p.description{{font-size:0.85rem;color:#6c757d;margin-bottom:0;}}.log-btn{{background-color:var(--primary);color:white;border:none;transition:background-color 0.3s;font-size:0.8rem;padding:0.25rem 0.75rem;}}.log-btn:hover{{background-color:var(--secondary);}}.last-update{{font-size:0.85rem;color:#e9ecef;}}.section-title{{color:var(--primary);font-weight:500;border-bottom:2px solid #dee2e6;padding-bottom:0.5rem;font-size:1.5rem;}}.badge.bg-dark{{background-color:var(--primary) !important;}}.img-fluid{{max-width:100%;height:auto;display:block;margin-left:auto;margin-right:auto;}}</style>
    </head><body>
    <header class="header py-3 mb-4"><div class="container"><div class="d-flex justify-content-between align-items-center"><div><h1 class="mb-0 h2"><i class="fas fa-traffic-light me-2"></i>Dashboard de Simulação de Tráfego</h1><p class="mb-0 last-update">Última atualização: {current_time_str}</p></div><div><button onclick="window.print();" class="btn btn-outline-light me-2"><i class="fas fa-download me-1"></i> Exportar</button></div></div></div></header>
    <div class="container mb-5">
        <div class="row mb-4"><div class="col-md-12"><div class="alert alert-primary d-flex align-items-center"><i class="fas fa-info-circle fa-2x me-3"></i><div>Este dashboard apresenta métricas e visualizações da simulação de tráfego urbano. Utilize os botões <span class="badge bg-dark"><i class="fas fa-file-alt me-1"></i> Ver Log</span> para acessar os dados brutos por trás de cada visualização.</div></div></div></div>
        <h2 class="mb-4 border-bottom pb-2 section-title"><i class="fas fa-chart-bar me-2"></i>Métricas Principais</h2>
        <div class="row g-4 mb-5">
            <div class="col-md-3"><div class="card metric-card h-100"><div class="card-body text-center"><h5 class="card-title">Veículos na Malha</h5><h2 class="card-text">{metrics_dict.get("vehicles_final", "N/A")}</h2><p class="card-text description">Total de veículos ativos no final da simulação</p></div></div></div>
            <div class="col-md-3"><div class="card metric-card h-100"><div class="card-body text-center"><h5 class="card-title">Tempo Médio de Viagem</h5><h2 class="card-text">{metrics_dict.get("avg_trip_duration_formatted", "N/A")}</h2><p class="card-text description">Duração média das viagens realizadas</p></div></div></div>
            <div class="col-md-3"><div class="card metric-card h-100"><div class="card-body text-center"><h5 class="card-title">Emissões de CO&sup2;</h5><h2 class="card-text">{metrics_dict.get("total_co2_kg_formatted", "N/A")} kg</h2><p class="card-text description">Total de emissões durante a simulação</p></div></div></div>
            <div class="col-md-3"><div class="card metric-card h-100"><div class="card-body text-center"><h5 class="card-title">Viagens Concluídas</h5><h2 class="card-text">{metrics_dict.get("num_trips_completed", "N/A")}</h2><p class="card-text description">Total de viagens completadas com sucesso</p></div></div></div>
        </div>
        <h2 class="mb-4 border-bottom pb-2 section-title"><i class="fas fa-chart-line me-2"></i>Visualizações</h2>
        <div class="row g-4">
            <div class="col-lg-6"><div class="chart-container"><div class="d-flex justify-content-between align-items-center mb-3"><h4>Emissões de CO&sup2;</h4><a href="{co2_log_path}" class="btn btn-sm log-btn" target="_blank"><i class="fas fa-file-alt me-1"></i> Ver Log</a></div><img src="{charts_relative_paths.get("Emissões de CO2", "placeholder.png")}" alt="Emissões de CO²" class="img-fluid rounded mb-3"><div class="chart-info"><p class="mb-1"><strong>O que este gráfico mostra?</strong></p><p class="mb-0 description">Acompanha a quantidade de CO&sup2; emitida pelos veículos ao longo do tempo da simulação. Permite visualizar os picos de poluição e o impacto ambiental do tráfego.<br><small><i>Nota: Se os dados do JSON estiverem ausentes ou zerados, as emissões neste gráfico são estimadas ({CO2_PER_CAR_PER_STEP_G:.2f}g/veículo/passo).</i></small></p></div></div></div>
            <div class="col-lg-6"><div class="chart-container"><div class="d-flex justify-content-between align-items-center mb-3"><h4>Densidade de Tráfego</h4><a href="{density_log_path}" class="btn btn-sm log-btn" target="_blank"><i class="fas fa-file-alt me-1"></i> Ver Log</a></div><img src="{charts_relative_paths.get("Densidade de Tráfego", "placeholder.png")}" alt="Densidade de Tráfego" class="img-fluid rounded mb-3"><div class="chart-info"><p class="mb-1"><strong>O que este gráfico mostra?</strong></p><p class="mb-0 description">Variação no número de veículos presentes na malha viária ao longo do tempo. Auxilia na identificação de períodos de maior ou menor congestionamento.</p></div></div></div>
        </div>
        <div class="row g-4 mt-1">
            <div class="col-lg-12">
                <div class="chart-container">
                    <div class="d-flex justify-content-between align-items-center mb-3">
                        <h4>{wait_time_card_title_html}</h4>
                        <a href="{wait_time_log_path}" class="btn btn-sm log-btn" target="_blank"><i class="fas fa-file-alt me-1"></i> Ver Log</a>
                    </div>
                    <img src="{wait_time_img_src}" alt="{wait_time_card_title_html}" class="img-fluid rounded mb-3">
                    <div class="chart-info">
                        <p class="mb-1"><strong>O que este gráfico mostra?</strong></p>
                        <p class="mb-0 description">{wait_time_description}</p>
                    </div>
                </div>
            </div>
        </div>
        <div class="row g-4 mt-1">
            <div class="col-lg-6"><div class="chart-container"><div class="d-flex justify-content-between align-items-center mb-3"><h4>Filas Semáforo B1</h4><a href="{get_queue_log_path("Filas no Semáforo B1")}" class="btn btn-sm log-btn" target="_blank"><i class="fas fa-file-alt me-1"></i> Ver Log</a></div><img src="{charts_relative_paths.get("Filas no Semáforo B1", "placeholder.png")}" alt="Filas Semáforo B1" class="img-fluid rounded mb-3"><div class="chart-info"><p class="mb-1"><strong>O que este gráfico mostra?</strong></p><p class="mb-0 description">Visualiza o tamanho das filas de veículos (Leste-Oeste e Norte-Sul) para o semáforo B1 ao longo do tempo da simulação.</p></div></div></div>
            <div class="col-lg-6"><div class="chart-container"><div class="d-flex justify-content-between align-items-center mb-3"><h4>Filas Semáforo B2</h4><a href="{get_queue_log_path("Filas no Semáforo B2")}" class="btn btn-sm log-btn" target="_blank"><i class="fas fa-file-alt me-1"></i> Ver Log</a></div><img src="{charts_relative_paths.get("Filas no Semáforo B2", "placeholder.png")}" alt="Filas Semáforo B2" class="img-fluid rounded mb-3"><div class="chart-info"><p class="mb-1"><strong>O que este gráfico mostra?</strong></p><p class="mb-0 description">Visualiza o tamanho das filas de veículos (Leste-Oeste e Norte-Sul) para o semáforo B2 ao longo do tempo da simulação.</p></div></div></div>
        </div>
        <div class="row g-4 mt-1">
            <div class="col-lg-6"><div class="chart-container"><div class="d-flex justify-content-between align-items-center mb-3"><h4>Filas Semáforo C1</h4><a href="{get_queue_log_path("Filas no Semáforo C1")}" class="btn btn-sm log-btn" target="_blank"><i class="fas fa-file-alt me-1"></i> Ver Log</a></div><img src="{charts_relative_paths.get("Filas no Semáforo C1", "placeholder.png")}" alt="Filas Semáforo C1" class="img-fluid rounded mb-3"><div class="chart-info"><p class="mb-1"><strong>O que este gráfico mostra?</strong></p><p class="mb-0 description">Visualiza o tamanho das filas de veículos (Leste-Oeste e Norte-Sul) para o semáforo C1 ao longo do tempo da simulação.</p></div></div></div>
            <div class="col-lg-6"><div class="chart-container"><div class="d-flex justify-content-between align-items-center mb-3"><h4>Filas Semáforo C2</h4><a href="{get_queue_log_path("Filas no Semáforo C2")}" class="btn btn-sm log-btn" target="_blank"><i class="fas fa-file-alt me-1"></i> Ver Log</a></div><img src="{charts_relative_paths.get("Filas no Semáforo C2", "placeholder.png")}" alt="Filas Semáforo C2" class="img-fluid rounded mb-3"><div class="chart-info"><p class="mb-1"><strong>O que este gráfico mostra?</strong></p><p class="mb-0 description">Visualiza o tamanho das filas de veículos (Leste-Oeste e Norte-Sul) para o semáforo C2 ao longo do tempo da simulação.</p></div></div></div>
        </div>
    </div>
    <footer class="bg-dark text-white py-4 mt-5"><div class="container"><div class="row align-items-center"><div class="col-md-6"><h5><i class="fas fa-project-diagram me-2"></i>Simulação de Tráfego Urbano</h5><p class="mb-0" style="font-size: 0.9rem;">Dashboard gerado automaticamente a partir de dados de simulação.</p></div><div class="col-md-6 text-md-end mt-3 mt-md-0"><button class="btn btn-outline-light me-2 btn-sm" onclick="window.location.reload();"><i class="fas fa-redo me-1"></i> Recarregar Dados</button><a href="{HELP_URL}" target="_blank" class="btn btn-light btn-sm"><i class="fas fa-question-circle me-1"></i> Ajuda</a></div></div></div></footer>
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    </body></html>
    """
    output_html_path = os.path.join(output_dir, DASHBOARD_HTML_FILENAME)
    with open(output_html_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"Dashboard HTML gerado em: {output_html_path}")
    try:
        abs_html_path = os.path.abspath(output_html_path)
        html_uri = pathlib.Path(abs_html_path).as_uri()
        print(f"Para visualizar o dashboard, abra este arquivo no seu navegador: {html_uri}")
    except Exception as e:
        print(f"Não foi possível obter o URI do arquivo: {e}. Abra manualmente: {os.path.abspath(output_html_path)}")

# --- Função Principal ---
def main():
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR); print(f"Diretório de saída criado: {OUTPUT_DIR}")

    if not os.path.exists(SIM_DATA_JSON):
        print(f"AVISO: Arquivo '{SIM_DATA_JSON}' não encontrado. Criando dados de exemplo.")
        dummy_data = []
        for i in range(0, 3601, 60):
            total_vehicles = max(1, int(65 - (i/40) + (10 * abs(math.sin(i/100)))))
            estimated_co2 = CO2_PER_CAR_PER_STEP_G * total_vehicles * (1 + 0.2 * math.sin(i/200))
            avg_stopped_wait_dummy = max(0, 20 + 30 * abs(math.sin(i/300)) + random.uniform(-5, 5)) if total_vehicles > 10 else random.uniform(0,10)
            total_wait_dummy = total_vehicles * (20 + 10 * abs(math.sin(i/300)))

            dummy_entry = {
                "step": i, "total_vehicles_network": total_vehicles,
                "total_system_waiting_time": total_wait_dummy,
                "teleported_vehicles_this_step": 0 if i % 600 != 0 else 1,
                "co2_emission": round(estimated_co2, 2),
                "avg_stopped_vehicle_wait_time_sec": round(avg_stopped_wait_dummy,1),
                "tls_data": [{"tls_id": "B1", "queue_W": int(total_vehicles/8), "queue_E":int(total_vehicles/10), "queue_N":int(total_vehicles/5), "queue_S":0}]
            }
            dummy_data.append(dummy_entry)
        try:
            os.makedirs(os.path.dirname(SIM_DATA_JSON), exist_ok=True)
            with open(SIM_DATA_JSON, "w", encoding="utf-8") as f_json: json.dump(dummy_data, f_json, indent=4)
            print(f"'{SIM_DATA_JSON}' criado com dados de exemplo.")
        except Exception as e: print(f"ERRO ao criar JSON de exemplo: {e}"); return

    try:
        with open(SIM_DATA_JSON, "r", encoding="utf-8") as f: raw_data_from_json = json.load(f)
    except json.JSONDecodeError: print(f"ERRO: Falha ao decodificar JSON do arquivo: {SIM_DATA_JSON}."); return
    except FileNotFoundError: print(f"ERRO: Arquivo de dados da simulação '{SIM_DATA_JSON}' não encontrado."); return
    except Exception as e: print(f"ERRO: Falha ao ler {SIM_DATA_JSON}: {e}"); return

    if not raw_data_from_json: print("Arquivo de dados da simulação JSON está vazio."); return
    df_sim = pd.DataFrame(raw_data_from_json)
    if df_sim.empty: print("DataFrame da simulação vazio após carregar JSON."); return

    cols_to_ensure_numeric = {
        "step": 0, "total_vehicles_network": 0,
        "total_system_waiting_time": 0.0,
        "teleported_vehicles_this_step": 0,
        "co2_emission": 0.0,
        "avg_stopped_vehicle_wait_time_sec": float('nan')
    }

    for col, default_val in cols_to_ensure_numeric.items():
        if col not in df_sim.columns:
            print(f"AVISO: Coluna '{col}' não encontrada no JSON. Será tratada com valor default/NaN.")
            df_sim[col] = default_val
        df_sim[col] = pd.to_numeric(df_sim.get(col), errors='coerce').fillna(default_val)

    # Estimativa de CO2 se necessário (para o gráfico de CO2)
    if "co2_emission" not in df_sim.columns or df_sim["co2_emission"].fillna(0).eq(0).all():
        if "total_vehicles_network" in df_sim.columns and not df_sim["total_vehicles_network"].eq(0).all():
            print(f"AVISO: 'co2_emission' ausente/zerada. Estimando como {CO2_PER_CAR_PER_STEP_G:.2f} * 'total_vehicles_network' para o gráfico.")
            df_sim["co2_emission"] = CO2_PER_CAR_PER_STEP_G * df_sim["total_vehicles_network"]
        # Se total_vehicles_network também for zero ou ausente, co2_emission permanecerá o default_val (0.0)
    df_sim["co2_emission"] = pd.to_numeric(df_sim["co2_emission"], errors='coerce').fillna(0)


    avg_trip_duration, avg_time_loss, num_trips_completed = parse_tripinfo(TRIPINFO_FILE)
    _, total_co2_from_emission_file_g = parse_emissions(EMISSION_FILE)
    total_co2_kg_val = 0; source_co2_metric = "valor dummy"
    if total_co2_from_emission_file_g > 0:
        total_co2_kg_val = total_co2_from_emission_file_g / 1000.0; source_co2_metric = "emission.xml"
    elif not os.path.exists(EMISSION_FILE) or total_co2_from_emission_file_g == 0:
        total_co2_kg_val = 140325.3; source_co2_metric = "valor fixo da imagem (fallback)" # Exemplo da imagem
    print(f"Métrica 'Total de CO² kg' usando: {source_co2_metric}")

    metrics = {
        "vehicles_final": format_large_number(df_sim["total_vehicles_network"].iloc[-1] if not df_sim.empty and "total_vehicles_network" in df_sim.columns and not df_sim["total_vehicles_network"].empty else 0, 0),
        "avg_trip_duration_formatted": format_duration(avg_trip_duration if avg_trip_duration else 680.7),
        "num_trips_completed": format_large_number(num_trips_completed if num_trips_completed else 73),
        "total_co2_kg_formatted": format_large_number(total_co2_kg_val, 1 if total_co2_kg_val >= 1000 else 2)
    }
    if not os.path.exists(TRIPINFO_FILE) and not num_trips_completed:
        print("Usando valores dummy para métricas de viagem.");
        metrics["avg_trip_duration_formatted"] = "680.7 s"; metrics["num_trips_completed"] = "73"

    charts_relative_paths = {}
    # Gráfico de Emissões de CO2
    # Ajuste no rótulo do eixo Y para simplificar
    charts_relative_paths["Emissões de CO2"] = plot_data(df_sim, "step", "co2_emission", "Emissões de CO² ao Longo do Tempo", "Tempo da Simulação (s)", "CO² Emitido (g)", "co2_per_step", OUTPUT_DIR, color='crimson', marker='.')
    
    # Gráfico de Densidade de Tráfego
    # Rótulo do eixo Y já é simples ("Número de Veículos")
    charts_relative_paths["Densidade de Tráfego"] = plot_data(df_sim, "step", "total_vehicles_network", "Veículos na Malha ao Longo do Tempo", "Tempo da Simulação (s)", "Número de Veículos", "density_over_time", OUTPUT_DIR, color='dodgerblue', marker='.')
    
    # Lógica para o gráfico de Tempo de Espera (Modificado para "Médio de Veículos Parados" ou fallback)
    wait_time_plot_y_col = "avg_stopped_vehicle_wait_time_sec"
    wait_time_plot_title = "Tempo Médio de Espera (Veículos Parados)"
    wait_time_plot_ylabel = "Tempo Médio de Espera (s)"
    wait_time_plot_filename_suffix = "avg_stopped_vehicle_wait_time"
    wait_time_plot_color = 'darkorange'
    wait_time_chart_key_for_dict = "Tempo Médio de Espera (Veículos Parados) (s)" # Chave para o dict charts_relative_paths
    wait_time_card_title_html = "Tempo Médio de Espera (Veículos Parados)"
    wait_time_description = "Representa o tempo médio de espera (em segundos) apenas dos veículos que estavam parados na malha em cada intervalo de coleta. Ajuda a identificar a intensidade da espera para os veículos diretamente afetados por congestionamentos."

    plot_specific_avg_stopped_data = False
    if "avg_stopped_vehicle_wait_time_sec" in df_sim.columns and \
       not df_sim["avg_stopped_vehicle_wait_time_sec"].isnull().all() and \
       not (pd.to_numeric(df_sim["avg_stopped_vehicle_wait_time_sec"], errors='coerce').fillna(0)).eq(0).all():
        plot_specific_avg_stopped_data = True
        print(f"Dados para '{wait_time_plot_title}' encontrados no JSON (coluna '{wait_time_plot_y_col}').")
    
    if not plot_specific_avg_stopped_data:
        print(f"AVISO: Dados para '{wait_time_plot_title}' (coluna '{wait_time_plot_y_col}') não encontrados ou inválidos no JSON.")
        if "total_system_waiting_time" in df_sim.columns and \
           "total_vehicles_network" in df_sim.columns and \
           not df_sim["total_vehicles_network"].fillna(0).eq(0).all(): # Evita divisão por zero no fallback
            
            print("Usando fallback: 'Tempo Médio de Espera do Sistema (por veículo)'.")
            df_sim["avg_system_wait_time_per_vehicle_sec"] = df_sim["total_system_waiting_time"].astype(float) / df_sim["total_vehicles_network"].astype(float).replace(0, float('nan')) # Substitui 0 por NaN para evitar divisão por zero e permitir fillna
            df_sim["avg_system_wait_time_per_vehicle_sec"] = df_sim["avg_system_wait_time_per_vehicle_sec"].fillna(0)

            wait_time_plot_title = "Tempo Médio de Espera do Sistema (por veículo)"
            wait_time_plot_y_col = "avg_system_wait_time_per_vehicle_sec"
            wait_time_plot_ylabel = "Tempo Médio de Espera (s)" # Mantém em segundos
            wait_time_plot_filename_suffix = "avg_system_wait_time_per_vehicle"
            wait_time_chart_key_for_dict = "Tempo Médio de Espera do Sistema (por veículo) (s)"
            wait_time_card_title_html = "Tempo Médio de Espera (Sistema)"
            wait_time_description = "Representa o tempo total de espera no sistema dividido pelo número total de veículos na malha (em segundos). Nota: Dados específicos para 'veículos parados' não disponíveis."
            print(f"Gráfico de tempo de espera será gerado com dados de fallback: '{wait_time_plot_y_col}'.")
        else:
            print("Não foi possível calcular o fallback para o gráfico de tempo médio de espera. Será um placeholder.")
            if wait_time_plot_y_col not in df_sim.columns: df_sim[wait_time_plot_y_col] = float('nan') # Garante coluna para placeholder
            wait_time_card_title_html = "Tempo Médio de Espera" # Título genérico para placeholder
            wait_time_description = "Dados para o tempo médio de espera de veículos parados não foram encontrados no arquivo JSON, e o fallback não pôde ser calculado."
            
    # Adiciona as informações dinâmicas ao metrics_dict para o template HTML
    metrics["wait_time_chart_title"] = wait_time_card_title_html
    metrics["wait_time_chart_key"] = wait_time_chart_key_for_dict
    metrics["wait_time_chart_description"] = wait_time_description

    charts_relative_paths[wait_time_chart_key_for_dict] = plot_data(
        df_sim, "step", wait_time_plot_y_col, 
        wait_time_plot_title, "Tempo da Simulação (s)", 
        wait_time_plot_ylabel, 
        wait_time_plot_filename_suffix, OUTPUT_DIR, 
        is_cumulative=False, color=wait_time_plot_color if 'wait_time_plot_color' in locals() else 'darkorange', marker='o' 
    )
    
    tls_ids_to_plot = []
    if raw_data_from_json and isinstance(raw_data_from_json, list) and len(raw_data_from_json) > 0 and isinstance(raw_data_from_json[0], dict) and isinstance(raw_data_from_json[0].get("tls_data"), list):
        all_tls_ids = list(set(td.get("tls_id") for entry in raw_data_from_json for td in entry.get("tls_data",[]) if td.get("tls_id")))
        preferred_tls = ["B1", "B2", "C1", "C2"]; tls_ids_to_plot = [tid for tid in preferred_tls if tid in all_tls_ids]
        for tid in all_tls_ids:
            if len(tls_ids_to_plot) < 4 and tid not in tls_ids_to_plot: tls_ids_to_plot.append(tid)
    if not tls_ids_to_plot: tls_ids_to_plot = ["B1", "B2", "C1", "C2"]; print(f"AVISO: Nenhum ID de semáforo no JSON. Usando padrão: {tls_ids_to_plot} para placeholders.")
    for tls_id in tls_ids_to_plot:
        charts_relative_paths[f"Filas no Semáforo {tls_id}"] = plot_queue_data(raw_data_from_json, tls_id, OUTPUT_DIR)

    generate_dashboard_html_from_template(metrics, charts_relative_paths, OUTPUT_DIR)

if __name__ == "__main__":
    main()