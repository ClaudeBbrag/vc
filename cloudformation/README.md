# CloudFormation Templates for Seed-VC

AWS CloudFormation templates for deploying Seed-VC infrastructure.

## Overview

This directory contains CloudFormation templates as an alternative to Terraform for deploying Seed-VC on AWS.

**Template:** `seedvc-eks-cluster.yaml`

Creates:
- VPC with public/private subnets
- EKS cluster with Kubernetes 1.28
- GPU node group (g4dn.xlarge by default)
- CPU node group (t3.medium by default)
- ECR repository for Docker images
- S3 bucket for model storage

## Quick Start

### Prerequisites

- AWS CLI installed and configured
- AWS account with EKS permissions

### Deploy

```bash
# Create stack
aws cloudformation create-stack \
    --stack-name seedvc-production \
    --template-body file://seedvc-eks-cluster.yaml \
    --capabilities CAPABILITY_IAM \
    --parameters \
        ParameterKey=ClusterName,ParameterValue=seedvc-production \
        ParameterKey=GPUNodeGroupDesiredSize,ParameterValue=3

# Wait for completion (15-20 minutes)
aws cloudformation wait stack-create-complete \
    --stack-name seedvc-production

# Get outputs
aws cloudformation describe-stacks \
    --stack-name seedvc-production \
    --query 'Stacks[0].Outputs'
```

### Configure kubectl

```bash
aws eks update-kubeconfig --region us-west-2 --name seedvc-production
```

### Verify

```bash
kubectl get nodes
```

## Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| ClusterName | seedvc-production | EKS cluster name |
| KubernetesVersion | 1.28 | Kubernetes version |
| GPUInstanceType | g4dn.xlarge | GPU instance type |
| GPUNodeGroupDesiredSize | 3 | Desired GPU nodes |
| GPUNodeGroupMinSize | 3 | Min GPU nodes |
| GPUNodeGroupMaxSize | 20 | Max GPU nodes |
| CPUInstanceType | t3.medium | CPU instance type |
| CPUNodeGroupDesiredSize | 2 | Desired CPU nodes |

## Custom Parameters

Create a parameters file:

```json
[
  {
    "ParameterKey": "ClusterName",
    "ParameterValue": "seedvc-prod"
  },
  {
    "ParameterKey": "GPUInstanceType",
    "ParameterValue": "g5.xlarge"
  },
  {
    "ParameterKey": "GPUNodeGroupDesiredSize",
    "ParameterValue": "5"
  }
]
```

Deploy with parameters file:

```bash
aws cloudformation create-stack \
    --stack-name seedvc-production \
    --template-body file://seedvc-eks-cluster.yaml \
    --parameters file://parameters.json \
    --capabilities CAPABILITY_IAM
```

## Update Stack

```bash
aws cloudformation update-stack \
    --stack-name seedvc-production \
    --template-body file://seedvc-eks-cluster.yaml \
    --parameters file://parameters.json \
    --capabilities CAPABILITY_IAM
```

## Delete Stack

**Warning:** This deletes ALL resources!

```bash
aws cloudformation delete-stack --stack-name seedvc-production
```

## Outputs

After deployment, get outputs:

```bash
aws cloudformation describe-stacks \
    --stack-name seedvc-production \
    --query 'Stacks[0].Outputs' \
    --output table
```

Example outputs:
- ClusterEndpoint
- ECRRepositoryURI
- ModelsBucketName
- ConfigureKubectl command

## Cost Estimate

Same as Terraform:
- 3× g4dn.xlarge: $1.14/hour
- 2× t3.medium: $0.08/hour
- NAT Gateway: $0.045/hour
- **Total: ~$1.29/hour (~$930/month)**

## Comparison: CloudFormation vs Terraform

| Feature | CloudFormation | Terraform |
|---------|---------------|-----------|
| **AWS Native** | ✅ Yes | ❌ No |
| **Multi-Cloud** | ❌ No | ✅ Yes |
| **State Management** | ✅ Automatic | ⚠️ Manual setup |
| **Modularity** | ⚠️ Nested stacks | ✅ Excellent |
| **Learning Curve** | Medium | Medium |
| **Community** | Large (AWS) | Very large |

**Recommendation:**
- Use **CloudFormation** if you're AWS-only
- Use **Terraform** if you need multi-cloud or prefer HCL syntax

## Troubleshooting

### Stack Creation Failed

```bash
# Get failure reason
aws cloudformation describe-stack-events \
    --stack-name seedvc-production \
    --query 'StackEvents[?ResourceStatus==`CREATE_FAILED`]'
```

### EKS Cluster Not Accessible

```bash
# Update kubeconfig
aws eks update-kubeconfig --region us-west-2 --name seedvc-production

# Verify
kubectl get svc
```

## Next Steps

1. Configure kubectl (see output)
2. Deploy NVIDIA device plugin
3. Deploy Seed-VC application (see ../k8s/)
4. Set up monitoring

## Resources

- [AWS CloudFormation Docs](https://docs.aws.amazon.com/cloudformation/)
- [EKS User Guide](https://docs.aws.amazon.com/eks/)
- [CloudFormation Best Practices](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/best-practices.html)
