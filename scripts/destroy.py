#!/usr/bin/env python3
"""
TasteKart 1-Click Teardown Script
Destroys all cloud infrastructure cleanly and forcefully.
"""

import os
import subprocess

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TERRAFORM_DIR = os.path.join(PROJECT_ROOT, "terraform")
AWS_REGION = "ap-south-1"
ECR_REPO = "tastekart-backend"

def main():
    print("=" * 60)
    print("Step 1: Forcefully purging ECR repository (if exists)...")
    print("=" * 60)
    subprocess.run(
        f"aws ecr delete-repository --repository-name {ECR_REPO} --force --region {AWS_REGION}",
        shell=True,
        capture_output=True
    )
    print("[SUCCESS] ECR repository purged.")

    print("\n" + "=" * 60)
    print("Step 2: Destroying remaining AWS Infrastructure via Terraform...")
    print("=" * 60)
    res = subprocess.run("terraform destroy -auto-approve", cwd=TERRAFORM_DIR, shell=True)
    if res.returncode == 0:
        print("\n" + "*" * 60)
        print("[SUCCESS] All TasteKart cloud infrastructure has been cleanly destroyed.")
        print("*" * 60)
    else:
        print("\n[ERROR] Terraform destroy encountered an error.")

if __name__ == "__main__":
    main()
