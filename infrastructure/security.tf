# Create security group for load balancer
aws ec2 create-security-group --group-name destiny-lb-sg --description "Security group for load balancer" --vpc-id $VPC_ID

# Note the security group ID
LB_SG=sg-xxxxxxxxxxxxxxxxx

# Allow HTTP and HTTPS traffic to load balancer
aws ec2 authorize-security-group-ingress --group-id $LB_SG --protocol tcp --port 80 --cidr 0.0.0.0/0
aws ec2 authorize-security-group-ingress --group-id $LB_SG --protocol tcp --port 443 --cidr 0.0.0.0/0

# Create security group for EC2 instances
aws ec2 create-security-group --group-name destiny-ec2-sg --description "Security group for EC2 instances" --vpc-id $VPC_ID

# Note the security group ID
EC2_SG=sg-xxxxxxxxxxxxxxxxx

# Allow SSH access from your IP
aws ec2 authorize-security-group-ingress --group-id $EC2_SG --protocol tcp --port 22 --cidr YOUR_IP/32

# Allow HTTP traffic from load balancer security group
aws ec2 authorize-security-group-ingress --group-id $EC2_SG --protocol tcp --port 80 --source-group $LB_SG