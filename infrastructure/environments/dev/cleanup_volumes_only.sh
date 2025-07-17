#!/bin/bash
# Clean up orphaned EBS volumes after terraform destroy
# Run this AFTER you manually run: terraform destroy

echo "🧹 Cleaning up orphaned EBS volumes..."

# Your proven working command
aws ec2 describe-volumes \
  --filters Name=status,Values=available \
           Name=tag-key,Values=kubernetes.io/created-for/pvc/name \
  --query "Volumes[*].VolumeId" --output text | \
xargs -r -n 1 -I {} sh -c 'echo "Deleting volume: {}"; aws ec2 delete-volume --volume-id {}'

echo "✅ Volume cleanup completed!"
