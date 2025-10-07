#! /bin/bash

# Configuration
PORT=22012
MACHINE=paffenroth-23.dyn.wpi.edu
MY_KEY_PATH=$HOME/.ssh/mlopskey  # Path to your personal SSH key
STUDENT_ADMIN_KEY_PATH=$HOME/.ssh/student-admin_key  # Path to student-admin fallback key

# Load environment variables from .env file if it exists
if [ -f .env ]; then
    echo "Loading environment variables from .env file..."
    export $(grep -v '^#' .env | xargs)
fi

# Clean up from previous runs
ssh-keygen -f "$HOME/.ssh/known_hosts" -R "[$MACHINE]:$PORT" 2>/dev/null
rm -rf tmp

# Create a temporary directory
mkdir tmp

# Change the permissions of the directory
chmod 700 tmp

# Change to the temporary directory
cd tmp

echo "Checking if personal key works..." 
# Try connecting with personal key
if ssh -i ${MY_KEY_PATH} -p ${PORT} -o StrictHostKeyChecking=no -o ConnectTimeout=10 student-admin@${MACHINE} "echo 'success'" > /dev/null 2>&1; then
    echo "✓ Personal key works! No update needed."
    MY_KEY=${MY_KEY_PATH}
else
    echo "✗ Personal key failed. Updating with student-admin key..."
    
    # Check if the keys exist
    if [ ! -f "${MY_KEY_PATH}.pub" ]; then
        echo "Error: Personal public key not found at ${MY_KEY_PATH}.pub"
        echo "Creating a new key pair..."
        ssh-keygen -f ${MY_KEY_PATH} -t ed25519 -N ""
    fi
    
    if [ ! -f "${STUDENT_ADMIN_KEY_PATH}" ]; then
        echo "Error: Student-admin key not found at ${STUDENT_ADMIN_KEY_PATH}"
        exit 1
    fi
    
    # Read the public key content
    MY_PUB_KEY=$(cat ${MY_KEY_PATH}.pub)
    
    # Update authorized_keys on the server using student-admin key
    echo "Connecting with student-admin key to update authorized_keys..."
    ssh -i ${STUDENT_ADMIN_KEY_PATH} -p ${PORT} -o StrictHostKeyChecking=no student-admin@${MACHINE} << EOF
mkdir -p ~/.ssh
chmod 700 ~/.ssh
touch ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys
# Remove any old keys from this machine
grep -v 'rcpaffenroth@paffenroth-23' ~/.ssh/authorized_keys > ~/.ssh/authorized_keys.tmp 2>/dev/null || true
mv ~/.ssh/authorized_keys.tmp ~/.ssh/authorized_keys 2>/dev/null || true
# Add the new key
echo '${MY_PUB_KEY}' >> ~/.ssh/authorized_keys
echo 'Key updated'
EOF
    
    if [ $? -ne 0 ]; then
        echo "Failed to update key with student-admin key"
        exit 1
    fi
    
    # Verify the personal key now works
    echo "Verifying personal key..."
    sleep 2
    
    if ssh -i ${MY_KEY_PATH} -p ${PORT} -o StrictHostKeyChecking=no student-admin@${MACHINE} "echo 'success'" > /dev/null 2>&1; then
        echo "✓ Success! Personal key is now working."
        MY_KEY=${MY_KEY_PATH}
    else
        echo "✗ Personal key still not working after update"
        exit 1
    fi
fi

# Add the key to the ssh-agent
eval "$(ssh-agent -s)"
ssh-add ${MY_KEY}

# Check the key file on the server
echo "Checking authorized_keys on server:"
ssh -i ${MY_KEY} -p ${PORT} -o StrictHostKeyChecking=no student-admin@${MACHINE} "cat ~/.ssh/authorized_keys"

# Clone or copy the repo
# If using git:
# git clone https://github.com/yourusername/Smart_Confidant
# Or just copy the local directory:
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
scp -i ${MY_KEY} -P ${PORT} -o StrictHostKeyChecking=no -r Smart_Confidant student-admin@${MACHINE}:~/

if [ $? -eq 0 ]; then
    echo "✓ Code successfully uploaded to server"
else
    echo "✗ Failed to upload code"
    exit 1
fi

# Define SSH command for subsequent steps using the confirmed key
COMMAND="ssh -i ${MY_KEY} -p ${PORT} -o StrictHostKeyChecking=no student-admin@${MACHINE}"

# Run all setup in a single SSH session
echo "Setting up environment on remote server..."
# Pass HF_TOKEN to the remote session
${COMMAND} bash -s << ENDSSH
set -e
export HF_TOKEN='${HF_TOKEN}'

# Stop old process
echo "→ Stopping old process if running..."
pkill -f 'python.*app.py' || true

# Check if micromamba is installed
if [ ! -f ~/bin/micromamba ]; then
    echo "→ Installing micromamba..."
    curl -Ls https://micro.mamba.pm/api/micromamba/linux-64/latest | tar -xvj -C ~/ bin/micromamba
    mkdir -p ~/micromamba
    export MAMBA_ROOT_PREFIX=~/micromamba
    echo 'export MAMBA_ROOT_PREFIX=~/micromamba' >> ~/.bashrc
    echo 'eval "$(~/bin/micromamba shell hook -s bash)"' >> ~/.bashrc
    echo "✓ Micromamba installed"
else
    echo "✓ Micromamba already installed"
    export MAMBA_ROOT_PREFIX=~/micromamba
fi

eval "$(~/bin/micromamba shell hook -s bash)" 2>/dev/null || true

cd Smart_Confidant

# Check if environment exists
if ~/bin/micromamba env list | grep -q "smart-confidant"; then
    echo "→ Updating existing environment..."
    ~/bin/micromamba install -n smart-confidant -f environment.yml -y
else
    echo "→ Creating new environment..."
    ~/bin/micromamba create -f environment.yml -y
fi

# Check if uv is installed
if ! ~/bin/micromamba run -n smart-confidant which uv &>/dev/null; then
    echo "→ Installing uv..."
    ~/bin/micromamba run -n smart-confidant pip install uv
else
    echo "✓ uv already installed"
fi

# Install/update dependencies
echo "→ Installing/updating dependencies..."
~/bin/micromamba run -n smart-confidant uv pip install -e .

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
sleep 5

echo "✓ Setup complete"
ENDSSH

# Extract the Gradio share link from the remote log file
SHARE_LINK=$(${COMMAND} "grep -oP 'https://[a-z0-9]+\.gradio\.live' ~/log.txt | tail -1" 2>/dev/null)

echo ""
echo "=========================================="
echo "Deployment complete!"
echo "Public Gradio Share Link: ${SHARE_LINK}"
echo "==========================================="


