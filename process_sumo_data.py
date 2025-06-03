import json
import pandas as pd
import matplotlib.pyplot as plt
import os
import xml.etree.ElementTree as ET # Para ler o emission.xml

DATA_FILE = os.path.join("dashboard_output", "simulation_dashboard_data.json")
EMISSION_FILE = "emission.xml" # Gerado pela simulação
TRIPINFO_FILE = "tripinfo.xml" # Gerado pela simulação
OUTPUT_DIR = "dashboard_output"

def parse_emissions(emission_file):
    """Analisa o arquivo de emissões para obter CO2 total por intervalo."""
    co2_data = {} # step -> total_co2_at_step
    try:
        tree = ET.parse(emission_file)
        root = tree.getroot()
        for timestep in root.findall('timestep'):
            time = float(timestep.get('time'))
            # Coleta CO2 de todos os veículos naquele timestep
            # A estrutura pode variar um pouco dependendo da versão do SUMO e das opções de saída
            # Este é um exemplo genérico. Pode ser necessário ajustar para CO2_abs ou similar.
            # Para este exemplo, vamos apenas contar o número de entradas de emissão como proxy
            # ou somar um atributo específico se conhecido.
            # Se você tem CO2_abs:
            # current_co2 = sum(float(vehicle.get('CO2_abs', 0)) for vehicle in timestep.findall('vehicle'))
            # Por simplicidade, vamos apenas verificar se há dados de emissão.
            # Para um cálculo real de CO2, você precisaria garantir que 'CO2_abs' ou similar está no output.
            # Aqui, vamos simular um aumento de CO2 para demonstração.
            # Em uma implementação real, você extrairia o valor real de CO2.
            if time not in co2_data:
                co2_data[time] = 0
            # Exemplo simulado:
            co2_data[time] += random.uniform(50, 200) * len(timestep.findall('vehicle')) # Simulação de valor de CO2
    except FileNotFoundError:
        print(f"Arquivo de emissões '{emission_file}' não encontrado.")
    except ET.ParseError:
        print(f"Erro ao analisar o arquivo de emissões '{emission_file}'.")
    return co2_data

def parse_tripinfo(tripinfo_file):
    """Analisa o arquivo tripinfo para obter tempos de viagem e perdas de tempo."""
    total_duration = 0
    total_time_loss = 0
    num_trips = 0
    try:
        tree = ET.parse(tripinfo_file)
        root = tree.getroot()
        for tripinfo in root.findall('tripinfo'):
            total_duration += float(tripinfo.get('duration', 0))
            total_time_loss += float(tripinfo.get('timeLoss', 0))
            num_trips += 1
    except FileNotFoundError:
        print(f"Arquivo tripinfo '{tripinfo_file}' não encontrado.")
    except ET.ParseError:
        print(f"Erro ao analisar o arquivo tripinfo '{tripinfo_file}'.")
    
    avg_duration = total_duration / num_trips if num_trips > 0 else 0
    avg_time_loss = total_time_loss / num_trips if num_trips > 0 else 0
    return avg_duration, avg_time_loss, num_trips


