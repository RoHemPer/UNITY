import os
import sys
import traci
import random
import json
from datetime import datetime

# --- Configuração do SUMO_HOME ---
if 'SUMO_HOME' in os.environ:
    tools = os.path.join(os.environ['SUMO_HOME'], 'tools')
    sys.path.append(tools)
    print(f"SUMO_HOME configurado: {os.environ['SUMO_HOME']}")
else:
    sys.exit("ERRO: A variável de ambiente SUMO_HOME não está definida.")

# --- Parâmetros de Configuração ---
SUMO_CONFIG_FILE = "grid.sumocfg" 
SUMO_BINARY = "sumo-gui"

# --- IDs dos Semáforos ---
TLS_IDS = ["A1", "A2", "B0", "B1", "B2", "B3", "C0", "C1", "C2", "C3", "D1", "D2"]

# --- Mapeamento de Detectores ---
DETECTOR_MAPPING = {
    "B0": {"W": "B0_W_DET", "E": "B0_E_DET", "S": "B0_S_DET"},
    "C0": {"W": "C0_W_DET", "E": "C0_E_DET", "S": "C0_S_DET"},
    "A1": {"N": "A1_N_DET", "S": "A1_S_DET", "E": "A1_E_DET"},
    "B1": {"N": "B1_N_DET", "S": "B1_S_DET", "E": "B1_E_DET", "W": "B1_W_DET"},
    "C1": {"N": "C1_N_DET", "S": "C1_S_DET", "E": "C1_E_DET", "W": "C1_W_DET"},
    "D1": {"N": "D1_N_DET", "S": "D1_S_DET", "W": "D1_W_DET"},
    "A2": {"N": "A2_N_DET", "S": "A2_S_DET", "E": "A2_E_DET"},
    "B2": {"N": "B2_N_DET", "S": "B2_S_DET", "E": "B2_E_DET", "W": "B2_W_DET"},
    "C2": {"N": "C2_N_DET", "S": "C2_S_DET", "E": "C2_E_DET", "W": "C2_W_DET"},
    "D2": {"N": "D2_N_DET", "S": "D2_S_DET", "W": "D2_W_DET"},
    "B3": {"N": "B3_N_DET", "W": "B3_W_DET", "E": "B3_E_DET"},
    "C3": {"N": "C3_N_DET", "W": "C3_W_DET", "E": "C3_E_DET"}
}

# --- Parâmetros de Tempo (segundos) ---
TIME_GREEN_MIN = 15
TIME_GREEN_NORMAL_BASE = 30
TIME_GREEN_EXTENDED_BASE = 60
TIME_YELLOW_DURATION = 3
TIME_ALL_RED_DURATION = 2
VEHICLE_THRESHOLD_FOR_EXTENSION = 3
VEHICLE_DIFFERENCE_FOR_PRESSURE_SWITCH = 5
COORDINATOR_INTERVAL = 10
MAX_PRIORITY_FACTOR_EFFECT = 0.6
VEHICLE_INSERTION_INTERVAL = 100
VEHICLES_PER_INSERTION = 8
D3_CONGESTION_THRESHOLD = 15  # Limiar de veículos para considerar congestionamento em D3

AVAILABLE_ROUTE_IDS = []
SIMULATION_DATA = []
TOTAL_CO2_EMITTED = 0
TOTAL_TRIP_TIME_LOSS = 0
NUM_TRIPS_COMPLETED = 0
vehicle_counter = 0


