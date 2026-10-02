# Feed review for every release

Before publishing each release, review all requested leagues, including feeds that are still pending. A successful installer build is not proof of data coverage.

Record the review date, version, source tested, upcoming/live/final examples, and remaining gaps in the GitHub release notes. Test an upcoming game within seven days and a recent result; when a live game is available, also check its status and score. Recheck failed feeds and retained results for duplicates and stale live status. If a new reliable source supplies only results, add that coverage without waiting for live tracking.

Priority backlog:
- NPB: Hanshin Tigers and Hiroshima Toyo Carp — source research remains open; no connected feed.
- NFL / college football: ESPN failures and fallback scores, especially Seattle, Cleveland, Washington, Arkansas and Central Washington.
- Soccer: Sounders, Frontale, and US/Japan senior men, including cup/friendly results and shootouts.
- Cricket: Seattle Orcas — pending.
- AFL: Geelong Cats — pending.
- Rugby: Seattle Seawolves plus US/Japan/Ireland national teams; national feeds pending.
- National baseball: US/Japan — pending.
- MLB / NHL / F1: retain working coverage and verify regressions; F1 remains schedule-only.

NPB research on 2026-10-02: official NPB pages publish results; TheSportsDB documents a results API. Neither establishes tested, complete NPB coverage for this app. Do not label NPB supported until retrieval, team matching and result parsing have been verified. Sources: https://npb.jp/ and https://www.thesportsdb.com/documentation

Release note template:
- Feed review date:
- Sources and example matches tested:
- Newly supported sports/teams:
- Pending sources / failures:
- Checks not possible this release:
