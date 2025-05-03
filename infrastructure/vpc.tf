# Create VPC
aws ec2 create-vpc --cidr-block 10.0.0.0/16 --tag-specifications 'ResourceType=vpc,Tags=[{Key=Name,Value=destiny-vpc}]'

# Note the VPC ID from the output
VPC_ID=vpc-xxxxxxxxxxxxxxxxx

# Create Internet Gateway
aws ec2 create-internet-gateway --tag-specifications 'ResourceType=internet-gateway,Tags=[{Key=Name,Value=destiny-igw}]'

# Note the Internet Gateway ID
IGW_ID=igw-xxxxxxxxxxxxxxxxx

# Attach Internet Gateway to VPC
aws ec2 attach-internet-gateway --internet-gateway-id $IGW_ID --vpc-id $VPC_ID

# Create public subnet in us-east-1a
aws ec2 create-subnet --vpc-id $VPC_ID --cidr-block 10.0.1.0/24 --availability-zone us-east-1a --tag-specifications 'ResourceType=subnet,Tags=[{Key=Name,Value=destiny-public-1a}]'

# Create public subnet in us-east-1b
aws ec2 create-subnet --vpc-id $VPC_ID --cidr-block 10.0.2.0/24 --availability-zone us-east-1b --tag-specifications 'ResourceType=subnet,Tags=[{Key=Name,Value=destiny-public-1b}]'

# Note the subnet IDs
PUBLIC_SUBNET_1A=subnet-xxxxxxxxxxxxxxxxx
PUBLIC_SUBNET_1B=subnet-xxxxxxxxxxxxxxxxx

# Create route table for public subnets
aws ec2 create-route-table --vpc-id $VPC_ID --tag-specifications 'ResourceType=route-table,Tags=[{Key=Name,Value=destiny-public-rt}]'

# Note the route table ID
PUBLIC_RT=rtb-xxxxxxxxxxxxxxxxx

# Create route to Internet Gateway
aws ec2 create-route --route-table-id $PUBLIC_RT --destination-cidr-block 0.0.0.0/0 --gateway-id $IGW_ID

# Associate route table with public subnets
aws ec2 associate-route-table --route-table-id $PUBLIC_RT --subnet-id $PUBLIC_SUBNET_1A
aws ec2 associate-route-table --route-table-id $PUBLIC_RT --subnet-id $PUBLIC_SUBNET_1B