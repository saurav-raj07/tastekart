#!/usr/bin/env python3
"""
TasteKart 1-Click Launch & Redeployment Script
Fully automates:
1. Terraform apply (Infra provisioning)
2. ECR Login & Docker push
3. Instance readiness wait (SSM & K3s)
4. Kubernetes manifest bundling & deployment
5. Health check verification
"""

import os
import sys
import json
import base64
import time
import subprocess

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TERRAFORM_DIR = os.path.join(PROJECT_ROOT, "terraform")
AWS_REGION = "ap-south-1"

def run_cmd(cmd, cwd=PROJECT_ROOT, check=True):
    print(f"\n[RUNNING] {cmd}")
    res = subprocess.run(cmd, cwd=cwd, shell=True, text=True, capture_output=True)
    if check and res.returncode != 0:
        print(f"[ERROR] Command failed:\nSTDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}")
        sys.exit(res.returncode)
    return res

def step_terraform_apply():
    print("=" * 60)
    print("STEP 1: Provisioning / Updating AWS Infrastructure with Terraform")
    print("=" * 60)
    run_cmd("terraform apply -auto-approve", cwd=TERRAFORM_DIR)
    
    # Extract outputs
    res = run_cmd("terraform output -json", cwd=TERRAFORM_DIR)
    outputs = json.loads(res.stdout)
    
    instance_id = outputs["ec2_instance_id"]["value"]
    public_ip = outputs["ec2_public_ip"]["value"]
    ecr_url = outputs["ecr_repository_url"]["value"]
    app_url = outputs["app_url"]["value"]
    
    print(f"[SUCCESS] Infrastructure ready:")
    print(f"  - EC2 Instance ID: {instance_id}")
    print(f"  - Public Elastic IP: {public_ip}")
    print(f"  - ECR URL: {ecr_url}")
    print(f"  - App URL: {app_url}")
    
    return instance_id, public_ip, ecr_url, app_url

def step_push_image(ecr_url):
    print("\n" + "=" * 60)
    print("STEP 2: Authenticating and Pushing Image to ECR")
    print("=" * 60)
    
    # Login to ECR
    login_cmd = f"(aws ecr get-login-password --region {AWS_REGION}).Trim() | docker login --username AWS --password-stdin {ecr_url.split('/')[0]}"
    run_cmd(f"powershell -Command \"{login_cmd}\"")
    
    # Build image (uses cache if unchanged)
    tag = f"{ecr_url}:latest"
    print(f"Building Docker image: {tag}...")
    run_cmd(f"docker build -t {tag} .", cwd=PROJECT_ROOT)
    
    # Push image
    print(f"Pushing Docker image: {tag}...")
    run_cmd(f"docker push {tag}", cwd=PROJECT_ROOT)
    print("[SUCCESS] Image pushed to ECR.")

def wait_for_ssm_and_k3s(instance_id):
    print("\n" + "=" * 60)
    print("STEP 3: Waiting for EC2 Instance & K3s to be Ready")
    print("=" * 60)
    
    # 1. Wait for SSM
    print("Checking AWS Systems Manager (SSM) agent...")
    for i in range(30):
        res = run_cmd(
            f'aws ssm describe-instance-information --filters "Key=InstanceIds,Values={instance_id}" --region {AWS_REGION} --output json',
            check=False
        )
        if res.returncode == 0:
            try:
                info = json.loads(res.stdout).get("InstanceInformationList", [])
                if info and info[0].get("PingStatus") == "Online":
                    print("[SUCCESS] EC2 instance is Online via SSM.")
                    break
            except Exception:
                pass
        time.sleep(5)
        print(f"  Waiting for SSM agent... ({i * 5}s)")
    else:
        print("[WARNING] Timed out waiting for SSM, proceeding to check K3s...")

    # 2. Wait for K3s node
    print("Checking K3s Kubernetes node status...")
    for i in range(25):
        inv = send_ssm_command(instance_id, "kubectl get nodes")
        if inv and "Ready" in inv.get("StandardOutputContent", ""):
            print("[SUCCESS] K3s Node is Ready!")
            break
        time.sleep(5)
        print(f"  Waiting for K3s node to report Ready... ({i * 5}s)")

