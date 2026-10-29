import boto3, botocore, os
import string, time
from troposphere import Template, Ref, Parameter, sso, Sub, Join
from troposphere.sso import Assignment
from troposphere.cloudformation import WaitConditionHandle
from sso_helpers import get_accounts, get_group_id, is_account_active, is_managed_account
from botocore.config import Config
from time import sleep

def sceptre_handler(sceptre_user_data):
    return Assignments(sceptre_user_data)
  
def Assignments(sceptre_user_data):

  my_config = Config(
    retries = {
        'max_attempts': 10,
        'mode': 'standard'
    }
  )

  sts_client = None
  while not sts_client:
      try:
          sts_client = boto3.client('sts', config=my_config)
      except:
          sts_client = None
  
  session_name = 'pipeline_session'

  response = sts_client.assume_role(RoleArn=sceptre_user_data["rolearn"], RoleSessionName=session_name)
  sso_client = boto3.client('identitystore',
                            region_name='ca-central-1',
                            aws_access_key_id=response['Credentials']['AccessKeyId'],
                            aws_secret_access_key=response['Credentials']['SecretAccessKey'],
                            aws_session_token=response['Credentials']['SessionToken'],
                            config=my_config)  

  org_client = boto3.client('organizations',
                            region_name='ca-central-1',
                            aws_access_key_id=response['Credentials']['AccessKeyId'],
                            aws_secret_access_key=response['Credentials']['SecretAccessKey'],
                            aws_session_token=response['Credentials']['SessionToken'],
                            config=my_config)

  ssm_client = boto3.client('ssm',
                            region_name='ca-central-1',
                            aws_access_key_id=response['Credentials']['AccessKeyId'],
                            aws_secret_access_key=response['Credentials']['SecretAccessKey'],
                            aws_session_token=response['Credentials']['SessionToken'],
                            config=my_config)


  target_groupid = None
  t = Template()
  myDesc = 'Team SSO Assignment - ' + sceptre_user_data['GroupName'] + ' - ' + sceptre_user_data['Permission'] + ''
  t.set_description(myDesc)      

  print('-----------------------------------------------------')
  print('SSM Prefix:', sceptre_user_data["SSMPrefix"])
  print('SSO Instance ID:', sceptre_user_data["SSOInstanceId"])
  print('SSO Instance ARN:', sceptre_user_data["SSOInstanceArn"])
  print('Group:', sceptre_user_data["GroupName"])
  print('Permission:', sceptre_user_data["Permission"])
  print('-----------------------------------------------------')

  account_list = get_accounts(org_client)

  target_groupid = get_group_id(sso_client, sceptre_user_data["SSOInstanceId"], sceptre_user_data["GroupName"])
  isPrivileged = sceptre_user_data.get("isPrivileged", "false").lower() == "true"

  # Pre-fetch the SSM parameter to avoid throttling during CloudFormation deployment
  ssm_param_name = sceptre_user_data["SSMPrefix"] + "/" + sceptre_user_data["Permission"]
  permission_set_arn = ssm_client.get_parameter(Name=ssm_param_name)['Parameter']['Value']
  
  print('Target GroupId:', target_groupid)
  if target_groupid is not None:
    print('Processing target_groupid:', target_groupid)
    previous = 'None'
    for account in account_list:
      #sleep(1.5)
      myId = account.get('Id')
      myName = account.get('Name')
      isProd = False 
      # Check for the prod account ids 
      if myId == '100000000005' or myId == '100000000225':
        isProd = True 
        print('prod account detected.')
      print('Checking if AccountId is active:', myId, ' and we manage it.')

      # Check if account has ManagedPAM tag set to true - skip if so
      print('Checking if AccountId has ManagedPAM Enabled')
      tags_response = org_client.list_tags_for_resource(ResourceId=myId)
      account_tags = {tag['Key']: tag['Value'] for tag in tags_response.get('Tags', [])}
      if account_tags.get('ManagedPAM', '').lower() == 'true' and isPrivileged:
          print(f'Account {myId} ({myName}) has ManagedPAM=true tag. Skipping permissions assignment.')
          continue

      # Note we only perform actions if account status is active and we manage it
      if (is_account_active(org_client, myId) and is_managed_account(org_client, myId)) or isProd:
        myName = sceptre_user_data["Permission"] + myId
        # myName = sceptre_user_data["Permission"] + myName.translate(str.maketrans('', '', string.punctuation))

        if previous == 'None':
          t.add_resource(Assignment(
            myName.replace(" ", ""),
            InstanceArn=sceptre_user_data["SSOInstanceArn"],
            PermissionSetArn=permission_set_arn, 
            TargetType='AWS_ACCOUNT',
            TargetId=myId,
            PrincipalType='GROUP', 
            PrincipalId=target_groupid
          ))
        else:
          t.add_resource(Assignment(
            myName.replace(" ", ""),
            DependsOn=previous,
            InstanceArn=sceptre_user_data["SSOInstanceArn"],
            PermissionSetArn=permission_set_arn, 
            TargetType='AWS_ACCOUNT',
            TargetId=myId,
            PrincipalType='GROUP', 
            PrincipalId=target_groupid
          ))
        #time.sleep(5)
        previous = myName.replace(" ", "")
  else:
    t.add_resource(WaitConditionHandle("myNullResource"))
  org_client.close()
  sso_client.close()
  ssm_client.close()
  sts_client.close()
  return t.to_yaml()


if __name__=="__main__":
  Assignments()