class TrafficLightController:
    def __init__(self, tls_id, detector_ids_for_tls):
        self.tls_id = tls_id
        self.detectors = detector_ids_for_tls
        self.time_in_current_phase = 0
        self.queue_lengths = {"N": 0, "S": 0, "E": 0, "W": 0}
        
        try:
            if tls_id not in traci.trafficlight.getIDList():
                print(f"ERRO: Semáforo {tls_id} não encontrado na rede")
                self.valid_program = False
                return
            
            logics = traci.trafficlight.getAllProgramLogics(tls_id)
            if not logics:
                print(f"ALERTA: Nenhuma lógica de programa encontrada para TLS {tls_id}")
                self.valid_program = False
                return
            
            self.logic = logics[0]
            self.all_phases_definitions = self.logic.phases
            self.num_total_phases = len(self.all_phases_definitions)
            self.current_phase_index = traci.trafficlight.getPhase(tls_id)
            self.valid_program = True

            self.main_green_phase_indices = []
            self.yellow_after_green = {}
            self.all_red_after_yellow = {}
            self._identify_phases()
            self._initialize_controller_state()
            
            print(f"Controlador iniciado para TLS {tls_id}: Fases verdes={self.main_green_phase_indices}")
            
        except traci.TraCIException as e:
            print(f"ERRO ao inicializar controlador para {tls_id}: {e}")
            self.valid_program = False

    def _identify_phases(self):
        potential_greens = []
        for i, phase_def in enumerate(self.all_phases_definitions):
            state = phase_def.state.lower()
            is_green_like = 'g' in state and 'y' not in state
            if is_green_like and phase_def.duration >= TIME_GREEN_MIN - 5:
                potential_greens.append({"index": i, "duration": phase_def.duration})
        
        potential_greens.sort(key=lambda x: x["duration"], reverse=True)
        if potential_greens:
            self.main_green_phase_indices.append(potential_greens[0]["index"])
            if len(potential_greens) > 1:
                self.main_green_phase_indices.append(potential_greens[1]["index"])
        
        for green_idx in self.main_green_phase_indices:
            self._find_transition_phases(green_idx)

    def _find_transition_phases(self, green_idx):
        for offset in range(1, self.num_total_phases):
            yellow_idx = (green_idx + offset) % self.num_total_phases
            state = self.all_phases_definitions[yellow_idx].state.lower()
            duration = self.all_phases_definitions[yellow_idx].duration
            
            if 'y' in state and 'g' not in state and duration <= TIME_YELLOW_DURATION + 2:
                self.yellow_after_green[green_idx] = yellow_idx
                self._find_all_red_phase(yellow_idx)
                return
        
        self.yellow_after_green[green_idx] = None

    def _find_all_red_phase(self, yellow_idx):
        all_red_idx = (yellow_idx + 1) % self.num_total_phases
        if all_red_idx < self.num_total_phases:
            state = self.all_phases_definitions[all_red_idx].state.lower()
            duration = self.all_phases_definitions[all_red_idx].duration
            
            if 'r' in state and 'g' not in state and 'y' not in state and duration <= TIME_ALL_RED_DURATION + 2:
                self.all_red_after_yellow[yellow_idx] = all_red_idx
                return
        
        self.all_red_after_yellow[yellow_idx] = None

    def _initialize_controller_state(self):
        self.current_main_green_group_idx_ptr = 0
        self.logic_is_alternating = len(self.main_green_phase_indices) > 1
        self.priority_factor = 0.0
        
        initial_target_phase = self.main_green_phase_indices[0]
        if self.current_phase_index != initial_target_phase:
            try:
                traci.trafficlight.setPhase(self.tls_id, initial_target_phase)
                self.current_phase_index = initial_target_phase
            except traci.TraCIException:
                pass
        
        self.time_in_current_phase = 0

    def get_active_green_phase_index(self):
        if not self.main_green_phase_indices:
            return None
        return self.main_green_phase_indices[self.current_main_green_group_idx_ptr]

    def update_detectors(self):
        for direction, det_id in self.detectors.items():
            try:
                if det_id not in traci.inductionloop.getIDList():
                    continue
                
                lane_id = traci.inductionloop.getLaneID(det_id)
                if lane_id not in traci.lane.getIDList():
                    continue
                
                self.queue_lengths[direction] = traci.lane.getLastStepHaltingNumber(lane_id)
            except traci.TraCIException:
                self.queue_lengths[direction] = 0

    def get_demand_for_active_group(self):
        if not self.main_green_phase_indices:
            return 0
            
        if self.current_main_green_group_idx_ptr == 0:
            return self.queue_lengths.get("W", 0) + self.queue_lengths.get("E", 0)
        else:
            return self.queue_lengths.get("N", 0) + self.queue_lengths.get("S", 0)

    def get_demand_for_conflicting_group(self):
        if not self.logic_is_alternating or len(self.main_green_phase_indices) < 2:
            return 0
            
        if self.current_main_green_group_idx_ptr == 0:
            return self.queue_lengths.get("N", 0) + self.queue_lengths.get("S", 0)
        else:
            return self.queue_lengths.get("W", 0) + self.queue_lengths.get("E", 0)

    def get_pressure_metric(self):
        if not self.main_green_phase_indices or not self.logic_is_alternating:
            return 0
        return self.get_demand_for_conflicting_group()

    def set_priority_factor(self, factor):
        self.priority_factor = max(-0.8, min(0.8, factor))

    def determine_green_duration(self):
        if not self.main_green_phase_indices:
            return TIME_GREEN_NORMAL_BASE
            
        active_green_idx = self.get_active_green_phase_index()
        if active_green_idx is None:
            return TIME_GREEN_NORMAL_BASE

        base_time = TIME_GREEN_NORMAL_BASE
        extended_time = TIME_GREEN_EXTENDED_BASE * (1 + (self.priority_factor * MAX_PRIORITY_FACTOR_EFFECT / 2))
        threshold = VEHICLE_THRESHOLD_FOR_EXTENSION * (1 - (abs(self.priority_factor) * MAX_PRIORITY_FACTOR_EFFECT))
        
        # Aumentar tempo verde para semáforos que alimentam D3 quando congestionado
        if self.tls_id in ["D2", "C3"]:
            extended_time *= 1.4  # +40% de tempo verde
        
        demand = self.get_demand_for_active_group()
        if demand >= threshold and self.time_in_current_phase < extended_time:
            return extended_time
        
        return base_time

    def should_switch_phase(self):
        if self.time_in_current_phase < TIME_GREEN_MIN:
            return False
            
        if self.time_in_current_phase >= self.determine_green_duration():
            return True
            
        if self.logic_is_alternating:
            current_demand = self.get_demand_for_active_group()
            conflicting_demand = self.get_demand_for_conflicting_group()
            if conflicting_demand > (current_demand + VEHICLE_DIFFERENCE_FOR_PRESSURE_SWITCH):
                return True
                
        return False

    def switch_to_next_phase(self):
        active_green_idx = self.get_active_green_phase_index()
        if active_green_idx is None:
            return
            
        current_phase = self.current_phase_index
        
        if current_phase == active_green_idx:
            return self.yellow_after_green.get(active_green_idx)
        elif current_phase in self.yellow_after_green.values():
            return self.all_red_after_yellow.get(current_phase)
        else:
            self.current_main_green_group_idx_ptr = (self.current_main_green_group_idx_ptr + 1) % len(self.main_green_phase_indices)
            return self.main_green_phase_indices[self.current_main_green_group_idx_ptr]

    def execute_phase_transition(self):
        if not self.valid_program or not self.main_green_phase_indices:
            return

        if self.current_phase_index in self.main_green_phase_indices and self.should_switch_phase():
            next_phase = self.switch_to_next_phase()
        elif self.time_in_current_phase > self.all_phases_definitions[self.current_phase_index].duration + 10:
            next_phase = self.switch_to_next_phase()
        else:
            return

        if next_phase is not None and next_phase < self.num_total_phases:
            try:
                traci.trafficlight.setPhase(self.tls_id, next_phase)
                self.current_phase_index = next_phase
                self.time_in_current_phase = 0
            except traci.TraCIException as e:
                print(f"ERRO ao mudar fase no TLS {self.tls_id}: {e}")

    def step(self, current_sim_step):
        if not self.valid_program:
            return
            
        self.time_in_current_phase += 1
        
        if current_sim_step % 5 == 0:
            self.update_detectors()
            
        self.execute_phase_transition()
        
        if current_sim_step % 300 == 0 and self.tls_id in ["B1", "C1", "B2", "C2", "D2", "C3"]:
            queues = ", ".join([f"{dir}:{q}" for dir, q in self.queue_lengths.items()])
            print(f"TLS:{self.tls_id} @{current_sim_step}s Fase:{self.current_phase_index}, "
                  f"Tempo:{self.time_in_current_phase}s, Filas: [{queues}]")


