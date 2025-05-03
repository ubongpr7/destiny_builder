# Get the latest Ubuntu AMI ID
AMI_ID=$(aws ec2 describe-images --owners 099720109477 --filters "Name=name,Values=ubuntu/images/hvm-ssd/ubuntu-focal-20.04-amd64-server-*" "Name=state,Values=available" --query "sort_by(Images, &CreationDate)[-1].ImageId" --output text)

# Create launch template
aws ec2 create-launch-template \
  --launch-template-name destiny-launch-template \
  --version-description "Initial version" \
  --launch-template-data "{
    \"ImageId\": \"$AMI_ID\",
    \"InstanceType\": \"t2.micro\",
    \"KeyName\": \"your-key-pair-name\",
    \"SecurityGroupIds\": [\"$EC2_SG\"],
    \"UserData\": \"$(base64 -w 0 user-data.sh)\",
    \"TagSpecifications\": [{
      \"ResourceType\": \"instance\",
      \"Tags\": [{
        \"Key\": \"Name\",
        \"Value\": \"destiny-backend\"
      }]
    }]
  }"