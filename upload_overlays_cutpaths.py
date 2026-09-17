"""
Lists overlay and cutpath PDFs currently in S3.
Run from PowerShell:  python upload_overlays_cutpaths.py
"""

import boto3

ACCESS_KEY = "AKIAWJINAHOM3TNMLR7U"
SECRET_KEY = input("Paste your AWS secret access key: ").strip()
REGION     = "us-east-1"
BUCKET     = "quickproof-database-2"

s3 = boto3.client("s3",
    aws_access_key_id=ACCESS_KEY,
    aws_secret_access_key=SECRET_KEY,
    region_name=REGION)

def list_prefix(prefix):
    paginator = s3.get_paginator("list_objects_v2")
    names = []
    for page in paginator.paginate(Bucket=BUCKET, Prefix=prefix):
        for obj in page.get("Contents", []):
            name = obj["Key"][len(prefix):]
            if name.lower().endswith(".pdf") and name:
                names.append(name)
    return sorted(names)

print("=== Overlays-PDF/ ===")
for f in list_prefix("Overlays-PDF/"):
    print(" ", f)

print("\n=== Cutpaths-PDF/ ===")
for f in list_prefix("Cutpaths-PDF/"):
    print(" ", f)
