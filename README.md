# 需求描述

为了节约config成本，仅开启security hub control对应的最小必要的config资源类型。

By default, AWS Config enables recording for more than 300 resource types in your account. Today, Security Hub has controls that cover approximately 60 of those resource types. This blog post walks you through how to set up and optimize the AWS Config recorder when it is used for controls in Security Hub. 

# 部署指引

1. 修改parameter.json, 指定需要开启的region和开启方式


| 参数名称                            | 默认值                               | 描述                                                                                                     |
| ------------------------------- | --------------------------------- | ------------------------------------------------------------------------------------------------------ |
| RoleARN                         | <None>                            | 执行脚本的role的ARN，需要有config:Put*和config:PutDeliveryChannel权限                                              |
| enable_region                   | <All>                             | 指定需要开启config的region, 如果不填写则是所有region都会开启，如果填写比如["us-east-1"]，则只开启指定的region             |
| AllSupported                    | false                             | 是否开启所有config资源类型，默认为false，因为本程序主要为了实现按需开启资源类型，如果需要设置为true，则ResourceTypes则要为空                           |
| IncludeGlobalResourceTypes      | False                             | 是否开启所有config全局资源类型                                                                                     |
| AllSupportedGlobalResourceTypes | False                             | 是否开启所有config全局资源类型                                                                                     |
| ResourceTypes                   | "mini_config_resource_types.json" | 开启的config资源类型，从json文件中读取，比如["AWS::EC2::Instance","AWS::CloudTrail::Trail"]                             |
| RecordingFrequency              | CONTINUOUS                        | 配置变更记录频率，可以设置为CONTINUOUS或者DAILY                                                                        |
| DeliveryChannelName             | <Generated>                       | 配置变更记录的投递通道名称                                                                                          |
| Frequency                       | TwentyFour_Hours                  | 配置变更记录的投递频率, AllowedValues: "One_Hour", "Three_Hours", "Six_Hours", "Twelve_Hours", "TwentyFour_Hours" |
| TopicArn                        | <None>                            | 配置变更记录的投递通道的SNS主题，默认没有SNS，也不允许配置，后续可以手动在控制台配置                                                          |
| NotificationEmail               | <None>                            | 配置订阅SNS主题的email，接收Config推送的通知，默认没有，也不允许配置，后续可以手动在控制台配置                                                 |
| ConfigBucket                    | <None>                            | 保存配置变更记录的存储桶名称，如果为空则会创建一个新的存储桶                                                                         |

2. 使用方法：
要运行enable_config.py，请按以下步骤操作：

1. 创建并激活Python虚拟环境：
```bash
# 创建虚拟环境
python3 -m venv venv

# 激活虚拟环境
# 在macOS/Linux上：
source venv/bin/activate
# 在Windows上：
# venv\Scripts\activate
 ```

2. 安装依赖包：
```bash
pip install -r requirements.txt
 ```

3. 执行脚本：
```bash
python enable_config.py
 ```

注意：执行脚本前，请确保：

- AWS凭证已正确配置
- parameter.json文件包含了正确的配置参数
- 相关的资源类型JSON文件（如max_config_resource_types.json或mini_config_resource_types.json）存在且格式正确
