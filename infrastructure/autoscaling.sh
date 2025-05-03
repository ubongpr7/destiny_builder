# Get the launch template ID
LAUNCH_TEMPLATE_ID=$(aws ec2 describe-launch-templates --launch-template-names destiny-launch-template --query "LaunchTemplates[0].LaunchTemplateId" --output text)

# Create auto scaling group
aws autoscaling create-auto-scaling-group \
  --auto-scaling-group-name destiny-asg \
  --launch-template LaunchTemplateId=$LAUNCH_TEMPLATE_ID,Version='$Latest' \
  --min-size 1 \
  --max-size 3 \
  --desired-capacity 1 \
  --vpc-zone-identifier "$PUBLIC_SUBNET_1A,$PUBLIC_SUBNET_1B" \
  --target-group-arns $TARGET_GROUP_ARN \
  --health-check-type ELB \
  --health-check-grace-period 300

# Create scaling policies (optional)
aws autoscaling put-scaling-policy \
  --auto-scaling-group-name destiny-asg \
  --policy-name destiny-scale-out \
  --policy-type SimpleScaling \
  --adjustment-type ChangeInCapacity \
  --scaling-adjustment 1 \
  --cooldown 300

aws autoscaling put-scaling-policy \
  --auto-scaling-group-name destiny-asg \
  --policy-name destiny-scale-in \
  --policy-type SimpleScaling \
  --adjustment-type ChangeInCapacity \
  --scaling-adjustment -1 \
  --cooldown 300