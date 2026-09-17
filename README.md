# Simple Arista playbooks for Ansible Automation Platform

Flat playbooks. Inventory and credentials come from AAP, not this repo.

1. Gather **all** EOS facts
2. Check a few standards against those facts
3. Post a short summary to Microsoft Teams

## AAP workflow

```text
Gather Arista Config
        |
     success
        v
Validate Switch Standards ---- always ----> Notify Microsoft Teams
```

Launch a job template with your AAP inventory and a **Network** credential. Connection settings live in the playbook.

| Job template | Playbook | Credential |
| --- | --- | --- |
| Gather Arista Config | `playbooks/gather_arista_config.yml` | Network |
| Validate Switch Standards | `playbooks/validate_switch_standards.yml` | Network |
| Notify Microsoft Teams | `playbooks/notify_teams.yml` | Microsoft Teams Webhook |

Start with **Gather Arista Config**. It runs `arista.eos.eos_facts` with `gather_subset: all` and `gather_network_resources: all`, then prints `ansible_facts`.

Edit NTP, VLAN, logging, and minimum EOS values in `playbooks/validate_switch_standards.yml` if you use that job.

## Certified collections

| Collection | Used for |
| --- | --- |
| [arista.eos](https://catalog.redhat.com/software/collection/arista/eos) | `eos_facts` |
| [ansible.netcommon](https://catalog.redhat.com/software/collection/ansible/netcommon) | `network_cli` |
| [ansible.controller](https://catalog.redhat.com/software/collection/ansible/controller) | `aap/setup.yml` on the supported EE |

Teams is notified with `ansible.builtin.uri`.

## Execution environment

```bash
export ANSIBLE_GALAXY_SERVER_AUTOMATION_HUB_CERTIFIED_TOKEN=<token>

ansible-builder build \
  -f execution-environment.yml \
  -t arista-playbooks-ee:latest
```

## Controller objects

1. Put switches in an AAP inventory. Attach a **Network** credential (username + password; check **Authorize** for enable mode).
2. Create a **Microsoft Teams Webhook** credential (`aap/setup.yml` creates that type).
3. Optional — create the project, job templates, and workflow:

```bash
export CONTROLLER_HOST=https://aap.example.com
export CONTROLLER_USERNAME=admin
export CONTROLLER_PASSWORD=...

ansible-playbook aap/setup.yml \
  -e aap_project_scm_url=https://github.com/agilleyrh/aap-arista-playbooks.git \
  -e aap_network_credential='Arista EOS' \
  -e aap_teams_credential='Teams Arista Alerts' \
  -e aap_ee_name='Arista EE'
```

Job templates prompt for inventory on launch.

## Local Containerlab (OpenShift Local / CRC)

Containerlab runs **inside the CRC VM** so AAP job pods can SSH to the devices at `192.168.127.2`.

1. Download **cEOSarm-lab** (ARM64) from [Arista software downloads](https://www.arista.com/en/support/software-download) into `~/Downloads`.
2. Deploy the 3-node lab:

```bash
chmod +x containerlab/deploy.sh
./containerlab/deploy.sh
```

3. In AAP, use inventory **Arista Containerlab** and Network credential **Arista cEOS** (`admin` / `admin`). Launch **Gather Arista Config**.

| Host | `ansible_host` | SSH port |
| --- | --- | --- |
| leaf-01 | 192.168.127.2 | 2201 |
| leaf-02 | 192.168.127.2 | 2202 |
| spine-01 | 192.168.127.2 | 2203 |

## License

Apache-2.0
