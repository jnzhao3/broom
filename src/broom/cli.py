import os
import json
import sys
import wandb
from datetime import datetime, timedelta, timezone
from colorama import Fore, Style, init as colorama_init
import argparse

MISSING = "<MISSING>"

# ---------- Color helpers ----------
def color_for_state(state: str) -> str:
    return {
        "finished": Fore.GREEN,
        "running": Fore.YELLOW,
        "crashed": Fore.RED,
        "failed": Fore.RED,
        "killed": Fore.MAGENTA,
        "queued": Fore.BLUE,
        "preempted": Fore.MAGENTA,
    }.get(state or "", Fore.WHITE)

# ---------- Flatten helpers ----------
def _flatten_dict(d, parent_key="", sep="."):
    out = {}
    for k, v in (d or {}).items():
        nk = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            out.update(_flatten_dict(v, nk, sep=sep))
        else:
            out[nk] = v
    return out

def _val_to_str(v):
    if isinstance(v, (dict, list, tuple, set)):
        try:
            return json.dumps(v, sort_keys=True)
        except Exception:
            return str(v)
    return str(v)

# ---------- Core commands ----------
def cmd_fetch(api, entity, project, hours=10, group=None, filters_json=None):
    colorama_init(autoreset=True)

    now = datetime.now(timezone.utc)
    threshold = now - timedelta(hours=hours)

    # Build filters
    filters = {}
    if group:
        filters["group"] = group
    if filters_json:
        try:
            extra = json.loads(filters_json)
            if not isinstance(extra, dict):
                raise ValueError("filters JSON must be an object")
            filters.update(extra)
        except Exception as e:
            print(f"{Fore.RED}Invalid --filters JSON: {e}{Style.RESET_ALL}", file=sys.stderr)
            sys.exit(2)

    runs = api.runs(f"{entity}/{project}", order="-created_at", filters=filters or None)

    rows = []
    running_count = 0

    for run in runs:
        # Stop early once older than threshold (newest first)
        created_at = datetime.fromisoformat(str(run.created_at).replace("Z", "+00:00"))
        if created_at < threshold:
            break

        state = run.state or "unknown"
        if state == "running":
            running_count += 1

        group_val = run.group or ""
        name  = run.name or run.id
        rid   = run.id
        url   = f"{run.url}/logs"

        # elapsed time as H:MM:SS
        total_seconds = int((now - created_at).total_seconds())
        h, rem = divmod(total_seconds, 3600)
        m, s   = divmod(rem, 60)
        started_str = f"{h}:{m:02d}:{s:02d}"

        step = run.summary.get("_step")
        step_str = "0" if step is None else str(step)

        rows.append((str(group_val), str(name), str(rid), str(url), started_str, step_str, str(state)))

    # Dynamic column widths
    def w(col, default):
        return (max((len(r[col]) for r in rows), default=default) + 2) if rows else default
    W_GROUP      = w(0, 5)
    W_NAME       = w(1, 10)
    W_RID        = w(2, 8)
    W_LOGS       = w(3, 12)
    W_STARTED_AT = w(4, 8)
    W_STEP       = w(5, 4)
    W_STATE      = w(6, 6)

    print(f"{Style.BRIGHT}Runs started in the last {hours} hours:{Style.RESET_ALL}")
    if filters:
        print(f"Filters: {filters}")
    print(
        f"{Style.BRIGHT}{'Group':<{W_GROUP}} "
        f"{'Name':<{W_NAME}} "
        f"{'Run ID':<{W_RID}} "
        f"{'Logs URL':<{W_LOGS}} "
        f"{'Time':<{W_STARTED_AT}} "
        f"{'Step':<{W_STEP}} "
        f"{'State':<{W_STATE}}{Style.RESET_ALL}"
    )
    print("-" * (W_GROUP + W_NAME + W_RID + W_LOGS + W_STARTED_AT + W_STEP + W_STATE + 4))

    for group_val, name, rid, url, started_str, step_str, state in rows:
        state_col = color_for_state(state)
        print(
            f"{Style.BRIGHT}{group_val:<{W_GROUP}}{Style.RESET_ALL} "
            f"{name:<{W_NAME}} "
            f"{Fore.YELLOW}{rid:<{W_RID}}{Style.RESET_ALL} "
            f"{Fore.CYAN}{url:<{W_LOGS}}{Style.RESET_ALL} "
            f"{started_str:<{W_STARTED_AT}} "
            f"{step_str:<{W_STEP}} "
            f"{state_col}{state:<{W_STATE}}{Style.RESET_ALL}"
        )

    print(
        f"\n{Style.BRIGHT}Currently running "
        f"{Fore.YELLOW}{sum(1 for r in rows if r[6]=='running')}{Style.RESET_ALL} runs (most recent job first)."
    )

