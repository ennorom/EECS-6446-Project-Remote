import requests
import time
import csv
import random
from datetime import datetime, timedelta, timezone
import boto3
import subprocess
import threading
# -------------- CONFIGURATION --------------
IS_EC2 = False 
INSTANCE_ID = "i-00086e1a30625dc9b"
REGION = "us-east-2"
NAMESPACE = "AWS/EC2" if IS_EC2 else "ECS/ContainerInsights"
# METRIC_NAME = 
CLUSTER_NAME = "spring-petclinic-cluster"
# SERVICE_NAME = "api-gateway"
SERVICE_CONTAINER  = "spring-petclinic-api-gateway:16"
DEPLOYMENT_LABEL = "ec2" if IS_EC2 else "ecs"
CLINIC_URL = "http://13.59.1.171:18080/api/" if IS_EC2 else "http://18.217.243.48:8080/api/"
TOTAL_VCPU = 2 if IS_EC2 else 0.25 # Where EC2 all containers share the 2vCPU while in ECS each container is assigned 0.25vCPU
# -------------------------------------------

ecs = boto3.client('ecs', region_name=REGION)
cloudwatch = boto3.client('cloudwatch', region_name=REGION)

def get_ecs_metric(metric_utilized, metric_reserved, target_time, service_name_filter):

    # Cloud watch only collects metrics in 60 seconds interval. 
    # Get the 60 secs in the past and 60 secs in the future where the metric is the midpoint
    start = target_time - timedelta(minutes=60)
    end = target_time + timedelta(minutes=60)
    
    # Get CPU utilized (absolute value)
    response = cloudwatch.get_metric_statistics(
        Namespace=NAMESPACE,
        MetricName=metric_utilized,  # This is the correct metric name from your list
        Dimensions=[
            {'Name': 'ServiceName', 'Value': service_name_filter},
            {'Name': 'ClusterName', 'Value': 'spring-petclinic-cluster'}
        ],
        StartTime=start,
        EndTime=end,
        Period=60,
        Statistics=['Average']
    )
    
    # Also get CPU reserved for calculating percentage
    reserved_response = cloudwatch.get_metric_statistics(
        Namespace=NAMESPACE,
        MetricName=metric_reserved,  # Also available in your metrics list
        Dimensions=[
            {'Name': 'ServiceName', 'Value': service_name_filter},
            {'Name': 'ClusterName', 'Value': 'spring-petclinic-cluster'}
        ],
        StartTime=start,
        EndTime=end,
        Period=60,
        Statistics=['Average']
    )
    
    utilized_datapoints = sorted(response.get('Datapoints', []), key=lambda x: x['Timestamp'])
    reserved_datapoints = sorted(reserved_response.get('Datapoints', []), key=lambda x: x['Timestamp'])
    
    if not utilized_datapoints:
        print("[WARN] No CPU utilization datapoints returned")
        return None
    
    # Get the latest datapoint
    latest_utilized = utilized_datapoints[-1]
    metric_utilized = latest_utilized['Average']
    
    # Calculate percentage if reserved data is available
    if reserved_datapoints:
        latest_reserved = min(reserved_datapoints, key=lambda x: abs(x['Timestamp'] - latest_utilized['Timestamp']))
        metric_reserved = latest_reserved['Average']
        metric_percentage = (metric_utilized / metric_reserved * 100) if metric_reserved > 0 else 0
        return round(metric_percentage, 2)
        
def get_cpu_ec2_api_gateway_docker( ec2_host, key_path, user, container_name_filter):

    remote_command = (r'docker stats --no-stream --format "{{.Name}},{{.CPUPerc}}"')

    ssh_command = ['ssh','-i', key_path, f'{user}@{ec2_host}', remote_command ]

    try:
        result = subprocess.check_output(ssh_command).decode('utf-8')

        for line in result.strip().split('\n'):
            # print(f"LOGGING EC2 CPU: {line}")
            parts = line.split(',')
            if len(parts) != 2:
                continue
            name, cpu = parts
            if container_name_filter in name:
                return float(cpu.strip().replace('%', ''))
    except subprocess.CalledProcessError as e:
        print("SSH or docker command failed:", e.output.decode())
    except Exception as e:
        print("Unexpected error:", str(e))
        
