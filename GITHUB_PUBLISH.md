# Publishing the frozen reproducibility repository to GitHub

The repository is prepared and the original and additional numerical outputs are bundled. The current connected GitHub account (`Todai-ops`) has no accessible repositories or GitHub App installations; publishing requires a target repository and app access (or a manual push using Git).

1. Log in to GitHub and create a new **empty repository**, suggested name `sapporo-bus-journey-protection` under your chosen account or organization. Decide whether to make it public (reviewers need access) or temporarily private (then invite reviewers). Do **not** auto-create a README, .gitignore or license because those are supplied here.
2. Extract the supplied ZIP so `README.md`, `reproduce.py`, `gtfs_sources/`, `revised/`, `sapporo_reconstruction/`, `revision_analysis/`, `paper/` and `supplement/` sit at the repository root. Do **not** upload the ZIP as a single GitHub file: GitHub won't unpack it.
3. From the extracted folder, run:

```sh
git init
git add .
git commit -m "Archive reproducible Sapporo journey-protection experiments"
git branch -M main
git remote add origin https://github.com/OWNER/sapporo-bus-journey-protection.git
git push -u origin main
```

Substitute `OWNER` with your actual GitHub username or organization. When pushing from a terminal, authenticate using your configured GitHub credentials, SSH key or GitHub credential manager; do not paste credentials into files or chat.

4. On GitHub, open **Actions → Reproducibility checks** to confirm the quick checks have passed. For a complete solver replay, choose **Run workflow** and check **full_replay**; this runs the original grid and seven sensitivity scenarios.
5. Optionally tag an immutable release and connect Zenodo/OSF for a citable archival DOI. Add the URL/DOI to the manuscript supplement and response letter only **after the repository is actually accessible**.
6. Choose an appropriate licence for original research code before public release if reuse is intended. The source GTFS snapshots have separate upstream Creative Commons Attribution conditions documented in `LICENSE_AND_ATTRIBUTION.md`.

**Important:** The original 830-call ledger, original output files and code are all included; do not mix the earlier 848-query exploratory pilot into this 832-query final study.
