import json
import subprocess
import time

def test_health():
    cmd = "curl -i http://localhost:30001/api/health"
    params = json.dumps({"commands": [cmd]})
    
    res = subprocess.run([
        'aws', 'ssm', 'send-command',
        '--instance-ids', 'i-0eb458f9795ffd43e',
        '--document-name', 'AWS-RunShellScript',
        '--parameters', params,
        '--region', 'ap-south-1',
        '--output', 'json'
    ], capture_output=True, text=True)
    
    cmd_id = json.loads(res.stdout)['Command']['CommandId']
    time.sleep(3)
    inv = subprocess.run([
        'aws', 'ssm', 'get-command-invocation',
        '--command-id', cmd_id,
        '--instance-id', 'i-0eb458f9795ffd43e',
        '--region', 'ap-south-1',
        '--output', 'json'
    ], capture_output=True, text=True)
    out = json.loads(inv.stdout)
    print("Health Check Response:\n", out.get('StandardOutputContent'))

if __name__ == '__main__':
    test_health()