def send_ssm_command(instance_id, script):
    params = json.dumps({"commands": [script]})
    res = subprocess.run([
        'aws', 'ssm', 'send-command',
        '--instance-ids', instance_id,
        '--document-name', 'AWS-RunShellScript',
        '--parameters', params,
        '--region', AWS_REGION,
        '--output', 'json'
    ], capture_output=True, text=True)
    
    if res.returncode != 0:
        return None
    
    cmd_id = json.loads(res.stdout)['Command']['CommandId']
    for _ in range(30):
        time.sleep(2)
        inv = subprocess.run([
            'aws', 'ssm', 'get-command-invocation',
            '--command-id', cmd_id,
            '--instance-id', instance_id,
            '--region', AWS_REGION,
            '--output', 'json'
        ], capture_output=True, text=True)
        if inv.returncode == 0:
            data = json.loads(inv.stdout)
            if data.get("Status") in ['Success', 'Failed', 'Cancelled', 'TimedOut']:
                return data
    return None

def bundle_manifests():
    manifests = [
        'namespace.yaml',
        'configmap.yaml',
        'secret.yaml',
        'mongodb.yaml',
        'user-service.yaml',
        'catalog-service.yaml',
        'order-service.yaml',
        'partner-service.yaml',
        'app-gateway.yaml'
    ]
    combined = []
    for m in manifests:
        path = os.path.join(PROJECT_ROOT, 'k8s', m)
        with open(path, 'r', encoding='utf-8') as f:
            combined.append(f.read().strip())
    bundle = '\n---\n'.join(combined) + '\n'
    os.makedirs(os.path.join(PROJECT_ROOT, 'deploy'), exist_ok=True)
    with open(os.path.join(PROJECT_ROOT, 'deploy', 'k8s-bundle.yaml'), 'w', encoding='utf-8') as f:
        f.write(bundle)
    return bundle

def step_deploy_k8s(instance_id):
    print("\n" + "=" * 60)
    print("STEP 4: Deploying Kubernetes Manifests to K3s")
    print("=" * 60)
    
    bundle = bundle_manifests()
    b64_content = base64.b64encode(bundle.encode('utf-8')).decode('utf-8')
    
    deploy_script = f"""
    /usr/local/bin/refresh-ecr-token.sh
    echo '{b64_content}' | base64 -d | /usr/local/bin/kubectl apply -f -
    """
    
    res = send_ssm_command(instance_id, deploy_script)
    if res and res.get("Status") == "Success":
        print("[SUCCESS] Manifests applied to cluster:")
        print(res.get("StandardOutputContent"))
    else:
        print("[ERROR] Failed to apply manifests:\n", res)
        sys.exit(1)

def step_verify_and_wait(instance_id, app_url):
    print("\n" + "=" * 60)
    print("STEP 5: Verifying Health Check")
    print("=" * 60)
    
    for i in range(20):
        time.sleep(5)
        res = send_ssm_command(instance_id, "curl -s http://localhost:30001/api/health")
        if res:
            out = res.get("StandardOutputContent", "")
            if '"ok": true' in out or '"ok":true' in out:
                print(f"[SUCCESS] TasteKart is fully healthy!")
                print(f"Health Response: {out}")
                break
        print(f"  Waiting for pods to start and report healthy... ({(i + 1) * 5}s)")
    
    print("\n" + "*" * 60)
    print("TASTEKART IS LIVE!")
    print(f"--> Direct URL: {app_url}")
    print(f"--> Health Check: {app_url}/api/health")
    print("*" * 60)

def main():
    instance_id, public_ip, ecr_url, app_url = step_terraform_apply()
    step_push_image(ecr_url)
    wait_for_ssm_and_k3s(instance_id)
    step_deploy_k8s(instance_id)
    step_verify_and_wait(instance_id, app_url)

if __name__ == "__main__":
    main()
