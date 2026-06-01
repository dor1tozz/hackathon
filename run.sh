#!/bin/bash

echo "========================================"
echo "Starting mail processing pipeline"
echo "========================================"

INBOX_DIR="data/inbox"
OUTPUT_DIR="data/output"
LOG_FILE="logs/processing.log"
REPORT_FILE="reports/processing_report.json"

echo "Checking input folder..."

if [ ! -d "$INBOX_DIR" ]; then
    echo "ERROR: Inbox folder not found: $INBOX_DIR"
    echo "Please create data/inbox and put .eml files there."
    exit 1
fi

echo "Inbox folder found: $INBOX_DIR"

echo "Creating output folders..."
mkdir -p "$OUTPUT_DIR"
mkdir -p "logs"
mkdir -p "reports"

echo "Running Python application..."

python3 file_main_process.py \
    --inbox "$INBOX_DIR" \
    --output "$OUTPUT_DIR" \
    --log "$LOG_FILE" \
    --json-report "$REPORT_FILE"

EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    echo "========================================"
    echo "Mail processing completed successfully"
    echo "Output folder: $OUTPUT_DIR"
    echo "Log file: $LOG_FILE"
    echo "JSON report: $REPORT_FILE"
    echo "========================================"
else
    echo "========================================"
    echo "Mail processing failed"
    echo "Exit code: $EXIT_CODE"
    echo "========================================"
    exit $EXIT_CODE
fi