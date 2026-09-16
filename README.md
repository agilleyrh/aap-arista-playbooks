# Simple Arista playbooks for Ansible Automation Platform

Traditional Ansible playbooks (no roles) that run as AAP job templates and a
workflow. Collections come from **Red Hat Automation Hub certified content**.

This is the simpler companion to
[aap-arista-compliance](https://github.com/agilleyrh/aap-arista-compliance).

1. Gather current configuration from Arista EOS switches
2. Check switch standards and expected bare-metal attachments
3. Post the current config summary and pass/fail results to Microsoft Teams

## AAP workflow

```text
Gather Arista Config
        |
     success
        v
Validate Switch Standards ---- always ----> Notify Microsoft Teams
```

Launch **Arista Baremetal Compliance**. Workflow `set_stats` artifacts pass
config and compliance results into the Teams job.

| Job template | Playbook | Credential |
| --- | --- | --- |
| Gather Arista Config | `playbooks/gather_arista_config.yml` | Network |
| Validate Switch Standards | `playbooks/validate_switch_standards.yml` | Network |
| Notify Microsoft Teams | `playbooks/notify_teams.yml` | Microsoft Teams Webhook |

## Certified collections

| Collection | Catalog | Used for |
| --- | --- | --- |
| [arista.eos](https://catalog.redhat.com/software/collection/arista/eos) | Certified | `eos_facts`, `eos_command` |
| [ansible.netcommon](https://catalog.redhat.com/software/collection/ansible/netcommon) | Certified | `network_cli` |
| [ansible.utils](https://catalog.redhat.com/software/collection/ansible/utils) | Certified | `json_query` |
| [ansible.controller](https://catalog.redhat.com/software/collection/ansible/controller) | Certified | `aap/setup.yml` on the supported EE |

Teams is notified with `ansible.builtin.uri`. There is no certified Teams collection.

## Layout

```text
playbooks/     three job-template playbooks, tasks inline
templates/     Teams Adaptive Card
vars/          switch standards
inventory/     example hosts and expected_servers
aap/setup.yml  creates the AAP project, JTs, and workflow
```

## Execution environment

```bash
export ANSIBLE_GALAXY_SERVER_AUTOMATION_HUB_CERTIFIED_TOKEN=<token>

ansible-builder build \
  -f execution-environment.yml \
  -t arista-playbooks-ee:latest
```

Push the image to the registry AAP uses, then set `aap_ee_name` to that EE.

## Controller objects

1. Create a **Network** credential for EOS.
2. Create a **Microsoft Teams Webhook** credential (`aap/setup.yml` creates the type).
3. Add switches to group `arista_switches` with `expected_servers` host vars.
4. Run `aap/setup.yml` with a Controller credential:

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

## License

Apache-2.0
