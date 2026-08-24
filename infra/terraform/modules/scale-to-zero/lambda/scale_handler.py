"""Scale NutriApp's dev EKS node groups and RDS instance for cost control.

Deployed as an AWS Lambda by infra/terraform/modules/scale-to-zero. Two
EventBridge Scheduler rules invoke this function with a different
`action` payload:
  - {"action": "scale_down"} — outside working hours: node group
    desired/min size -> 0, RDS instance stopped.
  - {"action": "scale_up"}   — start of working hours: node group sizes
    restored to their baseline, RDS instance started.

Idempotent by design: safe to invoke scale_down when already scaled
down, and vice versa (the AWS APIs used here no-op or return a
recognizable error in that case, both handled below).

See docs/cost-management.md section 1.
"""
from __future__ import annotations

import json
import logging
import os

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

eks_client = boto3.client("eks")
rds_client = boto3.client("rds")

CLUSTER_NAME = os.environ["CLUSTER_NAME"]
RDS_INSTANCE_ID = os.environ["RDS_INSTANCE_ID"]
# JSON map: {"<node-group-name>": {"desired": int, "min": int, "max": int}}
NODE_GROUP_BASELINES = json.loads(os.environ["NODE_GROUP_BASELINES"])


def _scale_node_group(node_group_name: str, desired: int, min_size: int, max_size: int) -> None:
    try:
        eks_client.update_nodegroup_config(
            clusterName=CLUSTER_NAME,
            nodegroupName=node_group_name,
            scalingConfig={
                "minSize": min_size,
                "maxSize": max(max_size, 1),  # AWS requires maxSize >= 1 even when desired=0
                "desiredSize": desired,
            },
        )
        logger.info(
            "Requested scaling for %s/%s: desired=%s min=%s max=%s",
            CLUSTER_NAME, node_group_name, desired, min_size, max_size,
        )
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "")
        if code == "ResourceInUseException":
            logger.warning(
                "Node group %s already has an update in progress, skipping this cycle.",
                node_group_name,
            )
            return
        raise


def _stop_rds() -> None:
    try:
        rds_client.stop_db_instance(DBInstanceIdentifier=RDS_INSTANCE_ID)
        logger.info("Stop requested for RDS instance %s", RDS_INSTANCE_ID)
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "")
        if code == "InvalidDBInstanceState":
            logger.info(
                "RDS instance %s already stopped/stopping, nothing to do.", RDS_INSTANCE_ID
            )
            return
        raise


def _start_rds() -> None:
    try:
        rds_client.start_db_instance(DBInstanceIdentifier=RDS_INSTANCE_ID)
        logger.info("Start requested for RDS instance %s", RDS_INSTANCE_ID)
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "")
        if code == "InvalidDBInstanceState":
            logger.info(
                "RDS instance %s already available/starting, nothing to do.", RDS_INSTANCE_ID
            )
            return
        raise


def handler(event: dict, _context) -> dict:
    action = event.get("action")
    if action not in ("scale_down", "scale_up"):
        raise ValueError(f"Unknown or missing 'action' in event payload: {event!r}")

    if action == "scale_down":
        for node_group_name in NODE_GROUP_BASELINES:
            _scale_node_group(node_group_name, desired=0, min_size=0, max_size=1)
        _stop_rds()
    else:
        for node_group_name, baseline in NODE_GROUP_BASELINES.items():
            _scale_node_group(
                node_group_name,
                desired=baseline["desired"],
                min_size=baseline["min"],
                max_size=baseline["max"],
            )
        _start_rds()

    return {"action": action, "status": "requested"}