def get_cpu_utilization(timestamp, service_name_filter):
    
    if IS_EC2:
        ec2_percent = get_cpu_ec2_api_gateway_docker('ec2-13-59-1-171.us-east-2.compute.amazonaws.com', 'petclinic-key-v2.pem', 'ec2-user', container_name_filter=service_name_filter)
        if ec2_percent != None: 
            used_ec2_vcpu = (ec2_percent / 100) * TOTAL_VCPU
            normalized_ec2_vcpu = (used_ec2_vcpu / .25) * 100
            return normalized_ec2_vcpu
    
    else:
        ecs_percent = get_ecs_metric("CpuUtilized", "CpuReserved", timestamp, service_name_filter)
        return ecs_percent

    return None

def get_mem_ec2_api_gateway_docker(ec2_host, key_path, user, container_name_filter):
    
    remote_command = (r'docker stats --no-stream --format "{{.Name}},{{.MemPerc}}"')

    ssh_command = ['ssh','-i', key_path,f'{user}@{ec2_host}',remote_command]

    try:
        result = subprocess.check_output(ssh_command).decode('utf-8')

        for line in result.strip().split('\n'):
            # print(f"LOGGING EC2 MEM: {line}")
            parts = line.split(',')
            if len(parts) != 2:
                continue
            name, mem = parts
            # print(f"LOGGING EC2 MEM: name {name} | mem {mem}")
            if container_name_filter in name:
                return float(mem.strip().replace('%', ''))
    except subprocess.CalledProcessError as e:
        print("SSH or docker command failed:", e.output.decode())
    except Exception as e:
        print("Unexpected error:", str(e))

def get_mem_utilization(timestamp, service_name_filter):
    
    if IS_EC2:
        ecs_mem_percent = get_mem_ec2_api_gateway_docker(ec2_host='ec2-13-59-1-171.us-east-2.compute.amazonaws.com', key_path='petclinic-key-v2.pem', user='ec2-user', container_name_filter=service_name_filter)
    else:
        ecs_mem_percent = get_ecs_metric("MemoryUtilized", "MemoryReserved", timestamp, service_name_filter)
        
    return ecs_mem_percent

class PetClinicCustomer:
    def __init__(self, customer_id, clinic_url, user_count):
        self.customer_id = customer_id
        self.clinic_url = clinic_url
        self.user_count = user_count
        self.session_data = []

    def _record(self, endpoint, latency, status_code, success, api_cpu_utilization, api_mem_utilization, service_cpu_utilization, service_mem_utilization):
        self.session_data.append({
            "timestamp": datetime.utcnow().isoformat(),
            "customer_id": self.customer_id,
            "endpoint": endpoint,
            "latency": latency,
            "status_code": status_code,
            "success": success,
            "api_cpu_utilization": api_cpu_utilization,
            "api_mem_utilization": api_mem_utilization,
            "service_cpu_utilization": service_cpu_utilization,
            "service_mem_utilization": service_mem_utilization,
            "deployment": DEPLOYMENT_LABEL,
            "users": self.user_count
        })

    def genai_service_request(self):
        endpoint = "genai/chatclient"
        url = f"{self.clinic_url}{endpoint}"
        start_time = time.time()
        payload = "Steps to register as a Pet owner and find a veterinarian"
        try:
            response = requests.post(url, data=payload, headers={"Content-Type": "application/json"})
            latency = time.time() - start_time
            success = response.status_code == 200
            api_cpu = get_cpu_utilization(datetime.now(timezone.utc), 'api-gateway')
            api_mem = get_mem_utilization(datetime.now(timezone.utc), 'api-gateway')
            service_cpu = get_cpu_utilization(datetime.now(timezone.utc), 'genai-service')
            service_mem = get_mem_utilization(datetime.now(timezone.utc), 'genai-service')
            self._record(endpoint, latency, response.status_code, success, api_cpu, api_mem, service_cpu, service_mem)
            return {"response": response.text}
        except Exception as e:
            self._record(endpoint, None, 0, False, api_cpu, api_mem, service_cpu, service_mem)
            return {"error": str(e)}

    def register_customer_request(self):
        endpoint = "customer/owners"
        url = f"{self.clinic_url}{endpoint}"
        payload = {
            "firstName": f"User{self.customer_id}",
            "lastName": "LoadTest",
            "address": f"{1000 + self.customer_id} Performance Lane",
            "telephone": f"{random.randint(1000000000,9999999999)}",
            "city": "Toronto"
        }
        start_time = time.time()
        try:
            response = requests.post(url, json=payload)
            latency = time.time() - start_time
            success = response.status_code == 201
            api_cpu = get_cpu_utilization(datetime.now(timezone.utc), 'api-gateway')
            api_mem = get_mem_utilization(datetime.now(timezone.utc), 'api-gateway')
            service_cpu = get_cpu_utilization(datetime.now(timezone.utc), 'customers-service')
            service_mem = get_mem_utilization(datetime.now(timezone.utc), 'customers-service')
            self._record(endpoint, latency, response.status_code, success, api_cpu, api_mem, service_cpu, service_mem)
            return response.json(), response.status_code
        except Exception as e:
            self._record(endpoint, None, 0, False, api_cpu, api_mem, service_cpu, service_mem)
            return {"error": str(e)}

    def find_vet_request(self):
        endpoint = "vet/vets"
        url = f"{self.clinic_url}{endpoint}"
        # print(f"VET URL LOGGING: {url}")
        start_time = time.time()
        try:
            response = requests.get(url)
            latency = time.time() - start_time
            success = response.status_code == 200
            api_cpu = get_cpu_utilization(datetime.now(timezone.utc), 'api-gateway')
            api_mem = get_mem_utilization(datetime.now(timezone.utc), 'api-gateway')
            service_cpu = get_cpu_utilization(datetime.now(timezone.utc), 'vets-service')
            service_mem = get_mem_utilization(datetime.now(timezone.utc), 'vets-service')
            self._record(endpoint, latency, response.status_code, success, api_cpu, api_mem, service_cpu, service_mem)
            return response.json()
        except Exception as e:
            self._record(endpoint, None, 0, False, api_cpu, api_mem, service_cpu, service_mem)
            return {"error": str(e)}

    def simulate_full_user_flow(self):
        self.genai_service_request()
        time.sleep(random.uniform(0.1, 0.5))
        self.register_customer_request()
        time.sleep(random.uniform(0.1, 0.5))
        self.find_vet_request()


