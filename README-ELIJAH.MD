FILE CHANGES FOR THIS EECS 6446 PROJECT
NOTE: Commands used to deploy the task definition are not included in this file. Commands for manual setup of EC2 instance before running docker-compose-t3-ec2.yml are not included in this file. Any missing details or instructions for running the project can be added upon request.


workload_generator.py - Generate workload, collect data and analysis data
cost-calculator.py - Calculate the cost for EC2 and ECS
petclinic-data.xlsx - Contains final data before ML training


Application.yml files below were update to allow deployment in ECS (Setup environment variables, Enable Cloud Map setup, Update genai secret but currently removed):
spring-petclinic-api-gateway/src/main/resources/application-ecs.yml
spring-petclinic-api-gateway/src/main/resources/application.yml

spring-petclinic-config-server/src/main/resources/application-ecs.yml
spring-petclinic-config-server/src/main/resources/application.yml

spring-petclinic-customers-service/src/main/resources/application-ecs.yml
spring-petclinic-customers-service/src/main/resources/application.yml

spring-petclinic-discovery-server/src/main/resources/application-ecs.yml
spring-petclinic-discovery-server/src/main/resources/application.yml

spring-petclinic-genai-service/src/main/resources/application-ecs.yml
spring-petclinic-genai-service/src/main/resources/application.yml

spring-petclinic-vets-service/src/main/resources/application-ecs.yml
spring-petclinic-vets-service/src/main/resources/application.yml


FOLDER: Raw_Experiment_Data - Contains the raw file with data from the experiment 
results_with_cpu_ec2_5.csv - ec2_5 users
results_with_cpu_ec2_10.csv - ec2_10 users
results_with_cpu_ec2_20.csv - ec2_20 users
results_with_cpu_ec2_50.csv - ec2_50 users
results_with_cpu_ecs_5.csv - ecs_5 users
results_with_cpu_ecs_10.csv - ecs_10 users
results_with_cpu_ecs_20.csv - ecs_20 users
results_with_cpu_ecs_50.csv - ecs_50 users

FOLDER: Task-Definition - Task Definition for ECS deployment 
task-definition-admin-server.json
task-definition-api-gateway.json
task-definition-customers-service.json
task-definition-discovery-server.json
task-definition-vets-service.json
task-definition-config-server.json
task-definition-genai-service.json

docker-compose-t3-ec2.yml - Deploy Docker containers on EC2

config.json - Enable calls from remote machine to AWS server need for running CLI commands to deploy in ECS, connect with ECR etc 

ecsTaskRole-trust-policy.json - IAM policy for ECS deployment 