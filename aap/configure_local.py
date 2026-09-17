#!/usr/bin/env python3
"""Create AAP project, containerlab inventory, Network credential, and job templates."""
from __future__ import annotations

import base64
import json
import os
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request

URL = os.environ.get("CONTROLLER_HOST", "").rstrip("/")
USER = os.environ.get("CONTROLLER_USERNAME", "admin")
PASSWORD = os.environ.get("CONTROLLER_PASSWORD", "")
VERIFY = os.environ.get("CONTROLLER_VERIFY_SSL", "false").lower() in {"1", "true", "yes"}
ORG_NAME = os.environ.get("AAP_ORGANIZATION", "Default")
PROJECT_NAME = "Arista Switch Playbooks"
PROJECT_URL = os.environ.get(
    "AAP_PROJECT_SCM_URL", "https://github.com/agilleyrh/aap-arista-playbooks.git"
)
INVENTORY_NAME = "Arista Containerlab"
CRED_NAME = "Arista cEOS"
EE_NAME = os.environ.get("AAP_EE_NAME", "Default execution environment")
HOSTS = [("leaf-01", 2201), ("leaf-02", 2202), ("spine-01", 2203)]
CTX = ssl.create_default_context() if VERIFY else ssl._create_unverified_context()


def request(method: str, path: str, payload: dict | None = None):
    data = None
    headers = {
        "Authorization": "Basic " + base64.b64encode(f"{USER}:{PASSWORD}".encode()).decode(),
        "Content-Type": "application/json",
    }
    if payload is not None:
        data = json.dumps(payload).encode()
    req = urllib.request.Request(URL + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, context=CTX) as resp:
            body = resp.read()
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        err = exc.read().decode()
        raise SystemExit(f"{method} {path} -> {exc.code}: {err}") from exc


def get(path: str):
    return request("GET", path)


def get_by_name(collection_path: str, name: str):
    query = collection_path + "?name=" + urllib.parse.quote(name)
    for item in get(query).get("results", []):
        if item.get("name") == name:
            return item
    return None


def upsert(collection_path: str, name: str, payload: dict):
    existing = get_by_name(collection_path, name)
    if existing:
        body = request("PATCH", f"{collection_path}{existing['id']}/", payload)
        print(f"updated {name} ({existing['id']})")
        return body
    body = request("POST", collection_path, payload)
    print(f"created {name} ({body.get('id')})")
    return body


def main():
    if not URL or not PASSWORD:
        raise SystemExit("Set CONTROLLER_HOST and CONTROLLER_PASSWORD")

    org = get_by_name("/api/controller/v2/organizations/", ORG_NAME)
    ee = get_by_name("/api/controller/v2/execution_environments/", EE_NAME)
    net_type = get_by_name("/api/controller/v2/credential_types/", "Network")
    if not org or not ee or not net_type:
        raise SystemExit("Missing organization, execution environment, or Network credential type")

    cred = upsert(
        "/api/controller/v2/credentials/",
        CRED_NAME,
        {
            "name": CRED_NAME,
            "description": "Default cEOS-lab admin user",
            "organization": org["id"],
            "credential_type": net_type["id"],
            "inputs": {
                "username": "admin",
                "password": "admin",
                "authorize": True,
                "authorize_password": "admin",
            },
        },
    )

    project = upsert(
        "/api/controller/v2/projects/",
        PROJECT_NAME,
        {
            "name": PROJECT_NAME,
            "description": "Flat Arista EOS playbooks",
            "organization": org["id"],
            "scm_type": "git",
            "scm_url": PROJECT_URL,
            "scm_branch": "main",
            "scm_update_on_launch": True,
        },
    )
    print("syncing project...")
    request("POST", f"/api/controller/v2/projects/{project['id']}/update/", {})
    for _ in range(60):
        project = get(f"/api/controller/v2/projects/{project['id']}/")
        print("  project status:", project.get("status"))
        if project.get("status") in {"successful", "failed", "error"}:
            break
        time.sleep(5)
    if project.get("status") != "successful":
        raise SystemExit(f"project sync ended with status {project.get('status')}")

    inv = upsert(
        "/api/controller/v2/inventories/",
        INVENTORY_NAME,
        {
            "name": INVENTORY_NAME,
            "description": "Local containerlab cEOS nodes on the CRC VM",
            "organization": org["id"],
            "variables": json.dumps(
                {
                    "ansible_connection": "ansible.netcommon.network_cli",
                    "ansible_network_os": "arista.eos.eos",
                    "ansible_network_cli_ssh_type": "paramiko",
                    "ansible_paramiko_look_for_keys": False,
                    "ansible_host_key_checking": False,
                    "ansible_become": True,
                    "ansible_become_method": "enable",
                }
            ),
        },
    )

    group = None
    for item in get(f"/api/controller/v2/inventories/{inv['id']}/groups/").get("results", []):
        if item["name"] == "arista_switches":
            group = item
            break
    if not group:
        group = request(
            "POST",
            "/api/controller/v2/groups/",
            {"name": "arista_switches", "inventory": inv["id"]},
        )
        print("created group arista_switches")

    existing_hosts = {
        h["name"]: h
        for h in get(f"/api/controller/v2/inventories/{inv['id']}/hosts/").get("results", [])
    }
    for hostname, port in HOSTS:
        payload = {
            "name": hostname,
            "inventory": inv["id"],
            "enabled": True,
            "variables": json.dumps({"ansible_host": "192.168.127.2", "ansible_port": port}),
        }
        if hostname in existing_hosts:
            host = request("PATCH", f"/api/controller/v2/hosts/{existing_hosts[hostname]['id']}/", payload)
            print(f"updated host {hostname}")
        else:
            host = request("POST", "/api/controller/v2/hosts/", payload)
            print(f"created host {hostname}")
        request("POST", f"/api/controller/v2/groups/{group['id']}/hosts/", {"id": host["id"]})

    for jt_name, playbook in [
        ("Gather Arista Config", "playbooks/gather_arista_config.yml"),
        ("Validate Switch Standards", "playbooks/validate_switch_standards.yml"),
    ]:
        payload = {
            "name": jt_name,
            "job_type": "run",
            "organization": org["id"],
            "inventory": inv["id"],
            "project": project["id"],
            "playbook": playbook,
            "execution_environment": ee["id"],
            "ask_inventory_on_launch": False,
            "ask_credential_on_launch": False,
            "verbosity": 1,
            "use_fact_cache": False,
        }
        existing = get_by_name("/api/controller/v2/job_templates/", jt_name)
        if existing:
            jt = request("PATCH", f"/api/controller/v2/job_templates/{existing['id']}/", payload)
            print(f"updated job template {jt_name}")
        else:
            jt = request("POST", "/api/controller/v2/job_templates/", payload)
            print(f"created job template {jt_name}")
        request("POST", f"/api/controller/v2/job_templates/{jt['id']}/credentials/", {"id": cred["id"]})

    print("done")
    print(f"UI: {URL}")
    print(f"Inventory: {INVENTORY_NAME}")
    print(f"Credential: {CRED_NAME}")
    print("Launch: Gather Arista Config")


if __name__ == "__main__":
    main()
