# Terraform Infrastructure for Seed-VC

Complete AWS infrastructure as code for deploying Seed-VC with GPU support.

## Architecture

This Terraform configuration creates:

- **EKS Cluster** with GPU nodes (NVIDIA T4/A10G)
- **VPC** with public/private subnets across 3 AZs
- **Application Load Balancer** for HTTP/WebSocket (Janus)
- **Network Load Balancer** for RTP/UDP traffic
- **ECR Repository** for Docker images
- **S3 Bucket** for model storage
- **CloudWatch** for logging
- **Route53 + ACM** (optional) for custom domain + SSL

### Cost Estimate

**Development (3 GPU nodes, 2 CPU nodes):**
- GPU: 3× g4dn.xlarge @ $0.526/hour = $1.14/hour
- CPU: 2× t3.medium @ $0.042/hour = $0.08/hour
- NAT Gateway: 1× $0.045/hour = $0.045/hour
- ALB: $0.0225/hour
- **Total: ~$1.29/hour (~$930/month)**

**Production (10 GPU nodes, 5 CPU nodes):**
- GPU: 10× g4dn.xlarge = $3.80/hour
- CPU: 5× t3.medium = $0.21/hour
- NAT Gateway: 3× $0.045/hour = $0.135/hour
- ALB + NLB: $0.045/hour
- **Total: ~$4.19/hour (~$3,017/month)**

**Cost Optimization:**
- Use spot instances: Save up to 70% on GPU costs
- Use single NAT gateway: Save $0.09/hour ($65/month)
- Use smaller instances during off-peak
- Enable HPA to scale down when idle

## Prerequisites

1. **AWS Account** with appropriate permissions
2. **AWS CLI** configured
   ```bash
   aws configure
   ```
3. **Terraform** 1.0+
   ```bash
   # Install Terraform
   wget https://releases.hashicorp.com/terraform/1.6.0/terraform_1.6.0_linux_amd64.zip
   unzip terraform_1.6.0_linux_amd64.zip
   sudo mv terraform /usr/local/bin/
   ```
4. **kubectl** for Kubernetes management
   ```bash
   curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
   sudo install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl
   ```

## Quick Start

### 1. Configure Variables

```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars with your settings
```

### 2. Initialize Terraform

```bash
terraform init
```

### 3. Plan Infrastructure

```bash
terraform plan
```

Review the plan carefully. This will show you all resources to be created and estimated costs.

### 4. Apply Infrastructure

```bash
terraform apply
```

Type `yes` when prompted. This will take 15-20 minutes to create the EKS cluster.

### 5. Configure kubectl

```bash
aws eks update-kubeconfig --region us-west-2 --name seedvc-production
```

### 6. Verify Cluster

```bash
kubectl get nodes
# You should see GPU and CPU nodes

kubectl get nodes -L node.kubernetes.io/instance-type
# Check instance types
```

### 7. Deploy Seed-VC

```bash
# Build and push Docker image
cd ..
docker build -t seedvc:latest .

# Tag and push to ECR
$(aws ecr get-login-password --region us-west-2 | docker login --username AWS --password-stdin YOUR_ECR_URL)
docker tag seedvc:latest YOUR_ECR_URL/seedvc:latest
docker push YOUR_ECR_URL/seedvc:latest

# Deploy to Kubernetes
kubectl apply -f k8s/
```

## Directory Structure

```
terraform/
├── main.tf                 # Main configuration
├── variables.tf            # Variable definitions
├── terraform.tfvars        # Your values (gitignored)
├── terraform.tfvars.example # Example values
├── outputs.tf              # Output definitions (in main.tf)
├── modules/
│   ├── vpc/               # VPC module
│   └── eks/               # EKS cluster module
└── README.md              # This file
```

## Modules

### VPC Module

Creates:
- VPC with custom CIDR
- 3 public subnets (one per AZ)
- 3 private subnets (one per AZ)
- Internet Gateway
- NAT Gateways (1 or 3, configurable)
- Route tables

### EKS Module

Creates:
- EKS cluster
- GPU node group (with NVIDIA device plugin)
- CPU node group
- IAM roles and policies
- Security groups

## Configuration

### Key Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `aws_region` | `us-west-2` | AWS region |
| `environment` | `production` | Environment name |
| `gpu_instance_types` | `["g4dn.xlarge"]` | GPU instance types |
| `gpu_nodes_desired` | `3` | Desired GPU nodes |
| `gpu_nodes_max` | `20` | Maximum GPU nodes |
| `domain_name` | `""` | Custom domain (optional) |
| `spot_instances_enabled` | `false` | Use spot instances |

### GPU Instance Types

| Instance Type | GPU | vCPUs | RAM | Price/hour | Use Case |
|---------------|-----|-------|-----|------------|----------|
| `g4dn.xlarge` | 1× T4 | 4 | 16 GB | $0.526 | Development |
| `g4dn.2xlarge` | 1× T4 | 8 | 32 GB | $0.752 | Production |
| `g5.xlarge` | 1× A10G | 4 | 16 GB | $1.006 | Better performance |
| `g5.2xlarge` | 1× A10G | 8 | 32 GB | $1.212 | Best performance |
| `p3.2xlarge` | 1× V100 | 8 | 61 GB | $3.06 | High-end |

**Recommendation:** `g4dn.xlarge` for most use cases (best price/performance)

## Outputs

After `terraform apply`, you'll see:

