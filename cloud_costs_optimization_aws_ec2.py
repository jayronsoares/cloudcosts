import os
import boto3
import pandas as pd
import psycopg2
from sqlalchemy import create_engine
from botocore.exceptions import ClientError
from datetime import datetime, timedelta

# AWS Credentials and Region
aws_access_key_id = os.environ.get('AWS_ACCESS_KEY_ID')
aws_secret_access_key = os.environ.get('AWS_SECRET_ACCESS_KEY')
region_name = 'us-east-1'

# PostgreSQL Database Credentials
db_username = os.environ.get('POSTGRES_USERNAME')
db_password = os.environ.get('POSTGRES_PASSWORD')
db_host = os.environ.get('POSTGRES_HOST')
db_name = os.environ.get('POSTGRES_DATABASE')

# Helper function to fetch AWS cost data using Boto3 with pagination
def fetch_aws_cost_data():
    try:
        ce = boto3.client('ce', region_name=region_name, aws_access_key_id=aws_access_key_id, aws_secret_access_key=aws_secret_access_key)

        # Set the time period for which you want to fetch the cost data (e.g., last 30 days)
        time_period = {
            'Start': '2023-06-26',
            'End': '2023-07-26'
        }

        # Fetch AWS cost data with pagination
        paginator = ce.get_paginator('get_cost_and_usage')
        response_iterator = paginator.paginate(
            TimePeriod=time_period,
            Granularity='DAILY',
            Metrics=['UnblendedCost'],
            GroupBy=[
                {
                    'Type': 'DIMENSION',
                    'Key': 'SERVICE'
                },
                {
                    'Type': 'DIMENSION',
                    'Key': 'INSTANCE_TYPE'
                }
            ]
        )

        for response in response_iterator:
            for group in response['ResultsByTime'][0]['Groups']:
                service, instance_type = group['Keys']
                cost = float(group['Metrics']['UnblendedCost']['Amount'])
                yield {'Service': service, 'Instance_Type': instance_type, 'Cost': cost}

    except ClientError as e:
        print("Error fetching AWS cost data:", e)
        return

