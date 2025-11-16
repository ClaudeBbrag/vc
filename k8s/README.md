## Kubernetes Deployment for Seed-VC

### Quick Start

```bash
# 1. Create namespace
kubectl apply -f namespace.yaml

# 2. Create ConfigMap with reference voice
kubectl create configmap seedvc-reference-voice \
    --from-file=reference.wav=../data/reference.wav \
    -n seedvc

# 3. Create PVC
kubectl apply -f pvc.yaml

# 4. Deploy application
kubectl apply -f deployment.yaml

# 5. Create service
kubectl apply -f service.yaml

# 6. Create HPA (autoscaler)
kubectl apply -f hpa.yaml
```

### Check Status

```bash
# Watch pods
kubectl get pods -n seedvc -w

# Check logs
kubectl logs -f deployment/seedvc-rtp -n seedvc

# Check service
kubectl get svc -n seedvc

# Check HPA
kubectl get hpa -n seedvc
```

### Scale Manually

```bash
# Scale to 5 replicas
kubectl scale deployment/seedvc-rtp --replicas=5 -n seedvc
```

### Delete Everything

```bash
kubectl delete namespace seedvc
```
