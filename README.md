Sure! Below is a simple and neat documentation for the code:

# AWS Cost and Metrics Data Collection and Analysis

This Python script collects AWS cost data for EC2 instances and their associated metrics data (CPU utilization, NetworkIn, NetworkOut, MemoryUtilization, VolumeReadBytes, VolumeWriteBytes) from CloudWatch. The collected data is then inserted into a PostgreSQL database for further analysis and cost optimization.

## Prerequisites

Before running the script, ensure that you have the following:

1. AWS Account: You will need valid AWS credentials with access to the AWS Cost Explorer and CloudWatch APIs. Make sure to provide these credentials as environment variables:

   - `AWS_ACCESS_KEY_ID`: Your AWS access key ID
   - `AWS_SECRET_ACCESS_KEY`: Your AWS secret access key

2. PostgreSQL Database: Set up a PostgreSQL database and obtain the necessary credentials:

   - `POSTGRES_USERNAME`: Your PostgreSQL database username
   - `POSTGRES_PASSWORD`: Your PostgreSQL database password
   - `POSTGRES_HOST`: Your PostgreSQL database host
   - `POSTGRES_DATABASE`: Your PostgreSQL database name

## Usage

1. Install the required Python packages by running the following command:

```bash
pip install boto3 pandas psycopg2 sqlalchemy
```

2. Replace the placeholder values in the script with your actual AWS and PostgreSQL credentials.

3. Customize the time period for data collection in the `time_period` dictionary. For example, you can set the `Start` and `End` values to fetch data for a different time range.

4. Run the script:

```bash
python aws_cost_and_metrics.py
```

## Functionality

The script performs the following tasks:

1. **Fetch AWS Cost Data**: The script uses the AWS Cost Explorer API to fetch cost data for EC2 instances. It collects the service, instance type, and unblended cost for each instance.

2. **Fetch Metrics Data from CloudWatch**: The script utilizes the CloudWatch API to fetch additional metrics data for EC2 instances. The metrics collected include CPU utilization, NetworkIn, NetworkOut, MemoryUtilization, VolumeReadBytes, and VolumeWriteBytes. This data is fetched for each running instance over a specified time period.

3. **Identify Underutilized Instances**: The script calculates the average daily CPU utilization for each instance and identifies instances with average utilization below 5.0%. These instances are considered underutilized and can potentially be optimized to reduce cloud costs.

4. **Insert Data into PostgreSQL Database**: The script creates three tables in the PostgreSQL database:

   - `aws_ec2_cost`: Stores AWS cost data with columns: `Service`, `Instance_Type`, and `Cost`.
   - `cpu_metrics`: Stores metrics data with columns: `Instance_ID`, `Timestamp`, `CPU_Utilization`, `NetworkIn`, `NetworkOut`, `MemoryUtilization`, `VolumeReadBytes`, and `VolumeWriteBytes`.
   - `underutilized_instances`: Stores information about underutilized instances with columns: `Instance_ID` and `CPU_Utilization`.

   The script then inserts the fetched data into these tables. Existing data is preserved as the script uses the `if_exists='append'` option for insertion, allowing for incremental data loading.

## Notes

- The script fetches data for running EC2 instances only to optimize data collection.

- Ensure that the PostgreSQL database tables are set up and accessible with the provided credentials.

- This script serves as a foundation for AWS cost analysis and optimization. Further data analysis and cost reduction actions may require additional customizations based on your organization's specific requirements.

- Always test the code in a development environment before deploying to production.

- For improved security, store sensitive credentials as environment variables and use IAM roles with appropriate permissions for AWS access.

Feel free to customize and extend the script as needed to suit your infrastructure and cost optimization needs.