# Helper function to fetch CPU utilization and additional metrics data from CloudWatch with pagination
def fetch_cpu_metrics_data():
    try:
        # Initialize CloudWatch client
        cloudwatch = boto3.client('cloudwatch', region_name=region_name,
                                  aws_access_key_id=aws_access_key_id,
                                  aws_secret_access_key=aws_secret_access_key)

        # Get the list of all EC2 instances in your account and region
        ec2 = boto3.resource('ec2', region_name=region_name,
                             aws_access_key_id=aws_access_key_id,
                             aws_secret_access_key=aws_secret_access_key)
        instances = ec2.instances.all()

        # Set the time range for which you want to fetch metric data (e.g., last 7 days)
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(days=7)

        # Fetch metric data from CloudWatch with pagination
        for instance in instances:
            # Skip instances that are not running
            if instance.state['Name'] != 'running':
                continue

            instance_id = instance.id

            # Fetch metric data from CloudWatch
            paginator = cloudwatch.get_paginator('get_metric_data')
            response_iterator = paginator.paginate(
                MetricDataQueries=[
                    {
                        'Id': 'cpu_utilization',
                        'MetricStat': {
                            'Metric': {
                                'Namespace': 'AWS/EC2',
                                'MetricName': 'CPUUtilization',
                                'Dimensions': [
                                    {
                                        'Name': 'InstanceId',
                                        'Value': instance_id
                                    },
                                ]
                            },
                            'Period': 3600,  # 1 hour intervals
                            'Stat': 'Average',
                        },
                        'ReturnData': True,
                    },
                    {
                        'Id': 'network_in',
                        'MetricStat': {
                            'Metric': {
                                'Namespace': 'AWS/EC2',
                                'MetricName': 'NetworkIn',
                                'Dimensions': [
                                    {
                                        'Name': 'InstanceId',
                                        'Value': instance_id
                                    },
                                ]
                            },
                            'Period': 3600,
                            'Stat': 'Average',
                        },
                        'ReturnData': True,
                    },
                    {
                        'Id': 'network_out',
                        'MetricStat': {
                            'Metric': {
                                'Namespace': 'AWS/EC2',
                                'MetricName': 'NetworkOut',
                                'Dimensions': [
                                    {
                                        'Name': 'InstanceId',
                                        'Value': instance_id
                                    },
                                ]
                            },
                            'Period': 3600,
                            'Stat': 'Average',
                        },
                        'ReturnData': True,
                    },
                    {
                        'Id': 'memory_utilization',
                        'MetricStat': {
                            'Metric': {
                                'Namespace': 'CWAgent',
                                'MetricName': 'MemoryUtilization',
                                'Dimensions': [
                                    {
                                        'Name': 'InstanceId',
                                        'Value': instance_id
                                    },
                                ]
                            },
                            'Period': 3600,
                            'Stat': 'Average',
                        },
                        'ReturnData': True,
                    },
                    {
                        'Id': 'volume_read_bytes',
                        'MetricStat': {
                            'Metric': {
                                'Namespace': 'AWS/EBS',
                                'MetricName': 'VolumeReadBytes',
                                'Dimensions': [
                                    {
                                        'Name': 'VolumeId',
                                        'Value': instance.block_device_mappings[0]['Ebs']['VolumeId']
                                    },
                                ]
                            },
                            'Period': 3600,
                            'Stat': 'Average',
                        },
                        'ReturnData': True,
                    },
                    {
                        'Id': 'volume_write_bytes',
                        'MetricStat': {
                            'Metric': {
                                'Namespace': 'AWS/EBS',
                                'MetricName': 'VolumeWriteBytes',
                                'Dimensions': [
                                    {
                                        'Name': 'VolumeId',
                                        'Value': instance.block_device_mappings[0]['Ebs']['VolumeId']
                                    },
                                ]
                            },
                            'Period': 3600,
                            'Stat': 'Average',
                        },
                        'ReturnData': True,
                    },
                ],
                StartTime=start_time,
                EndTime=end_time,
            )

            for response in response_iterator:
                cpu_utilization_result = response['MetricDataResults'][0]
                network_in_result = response['MetricDataResults'][1]
                network_out_result = response['MetricDataResults'][2]
                memory_utilization_result = response['MetricDataResults'][3]
                volume_read_bytes_result = response['MetricDataResults'][4]
                volume_write_bytes_result = response['MetricDataResults'][5]

                timestamps = cpu_utilization_result['Timestamps']
                cpu_utilization_values = cpu_utilization_result['Values']
                network_in_values = network_in_result['Values']
                network_out_values = network_out_result['Values']
                memory_utilization_values = memory_utilization_result['Values']
                volume_read_bytes_values = volume_read_bytes_result['Values']
                volume_write_bytes_values = volume_write_bytes_result['Values']

                for i in range(len(timestamps)):
                    yield {
                        'Instance_ID': instance_id,
                        'Timestamp': timestamps[i],
                        'CPU_Utilization': cpu_utilization_values[i],
                        'NetworkIn': network_in_values[i],
                        'NetworkOut': network_out_values[i],
                        'MemoryUtilization': memory_utilization_values[i],
                        'VolumeReadBytes': volume_read_bytes_values[i],
                        'VolumeWriteBytes': volume_write_bytes_values[i],
                    }

    except Exception as e:
        print("Error fetching metrics data from CloudWatch:", e)
        return

# Helper function for identifying idle or underutilized resources
def identify_underutilized_instances(cpu_utilization_df):
    try:
        # Calculate average daily CPU utilization for each instance
        average_cpu_utilization = cpu_utilization_df.groupby('Instance_ID')['CPU_Utilization'].mean().reset_index()
        underutilized_instances = average_cpu_utilization[average_cpu_utilization['CPU_Utilization'] < 5.0]
        return underutilized_instances

    except Exception as e:
        print("Error identifying underutilized instances:", e)
        return pd.DataFrame()

def main():
    # Step 1: Fetch AWS cost data
    aws_cost_data = pd.DataFrame(fetch_aws_cost_data())

    if aws_cost_data.empty:
        print("No AWS cost data found. Exiting...")
        return

    # Step 2: Fetch CPU utilization and additional metrics data from CloudWatch
    cpu_metrics_df = pd.DataFrame(fetch_cpu_metrics_data())

    if cpu_metrics_df.empty:
        print("No CPU utilization and metrics data found. Exiting...")
        return

    # Step 3: Identify idle or underutilized resources
    underutilized_instances = identify_underutilized_instances(cpu_metrics_df)

    # Step 4: Create the engine and connect to the PostgreSQL database
    engine = create_engine(f'postgresql://{db_username}:{db_password}@{db_host}/{db_name}')

    # Step 5: Create tables if they don't exist and insert data into the PostgreSQL database
    try:
        # Create tables if they don't exist
        aws_cost_data.to_sql('aws_ec2_cost', engine, if_exists='append', index=False)
        cpu_metrics_df.to_sql('cpu_metrics', engine, if_exists='append', index=False)
        underutilized_instances.to_sql('underutilized_instances', engine, if_exists='append', index=False)

        print("Data successfully inserted into the PostgreSQL database.")

    except (ClientError, psycopg2.Error, Exception) as e:
        print("Error inserting data into PostgreSQL database:", e)

if __name__ == "__main__":
    main()