def cmd_config(api, entity, project, run_id):
    colorama_init(autoreset=True)
    run = api.run(f"{entity}/{project}/{run_id}")
    cfg = dict(run.config)

    print(f"{Style.BRIGHT}Configuration for run {run_id}:{Style.RESET_ALL}\n")
    for key, value in cfg.items():
        if isinstance(value, dict):
            print(f"{Fore.MAGENTA}{key}{Style.RESET_ALL}:")
            for subkey, subvalue in value.items():
                print(f"\t{Fore.BLUE}{subkey}{Style.RESET_ALL}: {subvalue}")
        else:
            print(f"{Fore.MAGENTA}{key}{Style.RESET_ALL}: {value}")

def cmd_flag(api, entity, project, run_id, key):
    colorama_init(autoreset=True)
    run = api.run(f"{entity}/{project}/{run_id}")
    cfg = run.config
    if key in cfg:
        print(f"{Style.BRIGHT}{key}{Style.RESET_ALL}: {cfg[key]}")
    else:
        print(f"{Fore.RED}Flag '{key}' not found in run {run_id}.{Style.RESET_ALL}")

def cmd_vary(api, entity, project, group):
    colorama_init(autoreset=True)
    runs = api.runs(f"{entity}/{project}", filters={"group": group}, order="-created_at")

    flattened_runs = []
    all_keys = set()

    for run in runs:
        flat = _flatten_dict(dict(run.config))
        flattened_runs.append(flat)
        all_keys.update(flat.keys())

    if not flattened_runs:
        print(f"{Fore.RED}No runs found for group '{group}'.{Style.RESET_ALL}")
        return

    values_by_key = {}
    varying_keys = []
    for k in sorted(all_keys):
        vals = set()
        for flat in flattened_runs:
            v = flat.get(k, MISSING)
            vals.add(_val_to_str(v) if v is not MISSING else MISSING)
        values_by_key[k] = vals
        if len(vals) > 1:
            varying_keys.append(k)

    if not varying_keys:
        print(f"{Fore.GREEN}No varying parameters found in group '{group}'.{Style.RESET_ALL}")
        return

    print(f"{Style.BRIGHT}Varying parameters in group '{group}':{Style.RESET_ALL}")
    for k in varying_keys:
        vals = sorted(values_by_key[k], key=str)
        print(f"{Fore.MAGENTA}{k}{Style.RESET_ALL}: {', '.join(vals)}")

def cmd_delete(api, entity, project, run_id):
    colorama_init(autoreset=True)
    run = api.run(f"{entity}/{project}/{run_id}")
    print(f"Deleting run {run_id}...")
    run.delete()
    print(f"{Fore.GREEN}Run {run_id} deleted successfully.{Style.RESET_ALL}")

# ---------- CLI ----------
def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    parser = argparse.ArgumentParser(prog="wbpeek", description="Peek W&B runs.")
    parser.add_argument("--entity", default=os.getenv("WANDB_ENTITY"), help="W&B entity (default: $WANDB_ENTITY)")
    parser.add_argument("--project", default=os.getenv("WANDB_PROJECT"), help="W&B project (default: $WANDB_PROJECT)")

    sub = parser.add_subparsers(dest="cmd", required=True)

    p_fetch = sub.add_parser("fetch", help="List recent runs in a table")
    p_fetch.add_argument("--hours", "-H", type=int, default=10)
    p_fetch.add_argument("--group", help="Filter by W&B run group")
    p_fetch.add_argument("--filters", help="Extra W&B filters as JSON")
    p_fetch.set_defaults(func=lambda args, api: cmd_fetch(api, args.entity, args.project, args.hours, args.group, args.filters))

    p_cfg = sub.add_parser("config", help="Show config for a run")
    p_cfg.add_argument("run_id")
    p_cfg.set_defaults(func=lambda args, api: cmd_config(api, args.entity, args.project, args.run_id))

    p_flag = sub.add_parser("flag", help="Show a single config key for a run")
    p_flag.add_argument("run_id")
    p_flag.add_argument("key")
    p_flag.set_defaults(func=lambda args, api: cmd_flag(api, args.entity, args.project, args.run_id, args.key))

    p_vary = sub.add_parser("vary", help="Show which config params vary within a group")
    p_vary.add_argument("group")
    p_vary.set_defaults(func=lambda args, api: cmd_vary(api, args.entity, args.project, args.group))

    p_del = sub.add_parser("delete", help="Delete a run (DANGEROUS)")
    p_del.add_argument("run_id")
    p_del.set_defaults(func=lambda args, api: cmd_delete(api, args.entity, args.project, args.run_id))

    args = parser.parse_args(argv)

    if not args.entity or not args.project:
        print(f"{Fore.RED}Please set --entity/--project or WANDB_ENTITY/WANDB_PROJECT env vars.{Style.RESET_ALL}", file=sys.stderr)
        sys.exit(2)

    api = wandb.Api()
    args.func(args, api)

if __name__ == "__main__":
    main()
