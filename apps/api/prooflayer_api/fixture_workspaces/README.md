# Fixture workspaces

Synthetic repositories copied into the agent sandbox (`make sandbox-image`) and
into the mock sandbox. They contain no real credentials. The `.env.production`
file each sandbox exposes as a read-denied path is generated with a fake value
at image build time and is never committed.
