#! /bin/bash

# Configuration
PORT=22012
MACHINE=paffenroth-23.dyn.wpi.edu
MY_KEY_PATH=$HOME/.ssh/mlopskey  # Path to your personal SSH key

# Load environment variables from .env file if it exists
if [ -f .env ]; then
    echo "Loading environment variables from .env file..."
    export $(grep -v '^#' .env | xargs)
fi

# Define SSH command
COMMAND="ssh -i ${MY_KEY_PATH} -p ${PORT} -o StrictHostKeyChecking=no student-admin@${MACHINE}"

# Clean up from previous runs
rm -rf tmp

# Create a temporary directory
mkdir tmp

# Change the permissions of the directory
chmod 700 tmp

# Change to the temporary directory
cd tmp

# Copy the Smart_Confidant code
echo "Copying Smart_Confidant code..."
mkdir -p Smart_Confidant
# Copy all files except tmp and .git directories
for item in ../*; do
    base=$(basename "$item")
    if [ "$base" != "tmp" ] && [ "$base" != ".git" ]; then
        cp -r "$item" Smart_Confidant/
    fi
done

# Copy the files to the server
echo "Uploading code to server..."
scp -i ${MY_KEY_PATH} -P ${PORT} -o StrictHostKeyChecking=no -r Smart_Confidant student-admin@${MACHINE}:~/

if [ $? -eq 0 ]; then
    echo "✓ Code successfully uploaded to server"
else
    echo "✗ Failed to upload code"
    exit 1
fi

echo "Restarting application on remote server..."

# Restart the application in a single SSH session
${COMMAND} bash -s << ENDSSH
set -e
export HF_TOKEN='${HF_TOKEN}'

# Stop old process
echo "→ Stopping old process if running..."
pkill -f 'python.*app.py' || true

# Change to app directory
cd Smart_Confidant

# Start application
echo "→ Starting application..."
# Pass HF_TOKEN if it exists
if [ ! -z "$HF_TOKEN" ]; then
    echo "→ HF_TOKEN provided, API models will be available"
    nohup ~/bin/micromamba run -n smart-confidant -e HF_TOKEN="$HF_TOKEN" python -u app.py > ~/log.txt 2>&1 &
else
    echo "⚠ HF_TOKEN not set - API models will not work"
    nohup ~/bin/micromamba run -n smart-confidant python -u app.py > ~/log.txt 2>&1 &
fi

# Wait for the app to start
sleep 20

echo "✓ Restart complete"
ENDSSH

# Extract the Gradio share link from the remote log file
SHARE_LINK=$(${COMMAND} "grep -oP 'https://[a-z0-9]+\.gradio\.live' ~/log.txt | tail -1" 2>/dev/null)

echo ""
echo "=========================================="
echo "Restart complete!"
echo "Public Gradio Share Link: ${SHARE_LINK}"
echo "==========================================="

