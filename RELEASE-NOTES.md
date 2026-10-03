# SportsBug v0.2.1

Adds free NPB schedules and published final scores for all 12 clubs, selectable under Baseball → NPB. Existing Hanshin and Hiroshima favorites are retained. Finals use the existing gold treatment and W/L/T result column when one team in the match is followed.

Upcoming games follow the seven-day and one-per-team rules. During an unconfirmed match, the game remains visible for up to eight hours and the next fixture is suppressed. Once a final arrives, the next eligible fixture can appear. Cancelled games are omitted.

Data: Nippon Baseball Data Repository, https://github.com/armstjc/Nippon-Baseball-Data-Repository. Live update frequency is unverified; this release supports schedules and published results without claiming live tracking.

Validation: current 2026 CSV downloaded and parsed; October 1 Hanshin 2–2 Yomiuri, Hiroshima 5–1 Chunichi, and October 3 Hiroshima vs Hanshin 14:00 JST checked. Parser, score order, W/L/T, team selection migration and fixture suppression checks passed. Python compilation passed. Windows UI and installer upgrade still need testing before publishing the release. Other pending leagues remain pending.

Build: upload this package’s contents to the SportsBug repository root, run Build Windows installer, and test the resulting installer. Publish a GitHub release tagged v0.2.1 with SportsBug-Setup.exe attached after testing.
