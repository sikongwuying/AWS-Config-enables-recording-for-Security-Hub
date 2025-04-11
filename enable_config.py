import json
import boto3
import logging
from botocore.exceptions import ClientError

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def read_json_file(file_path):
    """读取JSON文件"""
    try:
        with open(file_path, 'r') as file:
            return json.load(file)
    except Exception as e:
        logger.error(f'读取文件 {file_path} 失败: {str(e)}')
        raise

def create_config_role():
    """创建AWS Config所需的IAM角色"""
    try:
        # 创建IAM客户端
        iam_client = boto3.client('iam')
        
        # 定义角色名称
        role_name = 'AWSConfigRole'
        
        # 定义信任关系策略
        trust_policy = {
            'Version': '2012-10-17',
            'Statement': [{
                'Effect': 'Allow',
                'Principal': {
                    'Service': 'config.amazonaws.com'
                },
                'Action': 'sts:AssumeRole'
            }]
        }
        
        # 创建角色
        try:
            response = iam_client.create_role(
                RoleName=role_name,
                AssumeRolePolicyDocument=json.dumps(trust_policy)
            )
            logger.info('成功创建IAM角色')
            
            # 附加AWS管理的Config策略
            iam_client.attach_role_policy(
                RoleName=role_name,
                PolicyArn='arn:aws:iam::aws:policy/service-role/AWS_ConfigRole'
            )
            logger.info('成功附加AWS Config策略')
            
            # 附加S3访问策略
            s3_policy = {
                'Version': '2012-10-17',
                'Statement': [{
                    'Effect': 'Allow',
                    'Action': [
                        's3:PutObject',
                        's3:GetBucketAcl'
                    ],
                    'Resource': [
                        f'arn:aws:s3:::*',
                        f'arn:aws:s3:::*/AWSLogs/*'
                    ]
                }]
            }
            
            # 创建并附加S3访问策略
            try:
                response = iam_client.create_policy(
                    PolicyName='AWSConfigS3AccessPolicy',
                    PolicyDocument=json.dumps(s3_policy)
                )
                iam_client.attach_role_policy(
                    RoleName=role_name,
                    PolicyArn=response['Policy']['Arn']
                )
                logger.info('成功附加S3访问策略')
            except ClientError as e:
                if e.response['Error']['Code'] == 'EntityAlreadyExists':
                    account_id = boto3.client('sts').get_caller_identity()['Account']
                    policy_arn = f'arn:aws:iam::{account_id}:policy/AWSConfigS3AccessPolicy'
                    iam_client.attach_role_policy(
                        RoleName=role_name,
                        PolicyArn=policy_arn
                    )
                    logger.info('成功附加已存在的S3访问策略')
                else:
                    raise
            
            return response['Role']['Arn']
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'EntityAlreadyExists':
                response = iam_client.get_role(RoleName=role_name)
                return response['Role']['Arn']
            else:
                raise
                
    except Exception as e:
        logger.error(f'创建IAM角色失败: {str(e)}')
        raise

def create_config_bucket(bucket_name, region):
    """创建S3存储桶并配置适当的权限"""
    try:
        s3_client = boto3.client('s3', region_name=region)
        
        # 创建存储桶
        if region == 'us-east-1':
            s3_client.create_bucket(Bucket=bucket_name)
        else:
            s3_client.create_bucket(
                Bucket=bucket_name,
                CreateBucketConfiguration={'LocationConstraint': region}
            )
        logger.info(f'成功创建S3存储桶: {bucket_name}')
        
        # 配置存储桶策略
        # 获取当前账户ID
        account_id = boto3.client('sts').get_caller_identity()['Account']
        
        bucket_policy = {
            'Version': '2012-10-17',
            'Statement': [
                {
                    'Sid': 'AWSConfigBucketPermissionsCheck',
                    'Effect': 'Allow',
                    'Principal': {'Service': 'config.amazonaws.com'},
                    'Action': 's3:GetBucketAcl',
                    'Resource': f'arn:aws:s3:::{bucket_name}'
                },
                {
                    'Sid': 'AWSConfigBucketDelivery',
                    'Effect': 'Allow',
                    'Principal': {'Service': 'config.amazonaws.com'},
                    'Action': 's3:PutObject',
                    'Resource': f'arn:aws:s3:::{bucket_name}/AWSLogs/{account_id}/*',
                    'Condition': {
                        'StringEquals': {
                            's3:x-amz-acl': 'bucket-owner-full-control'
                        }
                    }
                }
            ]
        }
        
        s3_client.put_bucket_policy(
            Bucket=bucket_name,
            Policy=json.dumps(bucket_policy)
        )
        logger.info('成功配置S3存储桶策略')
        
        return bucket_name
        
    except ClientError as e:
        if e.response['Error']['Code'] == 'BucketAlreadyOwnedByYou':
            logger.info(f'存储桶 {bucket_name} 已存在且属于您')
            return bucket_name
        else:
            logger.error(f'创建S3存储桶失败: {str(e)}')
            raise