def run_simulation(user_counts):
     for user_count in user_counts:
        all_data = []
        threads = []
        users = []
        print(f"\nStarting simulation with {user_count} users on {DEPLOYMENT_LABEL.upper()}...")
        start_time = time.time()
        print(f"START TIME: {start_time}")
        for i in range(user_count):
            user = PetClinicCustomer(i, CLINIC_URL, user_count)
            users.append(user)
            thread = threading.Thread(target=user.simulate_full_user_flow)
            threads.append(thread)
            
        for thread in threads:
            thread.start()
            time.sleep(0.5)
            
        for thread in threads:
            thread.join()
            
        for user in users:
            all_data.extend(user.session_data)
            
        end_time = time.time()
        print(f"START TIME: {end_time}")

        filename = f"results_with_cpu_{DEPLOYMENT_LABEL}_{user_count}.csv"
        with open(filename, "w", newline="") as csvfile:
            fieldnames = [
                "timestamp", "customer_id", "endpoint", "status_code", "success", "deployment", "users", "latency", "api_cpu_utilization", "api_mem_utilization", "service_cpu_utilization", "service_mem_utilization"
            ]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            for row in all_data:
                writer.writerow(row)

        total_requests = len(all_data)
        successful_requests = sum(1 for row in all_data if row["success"])
        failed_requests = total_requests - successful_requests
        avg_latency = sum(row["latency"] for row in all_data if row["latency"]) / successful_requests

        print(f"Simulation complete for {user_count} users")
        print(f"Total Requests: {total_requests}")
        print(f"Successful: {successful_requests} | Failed: {failed_requests}")
        print(f"Average Latency (s): {avg_latency:.3f}")
        print(f"Throughput (requests/sec): {total_requests / (end_time - start_time):.2f}")
        print(f"Results saved to: {filename}")


if __name__ == "__main__":
    simulation_start_time = time.time()
    print(f"START TIME OF THE EXPERIMENT: {simulation_start_time}")
    run_simulation(user_counts=[5, 10, 20, 50])
    # run_simulation(user_counts=[2])
    simulation_end_time = time.time() - simulation_start_time
    print(f"END TIME OF THE EXPERIMENT: {simulation_end_time}")
    print(f"TOTAL TIME OF THE EXPERIMENT (Seconds): {simulation_end_time}")

