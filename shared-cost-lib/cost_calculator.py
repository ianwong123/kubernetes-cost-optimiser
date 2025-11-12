"""
This class calculates VM requirements and costs
from Kubernetes resource requests
"""
import math

class CostCalculator:
    # Handles all VM and cost calculations 
    # for K8s resources
    #
    # VM specs can be modified 
    HOURLY_RATE = 0.04
    CPU_CORES_PER_VM = 2
    MEMORY_GB_PER_VM = 4

    # Calculate the VMs needed based on CPU and memory requirements
    # Args: total CPU cores and memory in GB required
    # Returns: number of VMs needed
    @staticmethod 
    def calculate_vms_needed(cpu_cores: float, memory_gb: float) -> int:
        cpu_vms = math.ceil(cpu_cores / CostCalculator.CPU_CORES_PER_VM)
        mem_vms = math.ceil(memory_gb / CostCalculator.MEMORY_GB_PER_VM)
        return max(cpu_vms, mem_vms)

    # Calculate the cost per hour based on VMs required
    # Args: total VMs needed
    # Returns: cost per hour
    @staticmethod
    def calculate_cost_per_hour(vms_needed: int) -> float:
        return vms_needed * CostCalculator.HOURLY_RATE

    # Convert CPU string e.g 500m to 0.5 cores
    # Args: cpu string from kubernetes
    # Returns: cpu in cores
    @staticmethod
    def convert_cpu_string_to_cores(cpu_string: str) -> float:
        if not cpu_string:
            return 0.0
        if cpu_string.endswith('m'):
            return float(cpu_string[:-1]) / 1000.0
        return float(cpu_string)

    # Convert memory bytes to GB
    # Args: memory in bytes
    # Returns: memory in GB
    @staticmethod
    def convert_memory_to_gb(memory_bytes: float) -> float:
        return memory_bytes / (1024 ** 3)


    # Convert memory string (e.g., '512Mi', '1Gi', '2G') to GB
    # Args: memory_string: Memory string from Kubernetes  
    # Returns: float: Memory in GB
    @staticmethod
    def convert_memory_string_to_gb(memory_string: str) -> float:
        if not memory_string:
            return 0.0
        memory_string = memory_string.upper()
        
        if memory_string.endswith('MI'):  
            # MiB to GB
            return float(memory_string[:-2]) * (1024 ** 2) / (1024 ** 3)  
        elif memory_string.endswith('GI'):  
            # GiB to GB
            return float(memory_string[:-2]) * (1024 ** 3) / (1024 ** 3)  
        elif memory_string.endswith('M'):   
            # MB (decimal) to GB
            return float(memory_string[:-1]) * (1000 ** 2) / (1024 ** 3)  
        elif memory_string.endswith('G'):   
            # GB (decimal) to GB
            return float(memory_string[:-1]) * (1000 ** 3) / (1024 ** 3)  
        elif memory_string.endswith('KI'):  
            # KiB to GB
            return float(memory_string[:-2]) * 1024 / (1024 ** 3)  
        elif memory_string.endswith('K'):   
            # KB (decimal) to GB
            return float(memory_string[:-1]) * 1000 / (1024 ** 3)  
        elif memory_string.endswith('B'):   
            # B to GB
            return float(memory_string[:-1]) / (1024 ** 3)  
        else:
            # Assume it's already in bytes
            return float(memory_string) / (1024 ** 3)

