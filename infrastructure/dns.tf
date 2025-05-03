# Get the load balancer DNS name
LB_DNS=$(aws elbv2 describe-load-balancers --load-balancer-arns $LB_ARN --query "LoadBalancers[0].DNSName" --output text)

# Create hosted zone (if you don't already have one)
aws route53 create-hosted-zone \
  --name destinybuilders.africa \
  --caller-reference $(date +%s)

# Note the hosted zone ID
HOSTED_ZONE_ID=Z1234567890ABCDEFGHIJ

# Create DNS record for dev subdomain
aws route53 change-resource-record-sets \
  --hosted-zone-id $HOSTED_ZONE_ID \
  --change-batch "{
    \"Changes\": [
      {
        \"Action\": \"CREATE\",
        \"ResourceRecordSet\": {
          \"Name\": \"dev.destinybuilders.africa\",
          \"Type\": \"A\",
          \"AliasTarget\": {
            \"HostedZoneId\": \"Z35SXDOTRQ7X7K\",
            \"DNSName\": \"$LB_DNS\",
            \"EvaluateTargetHealth\": true
          }
        }
      }
    ]
  }"