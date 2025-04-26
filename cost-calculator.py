import pandas as pd
from datetime import datetime

ECS_VCPU_PRICE = 0.04048      # per vCPU-Hour
ECS_MEM_GB_PRICE = 0.004445   # per GB-Hour

EC2_INSTANCE_HOURLY_PRICE = 0.0416  # t3.medium per-hour price (2 vCPU, 4GB)

file_paths = {
    "ec2_5": "results_with_cpu_ec2_5.csv",
    "ec2_10": "results_with_cpu_ec2_10.csv",
    "ec2_20": "results_with_cpu_ec2_20.csv",
    "ec2_50": "results_with_cpu_ec2_50.csv",
    "ecs_5": "results_with_cpu_ecs_5.csv",
    "ecs_10": "results_with_cpu_ecs_10.csv",
    "ecs_20": "results_with_cpu_ecs_20.csv",
    "ecs_50": "results_with_cpu_ecs_50.csv"
}

# Load and tag each dataset
dfs = []
for key, path in file_paths.items():
    deployment, users = key.split("_")
    df = pd.read_csv(path, parse_dates=["timestamp"])
    df["deployment"] = deployment
    df["users"] = int(users)
    dfs.append(df)

df_all = pd.concat(dfs, ignore_index=True)

# Keep only successful requests
df_all = df_all[df_all["success"] == True]

resource_summary = {}

# Estimate usage
for deployment in ["ec2", "ecs"]:
    df_deploy = df_all[df_all["deployment"] == deployment]

    if df_deploy.empty:
        continue

    # Time range
    start_time = df_deploy["timestamp"].min()
    end_time = df_deploy["timestamp"].max()
    duration_minutes = (end_time - start_time).total_seconds() / 60
    duration_hours = duration_minutes / 60

    # Average concurrent users
    avg_users = df_deploy["users"].mean()

    # Resource config
    if deployment == "ec2":
        vcpu = 2.0  # t3.medium
        mem_gb = 4.0
    else:
        vcpu = 0.25  # Fargate Task
        mem_gb = 0.5  # 512 MiB

    # Resource consumption = avg_users * task size * hours
    vcpu_hours = avg_users * vcpu * duration_hours
    mem_hours = avg_users * mem_gb * duration_hours

    resource_summary[deployment] = {
        "start": start_time,
        "end": end_time,
        "duration_minutes": round(duration_minutes, 2),
        "avg_users": avg_users,
        "vcpu_hours": round(vcpu_hours, 4),
        "mem_gb_hours": round(mem_hours, 4)
    }

# Output
print("\n=== RESOURCE USAGE ESTIMATE ===\n")
for deploy, stats in resource_summary.items():
    print(f"{deploy.upper()} Deployment")
    print(f"  Time: {stats['start']} → {stats['end']} ({stats['duration_minutes']} min)")
    print(f"  Avg Users: {stats['avg_users']}")
    print(f"  vCPU-Hours: {stats['vcpu_hours']}")
    print(f"  Memory GB-Hours: {stats['mem_gb_hours']}")
    
    if deploy == "ecs":
            cost = (stats['vcpu_hours'] * ECS_VCPU_PRICE) + (stats['mem_gb_hours'] * ECS_MEM_GB_PRICE)
    elif deploy == "ec2":
        duration_hours = stats['duration_minutes'] / 60
        cost = EC2_INSTANCE_HOURLY_PRICE * duration_hours

    print(f"Estimated Cost: ${cost:.4f}\n")