class CentralCoordinator:
    def __init__(self, controllers_map):
        self.controllers_map = controllers_map
        self.arterial_groups = {
            "NS": ["B1", "B2", "C1", "C2"],
            "EW": ["A1", "A2", "D1", "D2", "B0", "B3", "C0", "C3"]
        }
        self.d3_congestion_counter = 0  # Contador persistente de congestionamento

    def step_coordination(self, current_sim_step):
        if current_sim_step % COORDINATOR_INTERVAL != 0:
            return
            
        try:
            # Verificar congestionamento em D3
            d3_congestion = False
            if "D2" in self.controllers_map:
                d2_queues = self.controllers_map["D2"].queue_lengths
                if d2_queues.get("W", 0) > D3_CONGESTION_THRESHOLD:
                    d3_congestion = True
                    self.d3_congestion_counter += 1
                else:
                    self.d3_congestion_counter = max(0, self.d3_congestion_counter - 1)
            
            # Calcular pressões
            ns_pressure = sum(
                self.controllers_map[tls_id].get_pressure_metric()
                for tls_id in self.arterial_groups["NS"]
                if tls_id in self.controllers_map
            )
            
            ew_pressure = sum(
                self.controllers_map[tls_id].get_pressure_metric()
                for tls_id in self.arterial_groups["EW"]
                if tls_id in self.controllers_map
            )
            
            # Aumentar prioridade para EW se congestionamento persistente em D3
            if self.d3_congestion_counter > 3:  # Congestionamento persistente
                ew_pressure *= 1.8  # Aumento significativo na prioridade
                print(f"ALERTA: Congestionamento em D3 - Priorizando EW (Fator: {ew_pressure:.1f})")
            
            # Calcular fator de viés
            total_pressure = ns_pressure + ew_pressure
            if total_pressure > 0:
                pressure_diff = ns_pressure - ew_pressure
                bias_factor = pressure_diff / total_pressure * 0.8
                
                # Aplicar fator de prioridade
                for tls_id in self.arterial_groups["NS"]:
                    if tls_id in self.controllers_map:
                        self.controllers_map[tls_id].set_priority_factor(bias_factor)
                
                for tls_id in self.arterial_groups["EW"]:
                    if tls_id in self.controllers_map:
                        self.controllers_map[tls_id].set_priority_factor(-bias_factor)
        except Exception as e:
            print(f"ERRO na coordenação: {e}")


