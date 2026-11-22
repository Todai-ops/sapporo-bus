# Licensing and attribution

## Third-party GTFS snapshots

The three `gtfs_sources/*.zip` archives are preserved **unchanged** to make the experiment reproducible. They originate from the Hokkaido Open Data Platform (HODA), whose dataset pages state **Creative Commons Attribution**. The GTFS `feed_info.txt` identifies the original publishers; the precise official distribution links, archived SHA-256 hashes, and selected service dates are documented in `sapporo_reconstruction/data/provenance.json`. The snapshots remain subject to their original licences and source acknowledgements, not any license for this repository's research code.

- Bankei: https://ckan.hoda.jp/dataset/gtfs-data/resource/889906b8-eb1a-41c3-a7b3-75cd69aa891f
- Jotetsu: https://ckan.hoda.jp/dataset/gtfs-data/resource/fef98fef-6fe2-472f-bde3-9d4f0a509a4a
- Sapporo Subway: https://ckan.hoda.jp/dataset/gtfs-data/resource/3efff7e5-b604-4850-8888-38f0e60bb238
- Parent catalogue: https://ckan.hoda.jp/dataset/gtfs-data

The Jotetsu November 2026 feed lists **Jorudan Co., Ltd. (ジョルダン株式会社)** as the feed publisher. The bus operator name is Jotetsu (じょうてつ). The 2026-11-09 service date describes the selected Monday service **within the archived feed**; it is not an independent publication date of the operator's public PDF timetables. See `paper/references.bib` (entry `jotetsuGTFS`).

## Original code, prose and derived data

The repository's research code, paper and research-generated outputs are supplied for scientific inspection and reproducibility. **No new open-source licence for the author's original material has yet been chosen.** The author should select a suitable licence (for example, MIT for code) before public release if they intend to permit unrestricted reuse. A license for original material must not be taken to supersede the upstream GTFS terms.

## Research disclaimer

The 2026 bus and 2020 subway source feeds were combined into a stylized illustration. The reported outputs are not real passenger journey counts or a validated bus operating plan. Route eligibility, operator transfer equivalence, and fleet caps are study assumptions.
