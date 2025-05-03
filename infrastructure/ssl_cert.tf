# Request certificate
aws acm request-certificate \
  --domain-name dev.destinybuilders.africa \
  --validation-method DNS \
  --region us-east-1

# Note the certificate ARN
CERT_ARN=arn:aws:acm:us-east-1:xxxxxxxxxxxx:certificate/xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx

# Get validation records
aws acm describe-certificate \
  --certificate-arn $CERT_ARN \
  --query "Certificate.DomainValidationOptions[0].ResourceRecord" \
  --output json

# Add validation records to Route 53 (follow the output from the previous command)
# Once validated, add HTTPS listener to load balancer

aws elbv2 create-listener \
  --load-balancer-arn $LB_ARN \
  --protocol HTTPS \
  --port 443 \
  --certificates CertificateArn=$CERT_ARN \
  --ssl-policy ELBSecurityPolicy-2016-08 \
  --default-actions Type=forward,TargetGroupArn=$TARGET_GROUP_ARN

# Modify HTTP listener to redirect to HTTPS
aws elbv2 modify-listener \
  --listener-arn $HTTP_LISTENER_ARN \
  --default-actions "Type=redirect,RedirectConfig={Protocol=HTTPS,Port=443,StatusCode=HTTP_301}"