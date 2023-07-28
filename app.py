from flask import Flask, jsonify, render_template
from flask_sqlalchemy import SQLAlchemy
import os
import boto3
import pandas as pd
from botocore.exceptions import ClientError
from datetime import datetime, timedelta

app = Flask(__name__)

# Configure the PostgreSQL database
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
db = SQLAlchemy(app)

# Model for AWS cost data
class AWSCostData(db.Model):
    __tablename__ = 'aws_ec2_cost'
    id = db.Column(db.Integer, primary_key=True)
    service = db.Column(db.String(50))
    instance_type = db.Column(db.String(50))
    cost = db.Column(db.Float)

# Model for CPU metrics data
class CPUMetricsData(db.Model):
    __tablename__ = 'cpu_metrics'
    id = db.Column(db.Integer, primary_key=True)
    instance_id = db.Column(db.String(50))
    timestamp = db.Column(db.DateTime)
    cpu_utilization = db.Column(db.Float)
    network_in = db.Column(db.Float)
    network_out = db.Column(db.Float)
    memory_utilization = db.Column(db.Float)
    volume_read_bytes = db.Column(db.Float)
    volume_write_bytes = db.Column(db.Float)

# Model for underutilized instances
class UnderutilizedInstances(db.Model):
    __tablename__ = 'underutilized_instances'
    id = db.Column(db.Integer, primary_key=True)
    instance_id = db.Column(db.String(50))
    cpu_utilization = db.Column(db.Float)

# AWS Credentials and Region
aws_access_key_id = os.environ.get('AWS_ACCESS_KEY_ID')
aws_secret_access_key = os.environ.get('AWS_SECRET_ACCESS_KEY')
region_name = 'us-east-1'

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

        cost_data_list = []
        for response in response_iterator:
            for group in response['ResultsByTime'][0]['Groups']:
                service, instance_type = group['Keys']
                cost = float(group['Metrics']['UnblendedCost']['Amount'])
                cost_data_list.append({
                    'Service': service,
                    'Instance_Type': instance_type,
                    'Cost': cost
                })

        return cost_data_list

    except ClientError as e:
        print("Error fetching AWS cost data:", e)
        return []

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

        metric_data_list = []
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
                metric_data = response['MetricDataResults']
                for data in metric_data:
                    timestamp = data['Timestamps'][0]
                    cpu_utilization = data['Values'][0]
                    network_in = data['Values'][1]
                    network_out = data['Values'][2]
                    memory_utilization = data['Values'][3]
                    volume_read_bytes = data['Values'][4]
                    volume_write_bytes = data['Values'][5]

                    metric_data_list.append({
                        'Instance_ID': instance_id,
                        'Timestamp': timestamp,
                        'CPU_Utilization': cpu_utilization,
                        'NetworkIn': network_in,
                        'NetworkOut': network_out,
                        'MemoryUtilization': memory_utilization,
                        'VolumeReadBytes': volume_read_bytes,
                        'VolumeWriteBytes': volume_write_bytes,
                    })

        return metric_data_list

    except Exception as e:
        print("Error fetching metrics data from CloudWatch:", e)
        return []

# Helper function for identifying idle or underutilized resources
def identify_underutilized_instances(cpu_metrics_df):
    try:
        # Calculate average daily CPU utilization for each instance
        average_cpu_utilization = cpu_metrics_df.groupby('Instance_ID')['CPU_Utilization'].mean().reset_index()
        underutilized_instances = average_cpu_utilization[average_cpu_utilization['CPU_Utilization'] < 5.0]
        return underutilized_instances

    except Exception as e:
        print("Error identifying underutilized instances:", e)
        return pd.DataFrame()

@app.route('/collect_data', methods=['GET'])
def collect_data():
    # Step 1: Fetch AWS cost data
    aws_cost_data = pd.DataFrame(fetch_aws_cost_data())

    if aws_cost_data.empty:
        return jsonify({'message': 'No AWS cost data found.'}), 500

    # Step 2: Fetch CPU utilization and additional metrics data from CloudWatch
    cpu_metrics_df = pd.DataFrame(fetch_cpu_metrics_data())

    if cpu_metrics_df.empty:
        return jsonify({'message': 'No CPU utilization and metrics data found.'}), 500

    # Step 3: Identify idle or underutilized resources
    underutilized_instances = identify_underutilized_instances(cpu_metrics_df)

    # Step 4: Insert data into the PostgreSQL database
    try:
        # Insert AWS cost data
        aws_cost_data.to_sql(AWSCostData.__tablename__, db.engine, if_exists='replace', index=False)

        # Insert CPU metrics data
        cpu_metrics_df.to_sql(CPUMetricsData.__tablename__, db.engine, if_exists='replace', index=False)

        # Insert underutilized instances data
        underutilized_instances.to_sql(UnderutilizedInstances.__tablename__, db.engine, if_exists='replace', index=False)

        return jsonify({'message': 'Data successfully collected and inserted into the database.'}), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/get_aws_cost_data', methods=['GET'])
def get_aws_cost_data():
    aws_cost_data = AWSCostData.query.all()
    return render_template('index.html', aws_cost_data=aws_cost_data)

@app.route('/get_cpu_metrics_data', methods=['GET'])
def get_cpu_metrics_data():
    cpu_metrics_data = CPUMetricsData.query.all()
    return render_template('index.html', cpu_metrics_data=cpu_metrics_data)

@app.route('/get_underutilized_instances', methods=['GET'])
def get_underutilized_instances():
    underutilized_instances = UnderutilizedInstances.query.all()
    return render_template('index.html', underutilized_instances=underutilized_instances)

if __name__ == "__main__":
    app.run(debug=True)