def generate_dashboard_html(metrics, charts_paths):
    """Gera um arquivo HTML simples para o dashboard."""
    # Converte caminhos de arquivo para serem relativos ao HTML, se estiverem na mesma pasta de saída
    relative_charts_paths = {title: os.path.basename(path) if path else None for title, path in charts_paths.items()}

    html_content = f"""
    <!DOCTYPE html>
    <html lang="pt-BR">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Dashboard da Simulação SUMO</title>
        <style>
            body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; padding: 0; background-color: #f0f2f5; color: #333; display: flex; flex-direction: column; align-items: center; }}
            .header {{ background-color: #2c3e50; color: white; padding: 20px; text-align: center; width: 100%; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
            .container {{ width: 90%; max-width: 1200px; margin: 20px auto; background-color: #fff; padding: 25px; border-radius: 8px; box-shadow: 0 0 15px rgba(0,0,0,0.1); }}
            h1 {{ color: #fff; margin:0; font-size: 2em;}}
            h2 {{ color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 10px; margin-top: 30px; }}
            .metrics-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; margin-bottom: 30px; }}
            .metric {{ background-color: #ecf0f1; border: 1px solid #bdc3c7; padding: 20px; border-radius: 6px; text-align: center; }}
            .metric h3 {{ margin-top: 0; color: #3498db; font-size: 1.1em; }}
            .metric p {{ font-size: 1.8em; font-weight: bold; color: #2c3e50; margin: 10px 0 0 0;}}
            .charts-grid {{ display: grid; grid-template-columns: 1fr; gap: 30px; }}
            .chart {{ background-color: #fdfdfd; padding: 20px; border-radius: 6px; box-shadow: 0 0 10px rgba(0,0,0,0.05); }}
            .chart h3 {{ text-align: center; color: #3498db;}}
            img {{ max-width: 100%; height: auto; border: 1px solid #ddd; border-radius: 4px; display: block; margin: 0 auto; }}
            footer {{ text-align: center; margin-top: 30px; padding: 15px; color: #7f8c8d; font-size: 0.9em; width:100%; background-color: #e0e0e0; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>Dashboard da Simulação de Tráfego Inteligente</h1>
        </div>
        <div class="container">
            
            <h2>Métricas Gerais da Simulação</h2>
            <div class="metrics-grid">
                <div class="metric">
                    <h3>Veículos na Rede (Final)</h3>
                    <p>{metrics.get("last_total_vehicles", "N/A")}</p>
                </div>
                <div class="metric">
                    <h3>Tempo de Espera Total (Sistema)</h3>
                    <p>{metrics.get("total_system_waiting_time", 0):.2f} s</p>
                </div>
                <div class="metric">
                    <h3>Total de Teletransportes</h3>
                    <p>{metrics.get("total_teleported", "N/A")}</p>
                </div>
                <div class="metric">
                    <h3>Duração Média de Viagem</h3>
                    <p>{metrics.get("avg_trip_duration", 0):.2f} s</p>
                </div>
                <div class="metric">
                    <h3>Perda de Tempo Média por Viagem</h3>
                    <p>{metrics.get("avg_time_loss", 0):.2f} s</p>
                </div>
                 <div class="metric">
                    <h3>Total de Viagens Completas</h3>
                    <p>{metrics.get("num_trips_completed", "N/A")}</p>
                </div>
            </div>

            <h2>Visualizações Gráficas</h2>
            <div class="charts-grid">
    """

    for chart_title, chart_path in relative_charts_paths.items():
        if chart_path:
            html_content += f"""
            <div class="chart">
                <h3>{chart_title}</h3>
                <img src="{chart_path}" alt="{chart_title}">
            </div>
            """
        else:
            html_content += f"<p>Gráfico '{chart_title}' não pôde ser gerado (dados insuficientes ou erro).</p>"

    html_content += """
            </div>
        </div>
        <footer>Dashboard gerado automaticamente</footer>
    </body>
    </html>
    """
    
    output_html_path = os.path.join(OUTPUT_DIR, "dashboard.html")
    with open(output_html_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"Dashboard HTML gerado em: {output_html_path}")
    # Tenta abrir o dashboard no navegador padrão
    try:
        import webbrowser
        webbrowser.open_new_tab(output_html_path)
        print("Tentando abrir o dashboard no navegador padrão...")
    except Exception as e:
        print(f"Não foi possível abrir o navegador automaticamente: {e}")


