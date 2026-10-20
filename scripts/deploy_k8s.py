import os
import base64
import json
import subprocess
import time

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
        path = os.path.join('k8s', m)
        with open(path, 'r', encoding='utf-8') as f:
            combined.append(f.read().strip())
    bundle = '\n---\n'.join(combined) + '\n'
    os.makedirs('deploy', exist_ok=True)
    with open('deploy/k8s-bundle.yaml', 'w', encoding='utf-8') as f:
        f.write(bundle)
    print(f"Generated deploy/k8s-bundle.yaml ({len(bundle)} bytes)")
    return bundle

def deploy():
    bundle = bundle_manifests()
    b64_content = base64.b64encode(bundle.encode('utf-8')).decode('utf-8')

    script = f"""
    /usr/local/bin/refresh-ecr-token.sh
    echo '{b64_content}' | base64 -d | /usr/local/bin/kubectl apply -f -
    /usr/local/bin/kubectl delete pods --all -n tastekart --force --grace-period=0
    sleep 5
    /usr/local/bin/kubectl get pods -n tastekart
    """
    
    params = json.dumps({"commands": [script]})
    
    print("Applying updated manifests to K3s on i-0eb458f9795ffd43e...")
    res = subprocess.run([
        'aws', 'ssm', 'send-command',
        '--instance-ids', 'i-0eb458f9795ffd43e',
        '--document-name', 'AWS-RunShellScript',
        '--parameters', params,
        '--region', 'ap-south-1',
        '--output', 'json'
    ], capture_output=True, text=True)

    if res.returncode != 0:
        print("SSM send-command error:\n", res.stderr)
        return

    data = json.loads(res.stdout)
    cmd_id = data['Command']['CommandId']
    print(f"Command ID: {cmd_id}. Waiting for completion...")

    for i in range(25):
        time.sleep(3)
        inv = subprocess.run([
            'aws', 'ssm', 'get-command-invocation',
            '--command-id', cmd_id,
            '--instance-id', 'i-0eb458f9795ffd43e',
            '--region', 'ap-south-1',
            '--output', 'json'
        ], capture_output=True, text=True)

        if inv.returncode == 0:
            out = json.loads(inv.stdout)
            status = out.get('Status')
            if status in ['Success', 'Failed', 'Cancelled', 'TimedOut']:
                print(f"Status: {status}")
                print("--- Output ---")
                print(out.get('StandardOutputContent'))
                if out.get('StandardErrorContent'):
                    print("--- Error ---")
                    print(out.get('StandardErrorContent'))
                break

if __name__ == '__main__':
    deploy()