def remove_arrived_vehicles():
    try:
        arrived_ids = traci.simulation.getArrivedIDList()
        for veh_id in arrived_ids:
            try:
                if veh_id in traci.vehicle.getIDList():
                    traci.vehicle.remove(veh_id)
            except traci.TraCIException:
                pass
    except traci.TraCIException:
        pass


def insert_new_vehicles(step):
    global vehicle_counter
    
    if step % VEHICLE_INSERTION_INTERVAL != 0:
        return
        
    if not AVAILABLE_ROUTE_IDS:
        print("AVISO: Nenhuma rota disponível. Veículos não inseridos.")
        return
        
    try:
        # Filtrar rotas que não sobrecarregam D3
        safe_routes = [r for r in AVAILABLE_ROUTE_IDS if "D3" not in r]
        routes_to_use = safe_routes if safe_routes else AVAILABLE_ROUTE_IDS
        
        for i in range(VEHICLES_PER_INSERTION):
            route_id = random.choice(routes_to_use)
            vehicle_counter += 1
            veh_id = f"veh_{vehicle_counter}_{step}_{i}"
            
            try:
                traci.vehicle.add(veh_id, route_id)
                traci.vehicle.setSpeedMode(veh_id, 0)
                traci.vehicle.setVehicleClass(veh_id, "passenger")
                speed = random.uniform(8.0, 15.0)
                traci.vehicle.setMaxSpeed(veh_id, speed)
            except traci.TraCIException as e:
                print(f"Falha ao inserir veículo {veh_id} na rota {route_id}: {str(e)}")
    except Exception as e:
        print(f"ERRO na inserção de veículos: {str(e)}")


def collect_simulation_data(step, controllers_map):
    global TOTAL_CO2_EMITTED, TOTAL_TRIP_TIME_LOSS, NUM_TRIPS_COMPLETED
    
    if step % 10 == 0:
        try:
            new_arrivals = traci.simulation.getArrivedIDList()
            NUM_TRIPS_COMPLETED += len(new_arrivals)
            
            current_vehicles = traci.vehicle.getIDList()
            total_waiting_time = 0
            total_time_loss = 0
            total_co2 = 0
            
            for veh_id in current_vehicles:
                try:
                    total_waiting_time += traci.vehicle.getWaitingTime(veh_id)
                    total_time_loss += traci.vehicle.getTimeLoss(veh_id)
                    total_co2 += traci.vehicle.getCO2Emission(veh_id)
                except traci.TraCIException:
                    continue
            
            TOTAL_CO2_EMITTED += total_co2
            TOTAL_TRIP_TIME_LOSS += total_time_loss
            
            tls_data = []
            for tls_id, controller in controllers_map.items():
                if controller.valid_program:
                    tls_data.append({
                        "tls_id": tls_id,
                        "phase": controller.current_phase_index,
                        "queues": dict(controller.queue_lengths),
                        "priority": controller.priority_factor
                    })
            
            SIMULATION_DATA.append({
                "step": step,
                "vehicles": len(current_vehicles),
                "waiting_time": total_waiting_time,
                "co2": total_co2,
                "time_loss": total_time_loss,
                "completed_trips": len(new_arrivals),
                "tls_data": tls_data
            })
            
        except traci.TraCIException as e:
            print(f"AVISO na coleta de dados: {e}")


