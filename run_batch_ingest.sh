#!/bin/bash
# Sequential batch ingest runner for 金属切削工艺技术手册.pdf
# Processes all 777 pages in 40-page batches.
# DB idempotency: already-written records are skipped automatically.
# Periodic backups protect against external DB wipes (e.g. build_db.py).

cd /root/process-expert
if [ -f .env ]; then
    source .env
fi
if [ -z "$DASHSCOPE_API_KEY" ]; then
    echo "ERROR: DASHSCOPE_API_KEY not set. Create .env with: DASHSCOPE_API_KEY=your-key"
    exit 1
fi

PDF="references/金属切削工艺技术手册.pdf"
DB="data/knowledge.db"
STEP=40

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }

backup_db() {
    BKUP="${DB}.ingest_bak_$(date '+%H%M%S')"
    cp "$DB" "$BKUP" 2>/dev/null && log "DB backup: $BKUP"
}

log "Starting sequential batch ingest of $PDF"
backup_db

FAILED_BATCHES=""
BATCH_NUM=0
for START in $(seq 1 $STEP 777); do
    END=$((START + STEP - 1))
    [ $END -gt 777 ] && END=777
    BATCH_NUM=$((BATCH_NUM + 1))
    LOG="output/ingest_batch_${START}_${END}.log"
    log "=== Batch $BATCH_NUM: pages $START-$END ==="

    python3 -u ingest/cli.py --pdf "$PDF" --db "$DB" --pages "${START}-${END}" > "$LOG" 2>&1
    EXIT=$?

    if [ $EXIT -ne 0 ]; then
        log "WARNING: Batch $START-$END exited with code $EXIT"
        FAILED_BATCHES="$FAILED_BATCHES $START-$END"
    else
        log "Batch $START-$END OK"
    fi

    # Backup every 5 batches to protect against external DB wipes
    if [ $((BATCH_NUM % 5)) -eq 0 ]; then
        backup_db
    fi

    sleep 5
done

log "=== ALL BATCHES COMPLETE ==="
[ -n "$FAILED_BATCHES" ] && log "FAILED batches:$FAILED_BATCHES"
echo "=== DB Summary ==="
sqlite3 "$DB" "SELECT 'cutting_params', COUNT(*) FROM cutting_params;" 2>/dev/null
sqlite3 "$DB" "SELECT 'tolerance_fits', COUNT(*) FROM tolerance_fits;" 2>/dev/null
sqlite3 "$DB" "SELECT 'surface_standards', COUNT(*) FROM surface_standards;" 2>/dev/null
sqlite3 "$DB" "SELECT 'equipment_specs', COUNT(*) FROM equipment_specs;" 2>/dev/null
sqlite3 "$DB" "SELECT 'experience_log', COUNT(*) FROM experience_log;" 2>/dev/null
sqlite3 "$DB" "SELECT 'kb_chunks', COUNT(*) FROM kb_chunks;" 2>/dev/null
sqlite3 "$DB" "SELECT extraction_method, COUNT(*) FROM cutting_params GROUP BY extraction_method;" 2>/dev/null
log "Done."