def main():
    if not os.path.exists(DATA_FILE):
        print(f"Arquivo de dados '{DATA_FILE}' não encontrado. Execute a simulação primeiro.")
        return

    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    with open(DATA_FILE, "r") as f:
        raw_data = json.load(f)

    if not raw_data:
        print("Arquivo de dados da simulação está vazio.")
        return

    df = pd.DataFrame(raw_data)
    
    metrics = {}
    charts_paths = {}

    # Parse tripinfo data
    avg_trip_duration, avg_time_loss, num_trips = parse_tripinfo(TRIPINFO_FILE)
    metrics["avg_trip_duration"] = avg_trip_duration
    metrics["avg_time_loss"] = avg_time_loss
    metrics["num_trips_completed"] = num_trips

    # Parse emission data (exemplo de CO2)
    co2_by_step = parse_emissions(EMISSION_FILE)
    if co2_by_step:
        df_co2 = pd.DataFrame(list(co2_by_step.items()), columns=['step', 'co2_simulated'])
        df = pd.merge(df, df_co2, on="step", how="left").fillna(0) # Adiciona ao DataFrame principal
        metrics["total_co2_simulated"] = df["co2_simulated"].sum()

        plt.figure(figsize=(10, 5))
        plt.plot(df["step"], df["co2_simulated"].cumsum(), marker='.', linestyle='-', color='brown')
        plt.title("Emissão de CO2 (Simulada) Acumulada")
        plt.xlabel("Passo da Simulação (s)")
        plt.ylabel("CO2 (Simulado) Acumulado")
        plt.grid(True)
        chart_path = os.path.join(OUTPUT_DIR, "co2_over_time.png")
        plt.savefig(chart_path)
        plt.close()
        charts_paths["Emissão de CO2 Acumulada"] = chart_path
    else:
        charts_paths["Emissão de CO2 Acumulada"] = None


    if not df.empty:
        metrics["last_total_vehicles"] = df["total_vehicles_network"].iloc[-1] if "total_vehicles_network" in df and not df["total_vehicles_network"].empty else 0
        metrics["total_system_waiting_time"] = df["total_system_waiting_time"].sum() if "total_system_waiting_time" in df else 0
        metrics["total_teleported"] = df["teleported_vehicles_this_step"].sum() if "teleported_vehicles_this_step" in df else 0
        
        if "step" in df and "total_vehicles_network" in df:
            plt.figure(figsize=(10, 5))
            plt.plot(df["step"], df["total_vehicles_network"], marker='o', linestyle='-')
            plt.title("Total de Veículos na Rede ao Longo do Tempo")
            plt.xlabel("Passo da Simulação (s)"); plt.ylabel("Número de Veículos"); plt.grid(True)
            chart_path = os.path.join(OUTPUT_DIR, "total_vehicles_over_time.png")
            plt.savefig(chart_path); plt.close(); charts_paths["Total de Veículos na Rede"] = chart_path
        else: charts_paths["Total de Veículos na Rede"] = None

        if "step" in df and "total_system_waiting_time" in df:
            plt.figure(figsize=(10, 5))
            plt.plot(df["step"], df["total_system_waiting_time"].cumsum(), marker='o', linestyle='-')
            plt.title("Tempo de Espera Total Acumulado no Sistema"); plt.xlabel("Passo da Simulação (s)")
            plt.ylabel("Tempo de Espera Acumulado (s)"); plt.grid(True)
            chart_path = os.path.join(OUTPUT_DIR, "waiting_time_over_time.png")
            plt.savefig(chart_path); plt.close(); charts_paths["Tempo de Espera Acumulado"] = chart_path
        else: charts_paths["Tempo de Espera Acumulado"] = None
            
        if "step" in df and "teleported_vehicles_this_step" in df:
            plt.figure(figsize=(10, 5))
            plt.bar(df["step"], df["teleported_vehicles_this_step"], width=max(1, df['step'].diff().min() * 0.8 if df['step'].nunique() > 1 else 50)) # Ajusta largura da barra
            plt.title("Veículos Teletransportados por Intervalo de Coleta"); plt.xlabel("Passo da Simulação (s)")
            plt.ylabel("Número de Teletransportes"); plt.grid(True)
            chart_path = os.path.join(OUTPUT_DIR, "teleported_vehicles.png")
            plt.savefig(chart_path); plt.close(); charts_paths["Veículos Teletransportados"] = chart_path
        else: charts_paths["Veículos Teletransportados"] = None

        b1_data = []
        for entry in raw_data:
            for tls_entry in entry.get("tls_data", []):
                if tls_entry.get("tls_id") == "B1": # Foco em B1 para exemplo
                    b1_data.append({
                        "step": entry["step"],
                        "b1_queue_ew": tls_entry.get("queue_W", 0) + tls_entry.get("queue_E", 0), # Soma W e E
                        "b1_queue_ns": tls_entry.get("queue_N", 0) + tls_entry.get("queue_S", 0)  # Soma N e S
                    })
        if b1_data:
            df_b1 = pd.DataFrame(b1_data)
            if not df_b1.empty and "step" in df_b1:
                plt.figure(figsize=(10, 5))
                plt.plot(df_b1["step"], df_b1["b1_queue_ew"], label="Fila Aprox. Leste-Oeste (B1)", marker='.')
                plt.plot(df_b1["step"], df_b1["b1_queue_ns"], label="Fila Aprox. Norte-Sul (B1)", marker='.')
                plt.title("Tamanho Aproximado da Fila no Semáforo B1"); plt.xlabel("Passo da Simulação (s)")
                plt.ylabel("Número de Veículos Parados"); plt.legend(); plt.grid(True)
                chart_path = os.path.join(OUTPUT_DIR, "b1_queues.png")
                plt.savefig(chart_path); plt.close(); charts_paths["Filas no Semáforo B1"] = chart_path
            else: charts_paths["Filas no Semáforo B1"] = None
        else: charts_paths["Filas no Semáforo B1"] = None
    else:
        print("DataFrame vazio, não foi possível gerar métricas ou gráficos.")

    generate_dashboard_html(metrics, charts_paths)

if __name__ == "__main__":
    main()