def run_simulation_segment(start_step, duration, controllers_map, coordinator):
    current_sim_step = start_step
    end_step = start_step + duration
    
    while current_sim_step < end_step:
        if traci.simulation.getMinExpectedNumber() == 0:
            return False
            
        traci.simulationStep()
        current_sim_step += 1
        
        remove_arrived_vehicles()
        insert_new_vehicles(current_sim_step)
        
        for controller in controllers_map.values():
            controller.step(current_sim_step)
        
        coordinator.step_coordination(current_sim_step)
        
        if current_sim_step % 10 == 0:
            collect_simulation_data(current_sim_step, controllers_map)

        if current_sim_step % 300 == 0:
            print(f"Passo: {current_sim_step}/{end_step} - Veículos: {traci.vehicle.getIDCount()}")
    
    return True


def run_main_simulation_loop():
    controllers_map = {}
    
    try:
        sumo_cmd = [
            SUMO_BINARY, "-c", SUMO_CONFIG_FILE,
            "--step-length", "1",
            "--waiting-time-memory", "1000",
            "--time-to-teleport", "300",
            "--tripinfo-output", "tripinfo.xml",
            "--emission-output", "emission.xml",
            "--log", "sumo.log",
            "--error-log", "sumo_errors.log",
            "--random",
            "--seed", str(random.randint(1, 10000))
        ]
        
        traci.start(sumo_cmd)
        print("Simulação iniciada com sucesso")
        
        global AVAILABLE_ROUTE_IDS
        AVAILABLE_ROUTE_IDS = list(traci.route.getIDList())
        print(f"Rotas disponíveis: {AVAILABLE_ROUTE_IDS}")
        
        valid_tls = traci.trafficlight.getIDList()
        for tls_id in TLS_IDS:
            if tls_id in valid_tls:
                try:
                    controller = TrafficLightController(tls_id, DETECTOR_MAPPING.get(tls_id, {}))
                    if controller.valid_program:
                        controllers_map[tls_id] = controller
                        print(f"Controlador ativo para {tls_id}")
                    else:
                        print(f"Controlador inválido para {tls_id}")
                except Exception as e:
                    print(f"Falha ao criar controlador para {tls_id}: {str(e)}")
            else:
                print(f"Semáforo {tls_id} não encontrado")
        
        if not controllers_map:
            print("Nenhum controlador válido. Encerrando.")
            return
            
        coordinator = CentralCoordinator(controllers_map)
        print(f"Sistema iniciado com {len(controllers_map)} controladores")
        
        current_step = 0
        segment_duration = 3600
        
        while True:
            continue_simulation = run_simulation_segment(
                current_step, segment_duration, controllers_map, coordinator
            )
            
            current_step += segment_duration
            
            if not continue_simulation:
                print("Simulação concluída: não há mais veículos")
                break
                
            user_input = input(f"Simulação em {current_step} passos. Continuar? (s/n): ").strip().lower()
            if user_input != 's':
                print("Simulação interrompida pelo usuário")
                break
                
    except traci.FatalTraCIError as e:
        print(f"ERRO FATAL: {e}")
    except Exception as e:
        print(f"Erro inesperado: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        try:
            traci.close()
            print("Conexão com SUMO encerrada")
        except:
            pass
            
        if SIMULATION_DATA:
            try:
                os.makedirs("simulation_results", exist_ok=True)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"traffic_simulation_{timestamp}.json"
                filepath = os.path.join("simulation_results", filename)
                
                with open(filepath, 'w') as f:
                    json.dump(SIMULATION_DATA, f, indent=2)
                    
                print(f"Dados salvos em {filepath}")
                
                print("\n=== RESUMO DA SIMULAÇÃO ===")
                print(f"Passos simulados: {current_step}")
                print(f"Veículos atendidos: {NUM_TRIPS_COMPLETED}")
                print(f"CO2 total emitido: {TOTAL_CO2_EMITTED/1000:.2f} kg")
                print(f"Tempo total perdido: {TOTAL_TRIP_TIME_LOSS/3600:.2f} horas")
                
            except Exception as e:
                print(f"Erro ao salvar dados: {str(e)}")
                
        print("Simulação finalizada")


if __name__ == "__main__":
    print("Iniciando sistema de controle de tráfego inteligente")
    
    if not os.path.exists(SUMO_CONFIG_FILE):
        print(f"ERRO: Arquivo de configuração não encontrado: {SUMO_CONFIG_FILE}")
        sys.exit(1)
        
    run_main_simulation_loop()