import boto3, botocore, os, string 
import string

UNMANAGED_OUs=["ou-exam-00000001","ou-exam-00000002","ou-exam-00000003","ou-exam-00000004"]

def get_group_id(sso_client, SSOInstanceId, group_name):
  group_exists = True 
  try:  
    get_group_id_response = sso_client.get_group_id(
        AlternateIdentifier={
          'UniqueAttribute': {
              'AttributePath': 'displayName',
              'AttributeValue': group_name
          }
        },
        IdentityStoreId=SSOInstanceId
    )
  except sso_client.exceptions.ResourceNotFoundException as e:
    print("Group Name {} does not exists.".format(group_name))
    group_exists = False 
  if group_exists:
    GroupId=(get_group_id_response["GroupId"])
    return(GroupId)
  else: 
    return None

#def get_accounts(role):
def get_accounts(org_client):
    #response = org_client.list_accounts()
    p = org_client.get_paginator('list_accounts')
    response = p.paginate().build_full_result()
    results = response["Accounts"]
    while "NextToken" in response:
      response = org_client.list_accounts(NextToken=response["NextToken"])
      results.extend(response["Accounts"]) 
    return(results)

#def is_account_active(role, accountid):
def is_account_active(org_client, accountid):
    response = org_client.describe_account(AccountId=accountid)
    results = response["Account"]
    #print("Response: ", response)
    if results.get('Status') == "SUSPENDED":
      print('Account:' + accountid + 'is ' + results.get('Status'))
      return False
    else:
      return True

def is_managed_account(org_client, accountid):
    print('Checking Account Parent Details for Account', accountid)
    response = org_client.list_parents(ChildId=accountid)
    parents = response["Parents"]
    for parent in parents:
      myId = parent.get('Id')
      #print('Check if Parent Id=', myId, ' is unmanaged.')
      myType = parent.get('Type')
      if myType == 'ROOT':    # Accounts in the ROOT are not managed by us 
        print('Parent Identified as ROOT:', myType)
        return False
      else: # check if the account UNMANAGED
        response = org_client.describe_organizational_unit(OrganizationalUnitId=myId)
        myOU = response["OrganizationalUnit"]
        OUName = myOU.get('Name')
        if myId in UNMANAGED_OUs:
          print('Parent Identified as -Unmanaged OU-:', OUName)
          return False 
        # if OUName.lower() == 'unmanaged' or OUName.lower() == 'security':
        #   print('Parent Identified as -Unmanaged OU-:', OUName)
        #   return False 
      return True # Otherwise we manage it!