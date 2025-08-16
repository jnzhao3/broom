# Broom

Useful command line commands for running hyperparmeter sweeps with Weights & Biases. Heavily tailored to my own style of running sweeps.

## How I Run Sweeps

Each run posseses a run group, which populates `run.group` (as described by the `wandb` API). I also like to have the Logs URL readily available. It's how I check the experiment output for errors or debugging information.

## Commands

- `broom fetch --hours 24` - Fetches all runs from the last 24 hours.
- `broom config <run_id>` - Shows the config for a run.
- `broom vary <group>` - Shows which config params vary within a group.
- `broom delete <run_id>` - Deletes a run (DANGEROUS).

I'll document these commands in more detail later.

Example usage:

```bash
broom fetch --hours 6

Runs started in the last 6 hours:
Group          Name                                                               Run ID     Logs URL                                           Time      Step     State    
--------------------------------------------------------------------------------------------------------------------------------------------------------------------------
debugging      sd001_8751906860336_20250815_155120.892                            cjvo7vgl   https://wandb.ai/entity_name/group_name/runs/cjvo7vgl/logs   3:51:11   0        failed   
train_fql9_2   sd001_1401546250313_s_27409045.0.27363298.28.20250815_135811.892   fyaabbg3   https://wandb.ai/entity_name/group_name/runs/fyaabbg3/logs   5:44:24   745000   running 
```

In place of `broom`, `bm` also works.

## Installation

```
git clone git@github.com:entity_name/broom.git
cd broom
pip install -e .

export WANDB_PROJECT=project_name
export WANDB_ENTITY=entity_name
```
To make these environment variables persistent, you can add them to your `.bashrc` or `.bash_profile`:
```
echo 'export WANDB_PROJECT=project_name' >> ~/.bashrc
echo 'export WANDB_ENTITY=entity_name' >> ~/.bashrc
source ~/.bashrc
```

🧹