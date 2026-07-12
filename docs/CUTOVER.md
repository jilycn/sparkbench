# SparkBench v2 cutover runbook

Do not run this procedure without explicit operator approval.

All five conditions must be true:

1. No SparkBench lock is held.
2. No active benchmark process exists.
3. The full v2 test suite and snapshot-integrity tests are green.
4. A v2 partial smoke run completed successfully from `~/sparkbench-v2`.
5. One full v2 run completed successfully from `~/sparkbench-v2`.

After approval and only after all five conditions:

```bash
pgrep -af 'sparkbench|agent_build_r2|logic_eval|qa_eval|conc_eval' && exit 1
flock -n ~/bench/sparkbench/.lock true || exit 1
cd ~/sparkbench-v2 && venv/bin/python -m pytest -q
rsync -a --delete --exclude venv --exclude .git ~/sparkbench-v2/ ~/sparkbench.new/
ln -sfn ~/sparkbench/venv ~/sparkbench.new/venv
mv ~/sparkbench ~/sparkbench.v1-backup
mv ~/sparkbench.new ~/sparkbench
```

Keep `~/sparkbench.v1-backup` until a post-cutover full run and SparkOps integration verification pass.
