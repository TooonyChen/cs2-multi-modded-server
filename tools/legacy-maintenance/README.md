# Historical maintenance source

Sanitized source imported from TooonyChen/cs2-server-ops; local capture only, no credentials, player identities or private binaries. See runtime-caveats.md before using the historical helper. These files are preserved for provenance and future framework staging, NOT invoked by the new Compose project. The old scheduler targets a single container and must never be enabled against the shared base. Its independent locking does not participate in the fleet protocol.

The new fleet updater automatically checks Steam public build IDs and hashes the mounted central mod/custom overlay. Framework/menu package upgrades are staged into that overlay from trusted, pinned artifacts; they are not silently downloaded from arbitrary GitHub latest releases. No private production package has been uploaded. Existing locally pinned CSS/Metamod/menu binaries should be imported from a stopped private snapshot before migration.

Run historical helper tests separately: `python3 -m unittest discover -s tools/legacy-maintenance -p 'test_*.py' -v`. Passing those tests does not repair the documented legacy limitations.
