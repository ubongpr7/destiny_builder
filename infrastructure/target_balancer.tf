# Create target group
aws elbv2 create-target-group \
  --name destiny-target-group \
  --protocol HTTP \
  --port 80 \
  --vpc-id $VPC_ID \
  --health-check-path /health/ \
  --target-type instance

# Note the target group ARN
TARGET_GROUP_ARN=arn:aws:elasticloadbalancing:us-east-1:xxxxxxxxxxxx:targetgroup/destiny-target-group/xxxxxxxxxxxxxxxx

# Create load balancer
aws elbv2 create-load-balancer \
  --name destiny-load-balancer \
  --subnets $PUBLIC_SUBNET_1A $PUBLIC_SUBNET_1B \
  --security-groups $LB_SG \
  --type application

# Note the load balancer ARN
LB_ARN=arn:aws:elasticloadbalancing:us-east-1:xxxxxxxxxxxx:loadbalancer/app/destiny-load-balancer/xxxxxxxxxxxxxxxx

# Create HTTP listener
aws elbv2 create-listener \
  --load-balancer-arn $LB_ARN \
  --protocol HTTP \
  --port 80 \
  --default-actions Type=forward,TargetGroupArn=$TARGET_GROUP_ARN