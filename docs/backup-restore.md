# NC//NET backup and restore runbook

Campaign bundles contain an online SQLite snapshot, uploads, checksums, schema migration metadata, and entity counts. They contain private campaign content and password hashes; treat them as secrets.

## Create and inspect

```bash
cd ~/CBPR-helper
python3 app/backup.py create --retention 14 --reason manual
python3 app/backup.py list
python3 app/backup.py verify BUNDLE_NAME.tar.gz
```

The systemd installation runs `cbpr-backup.timer` daily around 04:00 with a randomized delay. The website does not need to stop for creation or verification.

```bash
systemctl status cbpr-backup.timer
sudo systemctl start cbpr-backup.service
journalctl -u cbpr-backup.service -n 50 --no-pager
```

## Before restoring

1. Use the same or a newer compatible NC//NET code version.
2. Verify the bundle successfully.
3. Review `schema_migrations`, counts, upload count, and creation time in the manifest/Admin preview.
4. Announce downtime: restoration requires stopping the web service.
5. Never restore an unverified archive or extract arbitrary tar files as root.

## Restore a verified local bundle

Set the exact bundle filename first:

```bash
cd ~/CBPR-helper
BUNDLE='ncnet-backup-YYYYMMDDTHHMMSSZ-xxxxxxxx.tar.gz'
python3 app/backup.py verify "$BUNDLE"
```

`backup.py verify` resolves names inside `app/data/backups` by default. Continue only when it reports `"valid": true`.

Stop the service and preserve the current state:

```bash
sudo systemctl stop cbpr
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
cp -a app/data/cbpr.db "app/data/cbpr.db.before-restore-$STAMP"
cp -a app/data/uploads "app/data/uploads.before-restore-$STAMP" 2>/dev/null || true
rm -f app/data/cbpr.db-wal app/data/cbpr.db-shm
```

Extract the already verified bundle into a private temporary directory:

```bash
RESTORE_DIR="$(mktemp -d)"
chmod 700 "$RESTORE_DIR"
tar -xzf "app/data/backups/$BUNDLE" -C "$RESTORE_DIR"
```

Install the snapshot and uploads:

```bash
install -m 600 "$RESTORE_DIR/campaign.db" app/data/cbpr.db
rm -rf app/data/uploads
mkdir -p app/data/uploads
if [ -d "$RESTORE_DIR/uploads" ]; then
  cp -a "$RESTORE_DIR/uploads/." app/data/uploads/
fi
rm -rf "$RESTORE_DIR"
```

Start and verify:

```bash
sudo systemctl start cbpr
sudo systemctl status cbpr --no-pager
curl http://127.0.0.1:8000/api/meta
journalctl -u cbpr -n 50 --no-pager
```

Log in and inspect several Characters, Contracts, Feed posts, and media before deleting the `.before-restore-*` safety copies.

## Roll back a failed restore

```bash
sudo systemctl stop cbpr
rm -f app/data/cbpr.db app/data/cbpr.db-wal app/data/cbpr.db-shm
cp -a "app/data/cbpr.db.before-restore-$STAMP" app/data/cbpr.db
rm -rf app/data/uploads
cp -a "app/data/uploads.before-restore-$STAMP" app/data/uploads 2>/dev/null || mkdir -p app/data/uploads
sudo systemctl start cbpr
```

## Moving from home server to VPS

1. Update both checkouts to compatible NC//NET versions.
2. Create and verify a bundle on the source.
3. Transfer it over SSH/SCP; do not use a public file-sharing link.
4. Put it in `app/data/backups/` on the destination.
5. Verify again on the destination.
6. Follow the stopped-service restore procedure.
7. Configure `CBPR_ADMIN_USERS`, public URL, secure cookies, and integrations separately; secrets are intentionally not included in bundles.
8. Keep the source server unchanged until the destination has been tested.

## Security notes

- Bundles are Admin-only downloads and use `Cache-Control: private, no-store`.
- Bundle paths are strict generated filenames; traversal and symlink members are rejected.
- Verification checks the archive structure, SQLite integrity, database SHA-256, and every upload SHA-256/size.
- Secrets from environment variables are not included.
- Password hashes, private notes, classified briefs, audit history, and OAuth-linked IDs are included because they are database state.
- Restoring through the live web process is intentionally unsupported; replacing an active SQLite database is unsafe.
