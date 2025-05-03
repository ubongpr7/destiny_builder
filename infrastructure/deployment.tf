#!/bin/bash
# deploy.sh

# Set variables
ASG_NAME="destiny-asg"
DEPLOY_VERSION=$(date +%Y%m%d%H%M%S)

# Pull latest code and create a new AMI
echo "Pulling latest code and creating new AMI..."

# Get an instance ID from the auto scaling group
INSTANCE_ID=$(aws autoscaling describe-auto-scaling-groups --auto-scaling-group-names $ASG_NAME --query "AutoScalingGroups[0].Instances[0].InstanceId" --output text)

# Create AMI from the instance
AMI_ID=$(aws ec2 create-image --instance-id $INSTANCE_ID --name "destiny-backend-$DEPLOY_VERSION" --description "Destiny Backend $DEPLOY_VERSION" --no-reboot --query "ImageId" --output text)

echo "Created AMI: $AMI_ID"

# Wait for AMI to be available
echo "Waiting for AMI to be available..."
aws ec2 wait image-available --image-ids $AMI_ID

# Create new launch template version
echo "Creating new launch template version..."
LAUNCH_TEMPLATE_ID=$(aws ec2 describe-launch-templates --filters "Name=launch-template-name,Values=destiny-launch-template" --query "LaunchTemplates[0].LaunchTemplateId" --output text)

aws ec2 create-launch-template-version \
  --launch-template-id $LAUNCH_TEMPLATE_ID \
  --version-description "Version $DEPLOY_VERSION" \
  --source-version '$Latest' \
  --launch-template-data "{\"ImageId\":\"$AMI_ID\"}"

# Update auto scaling group to use new launch template version
echo "Updating auto scaling group..."
aws autoscaling update-auto-scaling-group \
  --auto-scaling-group-name $ASG_NAME \
  --launch-template LaunchTemplateId=$LAUNCH_TEMPLATE_ID,Version='$Latest'

# Start instance refresh
echo "Starting instance refresh..."
aws autoscaling start-instance-refresh \
  --auto-scaling-group-name $ASG_NAME \
  --strategy Rolling \
  --preferences MinHealthyPercentage=90,InstanceWarmup=300

echo "Deployment initiated. Check AWS console for status."