def setup_aws_config(parameters):
    """设置AWS Config服务"""
    try:
        # 读取资源类型
        resource_types = read_json_file(parameters['ResourceTypes'])
        
        # 检查RoleARN是否为空，如果为空则创建新角色
        role_arn = parameters['RoleARN']
        if not role_arn:
            role_arn = create_config_role()
            logger.info(f'使用新创建的角色ARN: {role_arn}')
        
        # 获取AWS账户ID
        account_id = boto3.client('sts').get_caller_identity()['Account']
        
        # 检查ConfigBucket是否为空，如果为空则在第一个region创建新的存储桶
        config_bucket = parameters['ConfigBucket']
        if not config_bucket:
            primary_region = parameters['enable_region'][0]  # 使用第一个region创建存储桶
            config_bucket = f'aws-config-bucket-{account_id}-{primary_region}'
            parameters['ConfigBucket'] = config_bucket
            config_bucket = create_config_bucket(config_bucket, primary_region)
            logger.info(f'使用新创建的S3存储桶: {config_bucket}')
            
        
        # 遍历每个region并设置Config
        for region in parameters['enable_region']:
            logger.info(f'正在为region {region}配置AWS Config...')
            
            # 创建AWS Config客户端
            config_client = boto3.client('config', region_name=region)
            
            # 配置记录器
            recorder_name = 'aws-config-recorder'
            try:
                config_client.put_configuration_recorder(
                    ConfigurationRecorder={
                        'name': recorder_name,
                        'roleARN': role_arn,
                        'recordingMode': {
                            'recordingFrequency': parameters['RecordingFrequency']
                        },
                        'recordingGroup': {
                            'allSupported': parameters['AllSupported'],
                            'includeGlobalResourceTypes': parameters['IncludeGlobalResourceTypes']
                        } if parameters['AllSupported'] else {
                            'allSupported': parameters['AllSupported'],
                            'includeGlobalResourceTypes': parameters['IncludeGlobalResourceTypes'],
                            'resourceTypes': resource_types
                        }
                    }
                )
                logger.info(f'在region {region}成功创建配置记录器')
            except ClientError as e:
                logger.error(f'在region {region}创建配置记录器失败: {str(e)}')
                raise
            
            # 配置投递通道
            try:
                delivery_channel_config = {
                    'name': parameters['DeliveryChannelName'],
                    's3BucketName': config_bucket,
                    'configSnapshotDeliveryProperties': {
                        'deliveryFrequency': parameters['Frequency']
                    }
                }
                
                # 只有当TopicArn不为空时才添加SNS配置
                if parameters['TopicArn']:
                    delivery_channel_config['snsTopicARN'] = parameters['TopicArn']
                
                config_client.put_delivery_channel(
                    DeliveryChannel=delivery_channel_config
                )
                logger.info(f'在region {region}成功创建投递通道')
            except ClientError as e:
                logger.error(f'在region {region}创建投递通道失败: {str(e)}')
                raise
            
            # 启动配置记录器
            try:
                config_client.start_configuration_recorder(
                    ConfigurationRecorderName=recorder_name
                )
                logger.info(f'在region {region}成功启动配置记录器')
            except ClientError as e:
                logger.error(f'在region {region}启动配置记录器失败: {str(e)}')
                raise
            
            logger.info(f'region {region}的AWS Config配置完成')

            
    except Exception as e:
        logger.error(f'设置AWS Config失败: {str(e)}')
        raise

def main():
    try:
        # 读取参数文件
        parameters = read_json_file('parameter.json')
        
        # 设置AWS Config
        setup_aws_config(parameters)
        logger.info('AWS Config设置完成')
        
    except Exception as e:
        logger.error(f'程序执行失败: {str(e)}')
        raise

if __name__ == '__main__':
    main()