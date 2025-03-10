#!/bin/bash

SOURCE_DIR="/home/chunj/code/multisentimentarcs"
DEST_DIR="/mnt/usbssd/backup/multisentimentarcs"

mkdir -p "$DEST_DIR"

# Get total number of files
total_files=$(find "$SOURCE_DIR" -type f | wc -l)
counter=0

# Copy files one by one
find "$SOURCE_DIR" -type f | while read -r file; do
    # Compute relative path
    rel_path="${file#$SOURCE_DIR/}"
    dest_file="$DEST_DIR/$rel_path"
    
    # Create parent directory if needed
    mkdir -p "$(dirname "$dest_file")"

    # Check if file already exists
    if [ -e "$dest_file" ]; then
        echo "[SKIP] $rel_path"
    else
        cp "$file" "$dest_file"
        echo "[COPY] $rel_path"
    fi
    
    # Update progress
    ((counter++))
    percent=$(( 100 * counter / total_files ))
    echo "Progress: $percent% ($counter/$total_files) files copied"
done

