# SportsBug v0.2.2

Adds a daily calendar check at 00:01 in the computer's local time. Existing event labels are redrawn immediately so today's events say Today, and a feed refresh is requested. The existing 30-second heartbeat checks the deadline; after sleep it catches up when the app resumes. A running feed request is reused. Normal live and idle refresh intervals are retained.

Includes v0.2.1 NPB schedules and published results for all 12 teams.

Validation: simulated midnight, 00:01, repeated checks, resume after a missed midnight, and an ordinary scheduled refresh. Python compilation passed. Windows installer/UI testing remains required.