```
eks_cluster_endpoint = "https://XXX.eks.amazonaws.com"
eks_cluster_name = "seedvc-production"
alb_dns_name = "seedvc-alb-XXX.us-west-2.elb.amazonaws.com"
nlb_dns_name = "seedvc-nlb-XXX.us-west-2.elb.amazonaws.com"
ecr_repository_url = "123456789.dkr.ecr.us-west-2.amazonaws.com/seedvc"
s3_models_bucket = "seedvc-production-models"
configure_kubectl = "aws eks update-kubeconfig --region us-west-2 --name seedvc-production"
```

## Advanced Configuration

### Enable Spot Instances (Save 70% on GPU costs)

```hcl
# terraform.tfvars
spot_instances_enabled = true
```

**Pros:**
- 60-70% cost savings
- Same performance

**Cons:**
- Can be interrupted with 2-minute warning
- Need to handle pod disruption

### Custom Domain + SSL

```hcl
# terraform.tfvars
domain_name = "voice.example.com"
```

This creates:
- Route53 hosted zone
- ACM certificate (requires DNS validation)
- ALB listener rules for HTTPS

**After apply:**
1. Update your domain's nameservers to Route53 NS records
2. Wait for ACM certificate validation (~5-30 minutes)
3. Access your app at `https://voice.example.com`

### Multi-Region Deployment

```bash
# Deploy to multiple regions
terraform workspace new us-west-2
terraform apply -var="aws_region=us-west-2"

terraform workspace new eu-west-1
terraform apply -var="aws_region=eu-west-1"
```

### Remote State (Recommended for Production)

Create S3 bucket and DynamoDB table for state locking:

```bash
# Create state bucket
aws s3api create-bucket \
    --bucket your-terraform-state \
    --region us-west-2 \
    --create-bucket-configuration LocationConstraint=us-west-2

aws s3api put-bucket-versioning \
    --bucket your-terraform-state \
    --versioning-configuration Status=Enabled

# Create lock table
aws dynamodb create-table \
    --table-name terraform-locks \
    --attribute-definitions AttributeName=LockID,AttributeType=S \
    --key-schema AttributeName=LockID,KeyType=HASH \
    --billing-mode PAY_PER_REQUEST \
    --region us-west-2
```

Then uncomment backend configuration in `main.tf`.

## Monitoring

### CloudWatch Dashboards

```bash
# View logs
aws logs tail /aws/eks/seedvc-production/seedvc --follow
```

### Cost Explorer

```bash
# View monthly costs
aws ce get-cost-and-usage \
    --time-period Start=2024-01-01,End=2024-01-31 \
    --granularity MONTHLY \
    --metrics BlendedCost \
    --group-by Type=DIMENSION,Key=SERVICE
```

## Scaling

### Manual Scaling

```bash
# Scale GPU nodes
aws eks update-nodegroup-config \
    --cluster-name seedvc-production \
    --nodegroup-name gpu-nodes \
    --scaling-config minSize=5,maxSize=30,desiredSize=10
```

### Auto-Scaling

HPA is configured in `k8s/hpa.yaml`:
- Scales based on CPU/GPU utilization
- Min: 3 pods, Max: 20 pods
- Target: 70% CPU, 80% GPU

## Backup & Disaster Recovery

### Backup EKS Configuration

```bash
# Backup all Kubernetes resources
kubectl get all --all-namespaces -o yaml > k8s-backup.yaml

# Backup to S3
aws s3 cp k8s-backup.yaml s3://your-backup-bucket/
```

### Restore

```bash
# Restore from backup
kubectl apply -f k8s-backup.yaml
```

## Troubleshooting

### Nodes Not Ready

```bash
# Check node status
kubectl describe node NODE_NAME

# Check NVIDIA device plugin
kubectl logs -n kube-system -l name=nvidia-device-plugin-ds
```

### Cannot Pull ECR Images

```bash
# Verify ECR permissions
aws ecr get-login-password --region us-west-2 | docker login --username AWS --password-stdin YOUR_ECR_URL

# Check IAM role permissions
kubectl describe serviceaccount -n kube-system
```

### High Costs

1. Check idle resources:
   ```bash
   kubectl top nodes
   kubectl top pods
   ```

2. Enable HPA to scale down when idle

3. Consider spot instances

4. Use single NAT gateway for dev

## Cleanup

**Warning:** This will destroy ALL resources and delete data!

```bash
# Delete Kubernetes resources first
kubectl delete -f k8s/

# Destroy Terraform infrastructure
terraform destroy
```

Type `yes` to confirm.

## Best Practices

1. **Use workspaces** for multiple environments
2. **Enable state locking** with DynamoDB
3. **Store state remotely** in S3
4. **Tag all resources** for cost tracking
5. **Use spot instances** for non-critical workloads
6. **Enable auto-scaling** to optimize costs
7. **Monitor costs** with AWS Cost Explorer
8. **Set up alerts** for budget thresholds
9. **Regularly update** Terraform and providers
10. **Test in dev** before applying to production

## Security

- All traffic encrypted (TLS/DTLS-SRTP)
- Private subnets for worker nodes
- Security groups restrict access
- IAM roles with least privilege
- ECR image scanning enabled
- Secrets stored in AWS Secrets Manager (add if needed)

## Support

For issues:
- AWS EKS: https://docs.aws.amazon.com/eks/
- Terraform: https://www.terraform.io/docs
- Seed-VC: See main documentation

## License

Same as parent Seed-VC project
