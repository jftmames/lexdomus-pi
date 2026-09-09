# Baseline frontend advisory inventory

Observed 2026-09-09 against the reproduced baseline lock. 38 advisory entries: 34 Next and 4 PostCSS; 3 Critical, 14 High, 17 Moderate, 4 Low. These are scanner inventory matches, not confirmed live exposures. npm group counts are 1 Critical package (Next) and 1 High package (PostCSS).

Paths: N = node_modules/next@14.1.4; P = node_modules/postcss@8.4.35 (direct dev dependency) and node_modules/next/node_modules/postcss@8.4.31. All P advisory rows affect both installed copies.

CVE column is the GitHub Advisory API cve_id field. Where absent, CVEs mentioned in the description are separately labeled as related/upstream; they are not newly assigned IDs for that GHSA. npm Moderate corresponds to GitHub Medium.

| Package/path | GHSA | CVE field / related upstream CVEs | npm severity | Affected range in scanner |
| --- | --- | --- | --- | --- |
| next / N | [GHSA-gp8f-8m3g-qvj9](https://github.com/advisories/GHSA-gp8f-8m3g-qvj9) | CVE-2024-46982 | high | `>=14.0.0 <14.2.10` |
| next / N | [GHSA-g77x-44xx-532m](https://github.com/advisories/GHSA-g77x-44xx-532m) | CVE-2024-47831 | moderate | `>=10.0.0 <14.2.7` |
| next / N | [GHSA-7m27-7ghc-44w9](https://github.com/advisories/GHSA-7m27-7ghc-44w9) | CVE-2024-56332 | moderate | `>=14.0.0 <14.2.21` |
| next / N | [GHSA-3h52-269p-cp9r](https://github.com/advisories/GHSA-3h52-269p-cp9r) | CVE-2025-48068 | low | `>=13.0 <14.2.30` |
| next / N | [GHSA-g5qg-72qw-gw5v](https://github.com/advisories/GHSA-g5qg-72qw-gw5v) | CVE-2025-57752 | moderate | `>=0.9.9 <14.2.31` |
| next / N | [GHSA-7gfc-8cq8-jh5f](https://github.com/advisories/GHSA-7gfc-8cq8-jh5f) | CVE-2024-51479 | high | `>=9.5.5 <14.2.15` |
| next / N | [GHSA-4342-x723-ch2f](https://github.com/advisories/GHSA-4342-x723-ch2f) | CVE-2025-57822 | moderate | `>=0.9.9 <14.2.32` |
| next / N | [GHSA-xv57-4mr9-wg8v](https://github.com/advisories/GHSA-xv57-4mr9-wg8v) | CVE-2025-55173 | moderate | `>=0.9.9 <14.2.31` |
| next / N | [GHSA-qpjv-v59x-3qc4](https://github.com/advisories/GHSA-qpjv-v59x-3qc4) | CVE-2025-32421 | low | `>=0.9.9 <14.2.24` |
| next / N | [GHSA-mwv6-3258-q52c](https://github.com/advisories/GHSA-mwv6-3258-q52c) | No assigned CVE; related/upstream: CVE-2025-55184 | high | `>=13.3.0 <14.2.34` |
| next / N | [GHSA-5j59-xgg2-r9c4](https://github.com/advisories/GHSA-5j59-xgg2-r9c4) | No assigned CVE; related/upstream: CVE-2025-55184, CVE-2025-67779 | high | `>=13.3.1-canary.0 <14.2.35` |
| next / N | [GHSA-9g9p-9gw9-jx7f](https://github.com/advisories/GHSA-9g9p-9gw9-jx7f) | CVE-2025-59471 | moderate | `>=10.0.0 <15.5.10` |
| next / N | [GHSA-h25m-26qc-wcjf](https://github.com/advisories/GHSA-h25m-26qc-wcjf) | No assigned CVE; related/upstream: CVE-2026-23864 | high | `>=13.0.0 <15.0.8` |
| next / N | [GHSA-f82v-jwr5-mffw](https://github.com/advisories/GHSA-f82v-jwr5-mffw) | CVE-2025-29927 | critical | `>=14.0.0 <14.2.25` |
| next / N | [GHSA-ggv3-7p47-pfv8](https://github.com/advisories/GHSA-ggv3-7p47-pfv8) | CVE-2026-29057 | moderate | `>=9.5.0 <15.5.13` |
| next / N | [GHSA-3x4c-7xq6-9pq8](https://github.com/advisories/GHSA-3x4c-7xq6-9pq8) | CVE-2026-27980 | moderate | `>=10.0.0 <15.5.14` |
| next / N | [GHSA-q4gf-8mx6-v5v3](https://github.com/advisories/GHSA-q4gf-8mx6-v5v3) | No assigned CVE; related/upstream: CVE-2026-23869 | high | `>=13.0.0 <15.5.15` |
| next / N | [GHSA-8h8q-6873-q5fj](https://github.com/advisories/GHSA-8h8q-6873-q5fj) | No assigned CVE; related/upstream: CVE-2026-23870 | high | `>=13.0.0 <15.5.16` |
| next / N | [GHSA-3g8h-86w9-wvmq](https://github.com/advisories/GHSA-3g8h-86w9-wvmq) | CVE-2026-44572 | low | `>=12.2.0 <15.5.16` |
| next / N | [GHSA-ffhc-5mcf-pf4q](https://github.com/advisories/GHSA-ffhc-5mcf-pf4q) | CVE-2026-44581 | moderate | `>=13.4.0 <15.5.16` |
| next / N | [GHSA-vfv6-92ff-j949](https://github.com/advisories/GHSA-vfv6-92ff-j949) | CVE-2026-44582 | low | `>=13.4.6 <15.5.16` |
| next / N | [GHSA-gx5p-jg67-6x7h](https://github.com/advisories/GHSA-gx5p-jg67-6x7h) | CVE-2026-44580 | moderate | `>=13.0.0 <15.5.16` |
| next / N | [GHSA-h64f-5h5j-jqjh](https://github.com/advisories/GHSA-h64f-5h5j-jqjh) | CVE-2026-44577 | moderate | `>=10.0.0 <15.5.16` |
| next / N | [GHSA-c4j6-fc7j-m34r](https://github.com/advisories/GHSA-c4j6-fc7j-m34r) | CVE-2026-44578 | high | `>=13.4.13 <15.5.16` |
| next / N | [GHSA-36qx-fr4f-26g5](https://github.com/advisories/GHSA-36qx-fr4f-26g5) | CVE-2026-44573 | high | `>=12.2.0 <15.5.16` |
| next / N | [GHSA-m99w-x7hq-7vfj](https://github.com/advisories/GHSA-m99w-x7hq-7vfj) | CVE-2026-64641 | high | `>=13.0.0 <15.5.21` |
| next / N | [GHSA-89xv-2m56-2m9x](https://github.com/advisories/GHSA-89xv-2m56-2m9x) | CVE-2026-64649 | high | `>=14.1.1 <15.5.21` |
| next / N | [GHSA-68g3-v927-f742](https://github.com/advisories/GHSA-68g3-v927-f742) | CVE-2026-64648 | moderate | `>=13.0.0 <15.5.21` |
| next / N | [GHSA-4633-3j49-mh5q](https://github.com/advisories/GHSA-4633-3j49-mh5q) | CVE-2026-64647 | moderate | `>=13.0.0 <15.5.21` |
| next / N | [GHSA-4c39-4ccg-62r3](https://github.com/advisories/GHSA-4c39-4ccg-62r3) | CVE-2026-64646 | moderate | `>=13.0.0 <15.5.21` |
| next / N | [GHSA-p9j2-gv94-2wf4](https://github.com/advisories/GHSA-p9j2-gv94-2wf4) | CVE-2026-64645 | high | `>=12.0.0 <15.5.21` |
| next / N | [GHSA-955p-x3mx-jcvp](https://github.com/advisories/GHSA-955p-x3mx-jcvp) | CVE-2026-64643 | moderate | `>=13.0.0 <15.5.21` |
| next / N | [GHSA-p293-qw3h-jr36](https://github.com/advisories/GHSA-p293-qw3h-jr36) | CVE-2026-75604 | critical | `>=13.4.0 <15.5.24` |
| next / N | [GHSA-2xp9-vwfh-vxw4](https://github.com/advisories/GHSA-2xp9-vwfh-vxw4) | No assigned CVE | critical | `>=10.0.0 <15.5.24` |
| postcss / P | [GHSA-qx2v-qp2m-jg93](https://github.com/advisories/GHSA-qx2v-qp2m-jg93) | CVE-2026-41305 | moderate | `<8.5.10` |
| postcss / P | [GHSA-6g55-p6wh-862q](https://github.com/advisories/GHSA-6g55-p6wh-862q) | CVE-2026-45623 | high | `<=8.5.11` |
| postcss / P | [GHSA-fxqj-rqcc-2cmp](https://github.com/advisories/GHSA-fxqj-rqcc-2cmp) | CVE-2026-69153 | moderate | `<=8.5.22` |
| postcss / P | [GHSA-r28c-9q8g-f849](https://github.com/advisories/GHSA-r28c-9q8g-f849) | CVE-2026-73646 | high | `<=8.5.17` |
